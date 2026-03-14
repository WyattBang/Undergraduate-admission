#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import requests
from rapidocr_onnxruntime import RapidOCR

MCP_URL = "http://localhost:18060/mcp"
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/122.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
}

TOEFL_RE = re.compile(r"(?:托福|toefl)\D{0,8}(\d{2,3})", re.IGNORECASE)
IELTS_RE = re.compile(r"(?:雅思|ielts)\D{0,8}(\d(?:\.\d)?)", re.IGNORECASE)
GPA_RE = re.compile(r"(?:gpa|绩点)\D{0,8}([0-4](?:\.\d{1,3})?)", re.IGNORECASE)
AP_RE = re.compile(r"\bAP\b", re.IGNORECASE)
IB_RE = re.compile(r"\bIB\b", re.IGNORECASE)
ALEVEL_RE = re.compile(r"\bA-?Level\b", re.IGNORECASE)

SCHOOL_HINTS = [
    "Harvard", "Stanford", "MIT", "Yale", "Princeton", "Columbia", "Cornell", "UCLA", "UC Berkeley",
    "哈佛", "斯坦福", "麻省理工", "耶鲁", "普林斯顿", "哥大", "康奈尔", "伯克利", "加州大学",
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Search Xiaohongshu posts, download images, OCR, and normalize data")
    parser.add_argument("--keyword", required=True)
    parser.add_argument("--limit", type=int, default=8)
    parser.add_argument("--output", default=None, help="jsonl output file path")
    parser.add_argument("--image-dir", default="data/raw/xhs_mcp_images")
    return parser.parse_args()


class MCPClient:
    def __init__(self, mcp_url: str = MCP_URL) -> None:
        self.mcp_url = mcp_url
        self.session = requests.Session()
        self.session.headers.update({"Content-Type": "application/json"})
        self.mcp_session_id: str | None = None

    def initialize(self) -> None:
        payload = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "initialize",
            "params": {
                "protocolVersion": "2025-06-18",
                "capabilities": {},
                "clientInfo": {"name": "codex-xhs-ocr", "version": "1.0"},
            },
        }
        resp = self.session.post(self.mcp_url, data=json.dumps(payload), timeout=30)
        resp.raise_for_status()
        self.mcp_session_id = resp.headers.get("Mcp-Session-Id")

        headers = {"Mcp-Session-Id": self.mcp_session_id} if self.mcp_session_id else {}
        self.session.post(
            self.mcp_url,
            headers=headers,
            data=json.dumps({"jsonrpc": "2.0", "method": "notifications/initialized", "params": {}}),
            timeout=30,
        )

    def call_tool(self, name: str, arguments: dict[str, Any]) -> dict[str, Any]:
        headers = {"Mcp-Session-Id": self.mcp_session_id} if self.mcp_session_id else {}
        payload = {
            "jsonrpc": "2.0",
            "id": int(datetime.now(timezone.utc).timestamp() * 1000),
            "method": "tools/call",
            "params": {"name": name, "arguments": arguments},
        }
        resp = self.session.post(self.mcp_url, headers=headers, data=json.dumps(payload), timeout=90)
        resp.raise_for_status()
        body = resp.json()
        content = body.get("result", {}).get("content", [])
        if not content:
            raise RuntimeError(f"tool {name} returned empty content: {body}")
        text = content[0].get("text", "")
        return json.loads(text)


def safe_filename(raw: str) -> str:
    return re.sub(r"[^a-zA-Z0-9_-]+", "_", raw)[:80].strip("_") or "xhs"


def maybe_https(url: str) -> str:
    if url.startswith("http://"):
        return "https://" + url[len("http://") :]
    return url


def extract_structured(text: str) -> dict[str, Any]:
    def as_num(m: re.Match[str] | None) -> float | int | None:
        if not m:
            return None
        s = m.group(1)
        return float(s) if "." in s else int(s)

    schools = [s for s in SCHOOL_HINTS if s.lower() in text.lower()]
    return {
        "toefl": as_num(TOEFL_RE.search(text)),
        "ielts": as_num(IELTS_RE.search(text)),
        "gpa": as_num(GPA_RE.search(text)),
        "has_ap": bool(AP_RE.search(text)),
        "has_ib": bool(IB_RE.search(text)),
        "has_alevel": bool(ALEVEL_RE.search(text)),
        "school_mentions": schools,
    }


def flatten_ocr_result(result: Any) -> str:
    if not result:
        return ""
    chunks: list[str] = []
    for item in result:
        if not isinstance(item, (list, tuple)) or len(item) < 2:
            continue
        text = str(item[1]).strip()
        if text:
            chunks.append(text)
    return "\n".join(chunks)


def publish_time(value: Any) -> str | None:
    if value is None:
        return None
    try:
        ts = int(value)
        if ts > 10_000_000_000:
            ts = ts // 1000
        return datetime.fromtimestamp(ts, tz=timezone.utc).isoformat()
    except Exception:
        return None


def main() -> None:
    args = parse_args()
    output_path = Path(args.output) if args.output else Path("data/raw") / f"xhs_{safe_filename(args.keyword)}_ocr.jsonl"
    image_dir = Path(args.image_dir)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    image_dir.mkdir(parents=True, exist_ok=True)

    client = MCPClient()
    client.initialize()

    search = client.call_tool("search_feeds", {"keyword": args.keyword})
    feeds = [f for f in search.get("feeds", []) if f.get("modelType") == "note"][: args.limit]

    ocr_engine = RapidOCR()
    rows: list[dict[str, Any]] = []

    img_session = requests.Session()
    img_session.headers.update(HEADERS)

    for feed in feeds:
        feed_id = feed.get("id")
        xsec_token = feed.get("xsecToken")
        if not feed_id or not xsec_token:
            continue

        note_card = feed.get("noteCard", {}) or {}
        fallback_title = str(note_card.get("displayTitle", ""))
        fallback_author = str((note_card.get("user", {}) or {}).get("nickname", ""))
        fallback_interact = note_card.get("interactInfo", {}) or {}
        fallback_cover_url = maybe_https(
            str((note_card.get("cover", {}) or {}).get("urlDefault") or (note_card.get("cover", {}) or {}).get("urlPre") or "")
        )

        try:
            detail = client.call_tool(
                "get_feed_detail",
                {"feed_id": feed_id, "xsec_token": xsec_token, "load_all_comments": False},
            )
        except Exception as exc:  # noqa: BLE001
            # Fallback path: use cover image from search payload to avoid losing the sample.
            if fallback_cover_url:
                image_records: list[dict[str, Any]] = []
                ocr_texts: list[str] = []
                local_path = image_dir / f"{feed_id}_cover.webp"
                try:
                    resp = img_session.get(fallback_cover_url, timeout=30)
                    resp.raise_for_status()
                    local_path.write_bytes(resp.content)
                    ocr_result, _ = ocr_engine(str(local_path))
                    ocr_text = flatten_ocr_result(ocr_result)
                    if ocr_text:
                        ocr_texts.append(ocr_text)
                    image_records.append(
                        {
                            "index": 1,
                            "url": fallback_cover_url,
                            "local_path": str(local_path),
                            "download_ok": True,
                            "ocr_text": ocr_text,
                        }
                    )
                except Exception as img_exc:  # noqa: BLE001
                    image_records.append(
                        {
                            "index": 1,
                            "url": fallback_cover_url,
                            "local_path": str(local_path),
                            "download_ok": False,
                            "ocr_error": str(img_exc),
                        }
                    )

                merged_text = "\n".join([fallback_title] + ocr_texts)
                rows.append(
                    {
                        "keyword": args.keyword,
                        "feed_id": feed_id,
                        "xsec_token": xsec_token,
                        "title": fallback_title,
                        "desc": "",
                        "publish_time": None,
                        "author": fallback_author,
                        "liked_count": fallback_interact.get("likedCount"),
                        "comment_count": fallback_interact.get("commentCount"),
                        "image_count": len(image_records),
                        "images": image_records,
                        "ocr_text_all": "\n".join(ocr_texts),
                        "extracted": extract_structured(merged_text),
                        "warning": f"detail_failed_fallback_cover: {exc}",
                        "error": None,
                    }
                )
            else:
                rows.append({"keyword": args.keyword, "feed_id": feed_id, "error": f"detail_failed: {exc}"})
            continue

        note = detail.get("data", {}).get("note", {})
        image_list = note.get("imageList", []) or []

        image_records: list[dict[str, Any]] = []
        ocr_texts: list[str] = []

        for idx, image in enumerate(image_list):
            url = maybe_https(str(image.get("urlDefault") or image.get("urlPre") or "").strip())
            if not url:
                continue
            ext = ".webp"
            filename = f"{feed_id}_{idx+1}{ext}"
            local_path = image_dir / filename

            try:
                resp = img_session.get(url, timeout=30)
                resp.raise_for_status()
                local_path.write_bytes(resp.content)

                ocr_result, _ = ocr_engine(str(local_path))
                ocr_text = flatten_ocr_result(ocr_result)
            except Exception as exc:  # noqa: BLE001
                ocr_text = ""
                image_records.append(
                    {
                        "index": idx + 1,
                        "url": url,
                        "local_path": str(local_path),
                        "download_ok": False,
                        "ocr_error": str(exc),
                    }
                )
                continue

            if ocr_text:
                ocr_texts.append(ocr_text)
            image_records.append(
                {
                    "index": idx + 1,
                    "url": url,
                    "local_path": str(local_path),
                    "download_ok": True,
                    "ocr_text": ocr_text,
                }
            )

        title = str(note.get("title", ""))
        desc = str(note.get("desc", ""))
        merged_text = "\n".join([title, desc] + ocr_texts)

        row = {
            "keyword": args.keyword,
            "feed_id": feed_id,
            "xsec_token": xsec_token,
            "title": title,
            "desc": desc,
            "publish_time": publish_time(note.get("time")),
            "author": note.get("user", {}).get("nickname"),
            "liked_count": note.get("interactInfo", {}).get("likedCount"),
            "comment_count": note.get("interactInfo", {}).get("commentCount"),
            "image_count": len(image_records),
            "images": image_records,
            "ocr_text_all": "\n".join(ocr_texts),
            "extracted": extract_structured(merged_text),
            "error": None,
        }
        rows.append(row)

    with output_path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")

    ok = sum(1 for r in rows if not r.get("error"))
    print(f"saved={output_path}")
    print(f"rows={len(rows)} success={ok}")


if __name__ == "__main__":
    main()
