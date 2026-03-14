#!/usr/bin/env python3
from __future__ import annotations

import argparse
import base64
import csv
import json
import mimetypes
import os
import re
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlparse

import requests

MCP_URL = "http://localhost:18060/mcp"
LOGIN_STATUS_URL = "http://localhost:18060/api/v1/login/status"
SEARCH_URL = "http://localhost:18060/api/v1/feeds/search"

HTTP_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/122.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
}

EXTRACTION_JSON_SCHEMA: dict[str, Any] = {
    "name": "xhs_application_case",
    "strict": True,
    "schema": {
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "has_application_case": {"type": "boolean"},
            "applicant_profile": {
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "english_tests": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "additionalProperties": False,
                            "properties": {
                                "test": {"type": "string"},
                                "score": {"type": "string"},
                            },
                            "required": ["test", "score"],
                        },
                    },
                    "gpa": {"type": ["string", "null"]},
                    "curriculum_type": {"type": ["string", "null"]},
                    "ap_scores": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "additionalProperties": False,
                            "properties": {
                                "subject": {"type": "string"},
                                "score": {"type": "string"},
                            },
                            "required": ["subject", "score"],
                        },
                    },
                    "ib_score": {"type": ["string", "null"]},
                    "alevel_scores": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "additionalProperties": False,
                            "properties": {
                                "subject": {"type": "string"},
                                "grade": {"type": "string"},
                            },
                            "required": ["subject", "grade"],
                        },
                    },
                },
                "required": [
                    "english_tests",
                    "gpa",
                    "curriculum_type",
                    "ap_scores",
                    "ib_score",
                    "alevel_scores",
                ],
            },
            "experience": {
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "activities": {"type": "array", "items": {"type": "string"}},
                    "research": {"type": "array", "items": {"type": "string"}},
                    "awards": {"type": "array", "items": {"type": "string"}},
                },
                "required": ["activities", "research", "awards"],
            },
            "applications": {
                "type": "array",
                "items": {
                    "type": "object",
                    "additionalProperties": False,
                    "properties": {
                        "school": {"type": "string"},
                        "major": {"type": ["string", "null"]},
                        "result": {"type": "string"},
                        "cycle": {"type": ["string", "null"]},
                        "evidence": {"type": "string"},
                    },
                    "required": ["school", "major", "result", "cycle", "evidence"],
                },
            },
            "confidence": {"type": "number"},
            "missing_fields": {"type": "array", "items": {"type": "string"}},
            "evidence_snippets": {"type": "array", "items": {"type": "string"}},
            "notes": {"type": ["string", "null"]},
        },
        "required": [
            "has_application_case",
            "applicant_profile",
            "experience",
            "applications",
            "confidence",
            "missing_fields",
            "evidence_snippets",
            "notes",
        ],
    },
}

SYSTEM_PROMPT = """
你是留学申请信息抽取器。任务：从帖子文本和配图中提取“申请背景+申请结果”。
要求：
1) 只抽取能被文本或图片证据支持的信息，不猜测。
2) result 仅使用 offer/reject/waitlist/unknown。
3) 如果帖子不是个人申请案例（例如纯观点、广告、工具介绍），has_application_case=false。
4) 置信度范围 0~1。证据不足时降低置信度并填 missing_fields。
5) 输出必须满足给定 JSON schema。
""".strip()


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
                "clientInfo": {"name": "codex-xhs-ai", "version": "1.0"},
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

    def call_tool(self, name: str, arguments: dict[str, Any], timeout_sec: float = 120.0) -> dict[str, Any]:
        headers = {"Mcp-Session-Id": self.mcp_session_id} if self.mcp_session_id else {}
        payload = {
            "jsonrpc": "2.0",
            "id": int(datetime.now(timezone.utc).timestamp() * 1000),
            "method": "tools/call",
            "params": {"name": name, "arguments": arguments},
        }
        resp = self.session.post(self.mcp_url, headers=headers, data=json.dumps(payload), timeout=timeout_sec)
        resp.raise_for_status()
        body = resp.json()
        content = body.get("result", {}).get("content", [])
        if not content:
            raise RuntimeError(f"tool {name} returned empty content: {body}")
        text = content[0].get("text", "")
        return safe_json_loads(text)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Xiaohongshu MCP + Multimodal AI extraction to structured table")
    parser.add_argument("--keyword", required=True)
    parser.add_argument("--limit", type=int, default=12)
    parser.add_argument(
        "--target-raw",
        type=int,
        default=0,
        help="target unique candidate posts before extraction (0 means single-search mode)",
    )
    parser.add_argument(
        "--max-search-calls",
        type=int,
        default=36,
        help="max number of HTTP search calls when target-raw > 0",
    )
    parser.add_argument("--max-images-per-post", type=int, default=4)
    parser.add_argument("--model", default="gpt-4.1-mini")
    parser.add_argument("--image-dir", default="data/raw/xhs_ai_images")
    parser.add_argument("--output-jsonl", default=None)
    parser.add_argument("--output-csv", default=None)
    parser.add_argument("--output-raw-jsonl", default=None)
    parser.add_argument("--confidence-threshold", type=float, default=0.72)
    parser.add_argument("--openai-timeout-sec", type=float, default=45.0)
    parser.add_argument("--openai-retries", type=int, default=2)
    parser.add_argument("--progress-every", type=int, default=5)
    parser.add_argument("--seed-jsonl", default=None, help="Optional JSONL seed file with detail URLs")
    parser.add_argument("--seed-link-field", default="帖子详情页链接")
    parser.add_argument("--single-search-retries", type=int, default=2)
    parser.add_argument("--single-search-timeout-sec", type=float, default=90.0)
    parser.add_argument("--disable-single-search-http-fallback", action="store_true")
    parser.add_argument("--detail-timeout-sec", type=float, default=35.0)
    parser.add_argument("--detail-retries", type=int, default=1)
    parser.add_argument("--dry-run", action="store_true", help="No OpenAI call. Build payload and use heuristic fallback.")
    return parser.parse_args()


def load_local_env() -> None:
    # Priority: current environment > local .env files.
    env_candidates = [
        Path.cwd() / ".env",
        Path(__file__).resolve().parents[1] / ".env",
        Path(__file__).resolve().parents[2] / ".env",
    ]
    for env_path in env_candidates:
        if not env_path.exists():
            continue
        for line in env_path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            key = key.strip()
            value = value.strip().strip('"').strip("'")
            if key and key not in os.environ:
                os.environ[key] = value


def safe_json_loads(text: str) -> dict[str, Any]:
    text = (text or "").strip()
    if not text:
        return {}
    try:
        obj = json.loads(text)
        if isinstance(obj, dict):
            return obj
        return {"value": obj}
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", text, re.S)
        if not match:
            raise
        obj = json.loads(match.group(0))
        if isinstance(obj, dict):
            return obj
        return {"value": obj}


def maybe_https(url: str) -> str:
    if url.startswith("http://"):
        return "https://" + url[len("http://") :]
    return url


def safe_filename(raw: str) -> str:
    return re.sub(r"[^a-zA-Z0-9_-]+", "_", raw)[:100].strip("_") or "xhs"


def check_login_status() -> bool:
    try:
        resp = requests.get(LOGIN_STATUS_URL, timeout=10)
        resp.raise_for_status()
        body = resp.json()
        return bool(body.get("data", {}).get("is_logged_in"))
    except Exception:
        return False


def build_query_variants(base_keyword: str) -> list[str]:
    variants = [
        base_keyword,
        f"{base_keyword} 25fall",
        f"{base_keyword} 26fall",
        f"{base_keyword} offer",
        f"{base_keyword} 录取",
        f"{base_keyword} 托福",
        f"{base_keyword} SAT",
        f"{base_keyword} GPA",
        f"{base_keyword} CS",
        f"{base_keyword} economics",
        f"{base_keyword} common app",
        f"{base_keyword} 早申",
        f"{base_keyword} rd",
        f"{base_keyword} 背景",
        f"{base_keyword} 案例",
    ]
    seen: set[str] = set()
    deduped: list[str] = []
    for v in variants:
        v = v.strip()
        if not v or v in seen:
            continue
        seen.add(v)
        deduped.append(v)
    return deduped


def search_feeds_http(
    keyword: str,
    sort_by: str,
    note_type: str,
    publish_time: str,
) -> list[dict[str, Any]]:
    payload = {
        "keyword": keyword,
        "filters": {
            "sort_by": sort_by,
            "note_type": note_type,
            "publish_time": publish_time,
        },
    }
    resp = requests.post(SEARCH_URL, json=payload, timeout=30)
    resp.raise_for_status()
    body = resp.json()
    if not body.get("success"):
        return []
    return [f for f in body.get("data", {}).get("feeds", []) if f.get("modelType") == "note"]


def parse_feed_from_url(url: str) -> tuple[str, str] | None:
    if not url:
        return None
    parsed = urlparse(url)
    path_match = re.search(r"/(?:search_result|explore)/([0-9a-zA-Z]+)", parsed.path or "")
    if not path_match:
        return None
    feed_id = path_match.group(1)
    xsec_token = parse_qs(parsed.query or "").get("xsec_token", [""])[0]
    if not feed_id or not xsec_token:
        return None
    return feed_id, xsec_token


def load_seed_items(seed_jsonl: Path, keyword: str, link_field: str, limit: int) -> list[dict[str, Any]]:
    if not seed_jsonl.exists():
        raise FileNotFoundError(f"seed file not found: {seed_jsonl}")

    items: list[dict[str, Any]] = []
    seen_feed_ids: set[str] = set()
    for line in seed_jsonl.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            obj = json.loads(line)
        except Exception:
            continue

        feed_id = ""
        xsec_token = ""
        link = str(obj.get(link_field, "")).strip()
        parsed = parse_feed_from_url(link)
        if parsed:
            feed_id, xsec_token = parsed
        else:
            feed_id = str(obj.get("feed_id", "")).strip()
            xsec_token = str(obj.get("xsec_token", "")).strip()
            if not feed_id or not xsec_token:
                continue

        if feed_id in seen_feed_ids:
            continue
        seen_feed_ids.add(feed_id)

        items.append(
            {
                "feed_id": feed_id,
                "xsec_token": xsec_token,
                "source_query": str(obj.get("搜索词") or obj.get("keyword") or keyword),
                "source_filter": "seed_jsonl",
                "fallback_title": str(obj.get("标题") or obj.get("title") or ""),
                "fallback_author": str(obj.get("作者") or obj.get("author") or ""),
            }
        )
        if len(items) >= limit:
            break

    return items


def single_query_search_with_retry(
    client: MCPClient,
    keyword: str,
    retries: int,
    timeout_sec: float,
    enable_http_fallback: bool,
) -> list[dict[str, Any]]:
    last_err: Exception | None = None
    for attempt in range(max(0, retries) + 1):
        try:
            search = client.call_tool("search_feeds", {"keyword": keyword}, timeout_sec=timeout_sec)
            feeds = [f for f in search.get("feeds", []) if f.get("modelType") == "note"]
            if feeds:
                for feed in feeds:
                    feed["_source_query"] = keyword
                    feed["_source_filter"] = "mcp_single_search"
                print(f"single_search_source=mcp count={len(feeds)}")
                return feeds
        except Exception as exc:  # noqa: BLE001
            last_err = exc
        if attempt < retries:
            time.sleep(1.2 * (attempt + 1))

    if not enable_http_fallback:
        if last_err is not None:
            raise last_err
        return []

    fallback_filters = [
        ("综合", "不限", "不限"),
        ("最新", "图文", "不限"),
        ("最热", "图文", "半年内"),
    ]
    deduped_feeds: dict[str, dict[str, Any]] = {}
    for sort_by, note_type, publish_time in fallback_filters:
        try:
            result_feeds = search_feeds_http(keyword, sort_by, note_type, publish_time)
        except Exception:
            continue
        for feed in result_feeds:
            feed_id = str(feed.get("id", ""))
            if not feed_id or feed_id in deduped_feeds:
                continue
            feed["_source_query"] = keyword
            feed["_source_filter"] = f"http_fallback:{sort_by}/{note_type}/{publish_time}"
            deduped_feeds[feed_id] = feed
        if deduped_feeds:
            break

    feeds = list(deduped_feeds.values())
    print(f"single_search_source=http_fallback count={len(feeds)}")
    return feeds


def build_post_from_feed(
    client: MCPClient,
    *,
    feed_id: str,
    xsec_token: str,
    source_query: str,
    source_filter: str,
    fallback_title: str = "",
    fallback_author: str = "",
    detail_timeout_sec: float = 35.0,
    detail_retries: int = 1,
) -> dict[str, Any]:
    fallback = {
        "title": fallback_title,
        "desc": "",
        "author": fallback_author,
        "publish_time": None,
        "liked_count": "",
        "comment_count": "",
        "image_urls": [],
        "warning": "",
        "source_query": source_query,
        "source_filter": source_filter,
    }
    last_err: Exception | None = None
    detail: dict[str, Any] | None = None
    for attempt in range(max(0, detail_retries) + 1):
        try:
            detail = client.call_tool(
                "get_feed_detail",
                {"feed_id": feed_id, "xsec_token": xsec_token, "load_all_comments": False},
                timeout_sec=detail_timeout_sec,
            )
            break
        except Exception as exc:  # noqa: BLE001
            last_err = exc
            if attempt < max(0, detail_retries):
                time.sleep(1.0 * (attempt + 1))
    try:
        if detail is None:
            raise RuntimeError(last_err or "detail unavailable")
        note = detail.get("data", {}).get("note", {})
        image_list = note.get("imageList", []) or []
        image_urls = [
            maybe_https(str(img.get("urlDefault") or img.get("urlPre") or ""))
            for img in image_list
            if str(img.get("urlDefault") or img.get("urlPre") or "").strip()
        ]
        return {
            "feed_id": feed_id,
            "xsec_token": xsec_token,
            "title": str(note.get("title", "")),
            "desc": str(note.get("desc", "")),
            "author": str((note.get("user", {}) or {}).get("nickname", "")),
            "publish_time": epoch_to_iso(note.get("time")),
            "liked_count": (note.get("interactInfo", {}) or {}).get("likedCount", ""),
            "comment_count": (note.get("interactInfo", {}) or {}).get("commentCount", ""),
            "image_urls": image_urls,
            "warning": "",
            "source_query": source_query,
            "source_filter": source_filter,
        }
    except Exception as exc:  # noqa: BLE001
        return {
            "feed_id": feed_id,
            "xsec_token": xsec_token,
            **fallback,
            "warning": f"detail_failed_fallback_cover: {exc}",
        }


def gather_posts(
    keyword: str,
    limit: int,
    target_raw: int = 0,
    max_search_calls: int = 36,
    seed_jsonl: Path | None = None,
    seed_link_field: str = "帖子详情页链接",
    single_search_retries: int = 2,
    single_search_timeout_sec: float = 90.0,
    single_search_http_fallback: bool = True,
    detail_timeout_sec: float = 35.0,
    detail_retries: int = 1,
) -> list[dict[str, Any]]:
    client = MCPClient()
    client.initialize()

    if seed_jsonl is not None:
        seed_items = load_seed_items(seed_jsonl, keyword, seed_link_field, limit)
        print(f"seed_items={len(seed_items)} source={seed_jsonl}")
        posts: list[dict[str, Any]] = []
        for i, item in enumerate(seed_items, 1):
            if i == 1 or i % 5 == 0:
                print(f"detail_progress={i}/{len(seed_items)} (seed)")
            posts.append(
                build_post_from_feed(
                    client,
                    feed_id=str(item.get("feed_id", "")),
                    xsec_token=str(item.get("xsec_token", "")),
                    source_query=str(item.get("source_query", keyword)),
                    source_filter=str(item.get("source_filter", "seed_jsonl")),
                    fallback_title=str(item.get("fallback_title", "")),
                    fallback_author=str(item.get("fallback_author", "")),
                    detail_timeout_sec=detail_timeout_sec,
                    detail_retries=detail_retries,
                )
            )
        return posts

    feeds: list[dict[str, Any]] = []
    if target_raw > 0:
        query_variants = build_query_variants(keyword)
        filter_combos = [
            ("综合", "不限", "不限"),
            ("最新", "不限", "不限"),
            ("最热", "不限", "不限"),
            ("最新", "图文", "不限"),
            ("最新", "图文", "一周内"),
            ("最新", "图文", "半年内"),
            ("最热", "图文", "半年内"),
            ("综合", "图文", "不限"),
        ]
        deduped_feeds: dict[str, dict[str, Any]] = {}
        total_calls = 0

        for query in query_variants:
            for sort_by, note_type, publish_time in filter_combos:
                if total_calls >= max_search_calls:
                    break
                total_calls += 1
                try:
                    result_feeds = search_feeds_http(query, sort_by, note_type, publish_time)
                except Exception:
                    continue
                for feed in result_feeds:
                    feed_id = str(feed.get("id", ""))
                    if not feed_id or feed_id in deduped_feeds:
                        continue
                    feed["_source_query"] = query
                    feed["_source_filter"] = f"{sort_by}/{note_type}/{publish_time}"
                    deduped_feeds[feed_id] = feed
                if total_calls % 6 == 0:
                    print(
                        f"search_progress calls={total_calls}/{max_search_calls} "
                        f"unique_candidates={len(deduped_feeds)}"
                    )
                if len(deduped_feeds) >= target_raw:
                    break
            if total_calls >= max_search_calls:
                break
            if len(deduped_feeds) >= target_raw:
                break
        feeds = list(deduped_feeds.values())
        print(
            f"search_candidates={len(feeds)} target_raw={target_raw} "
            f"queries={len(query_variants)} calls={total_calls}"
        )
    else:
        feeds = single_query_search_with_retry(
            client,
            keyword,
            retries=single_search_retries,
            timeout_sec=single_search_timeout_sec,
            enable_http_fallback=single_search_http_fallback,
        )

    feeds = feeds[:limit]

    posts: list[dict[str, Any]] = []
    for i, feed in enumerate(feeds, 1):
        feed_id = str(feed.get("id", ""))
        xsec_token = str(feed.get("xsecToken", ""))
        if not feed_id or not xsec_token:
            continue
        if i == 1 or i % 5 == 0:
            print(f"detail_progress={i}/{len(feeds)}")

        note_card = feed.get("noteCard", {}) or {}
        fallback = {
            "title": str(note_card.get("displayTitle", "")),
            "desc": "",
            "author": str((note_card.get("user", {}) or {}).get("nickname", "")),
            "publish_time": None,
            "liked_count": (note_card.get("interactInfo", {}) or {}).get("likedCount", ""),
            "comment_count": (note_card.get("interactInfo", {}) or {}).get("commentCount", ""),
            "image_urls": [
                maybe_https(
                    str(
                        (note_card.get("cover", {}) or {}).get("urlDefault")
                        or (note_card.get("cover", {}) or {}).get("urlPre")
                        or ""
                    )
                )
            ],
            "warning": "",
            "source_query": str(feed.get("_source_query", keyword)),
            "source_filter": str(feed.get("_source_filter", "")),
        }

        posts.append(
            build_post_from_feed(
                client,
                feed_id=feed_id,
                xsec_token=xsec_token,
                source_query=str(feed.get("_source_query", keyword)),
                source_filter=str(feed.get("_source_filter", "")),
                fallback_title=str(fallback.get("title", "")),
                fallback_author=str(fallback.get("author", "")),
                detail_timeout_sec=detail_timeout_sec,
                detail_retries=detail_retries,
            )
        )

    return posts


def epoch_to_iso(value: Any) -> str | None:
    if value is None:
        return None
    try:
        ts = int(value)
        if ts > 10_000_000_000:
            ts = ts // 1000
        return datetime.fromtimestamp(ts, tz=timezone.utc).isoformat()
    except Exception:
        return None


def download_images(image_urls: list[str], image_dir: Path, feed_id: str, max_count: int) -> list[Path]:
    image_dir.mkdir(parents=True, exist_ok=True)
    session = requests.Session()
    session.headers.update(HTTP_HEADERS)

    local_paths: list[Path] = []
    for idx, url in enumerate(image_urls[:max_count], 1):
        if not url:
            continue

        url = maybe_https(url)
        suffix = Path(url.split("?", 1)[0]).suffix.lower() or ".webp"
        filename = f"{feed_id}_{idx}{suffix if len(suffix) <= 6 else '.img'}"
        local_path = image_dir / filename
        try:
            resp = session.get(url, timeout=30)
            resp.raise_for_status()
            local_path.write_bytes(resp.content)
            local_paths.append(local_path)
        except Exception:
            continue

    return local_paths


def image_to_data_url(path: Path) -> str:
    mime, _ = mimetypes.guess_type(str(path))
    mime = mime or "image/webp"
    b64 = base64.b64encode(path.read_bytes()).decode("utf-8")
    return f"data:{mime};base64,{b64}"


def heuristic_extract(post: dict[str, Any]) -> dict[str, Any]:
    text = "\n".join([post.get("title", ""), post.get("desc", "")])
    gpa_match = re.search(r"(?:gpa|绩点)\D{0,8}([0-4](?:\.\d{1,3})?)", text, re.I)
    gpa = gpa_match.group(1) if gpa_match else None
    return {
        "has_application_case": bool(text.strip()),
        "applicant_profile": {
            "english_tests": [],
            "gpa": gpa,
            "curriculum_type": None,
            "ap_scores": [],
            "ib_score": None,
            "alevel_scores": [],
        },
        "experience": {"activities": [], "research": [], "awards": []},
        "applications": [],
        "confidence": 0.2,
        "missing_fields": ["not_extracted_in_dry_run"],
        "evidence_snippets": [text[:300]],
        "notes": "dry_run mode",
    }


def call_multimodal_extractor(
    model: str,
    post: dict[str, Any],
    image_paths: list[Path],
    dry_run: bool,
    openai_timeout_sec: float,
    openai_retries: int,
) -> dict[str, Any]:
    if dry_run:
        return heuristic_extract(post)

    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY is required unless --dry-run is used")

    from openai import OpenAI

    client = OpenAI(api_key=api_key, timeout=openai_timeout_sec, max_retries=0)

    user_content: list[dict[str, Any]] = [
        {
            "type": "text",
            "text": (
                "请抽取这条帖子是否是申请案例，以及申请背景与录取结果。"
                "\n\n帖子元数据:"
                f"\n- 标题: {post.get('title','')}"
                f"\n- 正文: {post.get('desc','')}"
                f"\n- 作者: {post.get('author','')}"
            ),
        }
    ]

    for path in image_paths:
        user_content.append({"type": "image_url", "image_url": {"url": image_to_data_url(path)}})

    last_err: Exception | None = None
    for attempt in range(openai_retries + 1):
        try:
            response = client.chat.completions.create(
                model=model,
                temperature=0,
                response_format={"type": "json_schema", "json_schema": EXTRACTION_JSON_SCHEMA},
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": user_content},
                ],
                timeout=openai_timeout_sec,
            )
            message_text = response.choices[0].message.content or "{}"
            return safe_json_loads(message_text)
        except Exception as exc:  # noqa: BLE001
            last_err = exc
            if attempt >= openai_retries:
                break
            time.sleep(1.5 * (attempt + 1))

    raise RuntimeError(f"openai_extract_failed after retries: {last_err}")


def normalize_result_row(
    keyword: str,
    post: dict[str, Any],
    extracted: dict[str, Any],
    image_paths: list[Path],
    confidence_threshold: float,
) -> dict[str, Any]:
    applications = extracted.get("applications", []) if isinstance(extracted, dict) else []
    offers = [a.get("school", "") for a in applications if str(a.get("result", "")).lower() == "offer"]

    confidence = float(extracted.get("confidence", 0) or 0)
    needs_review = (
        confidence < confidence_threshold
        or not bool(extracted.get("has_application_case", False))
        or len(applications) == 0
    )

    profile = extracted.get("applicant_profile", {}) if isinstance(extracted, dict) else {}
    experience = extracted.get("experience", {}) if isinstance(extracted, dict) else {}

    return {
        "keyword": keyword,
        "feed_id": post.get("feed_id", ""),
        "source_query": post.get("source_query", keyword),
        "source_filter": post.get("source_filter", ""),
        "title": post.get("title", ""),
        "author": post.get("author", ""),
        "publish_time": post.get("publish_time", ""),
        "liked_count": post.get("liked_count", ""),
        "comment_count": post.get("comment_count", ""),
        "image_count": len(image_paths),
        "local_images": "|".join(str(x) for x in image_paths),
        "has_application_case": extracted.get("has_application_case", False),
        "english_tests": json.dumps(profile.get("english_tests", []), ensure_ascii=False),
        "gpa": profile.get("gpa", None),
        "curriculum_type": profile.get("curriculum_type", None),
        "ap_scores": json.dumps(profile.get("ap_scores", []), ensure_ascii=False),
        "ib_score": profile.get("ib_score", None),
        "alevel_scores": json.dumps(profile.get("alevel_scores", []), ensure_ascii=False),
        "activities": json.dumps(experience.get("activities", []), ensure_ascii=False),
        "research": json.dumps(experience.get("research", []), ensure_ascii=False),
        "awards": json.dumps(experience.get("awards", []), ensure_ascii=False),
        "applications": json.dumps(applications, ensure_ascii=False),
        "offer_schools": "|".join([s for s in offers if s]),
        "confidence": confidence,
        "missing_fields": json.dumps(extracted.get("missing_fields", []), ensure_ascii=False),
        "evidence_snippets": json.dumps(extracted.get("evidence_snippets", []), ensure_ascii=False),
        "notes": extracted.get("notes", None),
        "needs_review": needs_review,
        "warning": post.get("warning", ""),
    }


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    if not rows:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def main() -> None:
    args = parse_args()
    load_local_env()

    if not check_login_status():
        raise RuntimeError("Xiaohongshu MCP not logged in. Please login first.")

    suffix = safe_filename(args.keyword)
    output_raw = Path(args.output_raw_jsonl or f"data/raw/xhs_{suffix}_ai_raw.jsonl")
    output_jsonl = Path(args.output_jsonl or f"data/normalized/xhs_{suffix}_ai_cleaned.jsonl")
    output_csv = Path(args.output_csv or f"data/normalized/xhs_{suffix}_ai_cleaned.csv")
    image_dir = Path(args.image_dir)

    posts = gather_posts(
        args.keyword,
        args.limit,
        target_raw=args.target_raw,
        max_search_calls=args.max_search_calls,
        seed_jsonl=Path(args.seed_jsonl) if args.seed_jsonl else None,
        seed_link_field=args.seed_link_field,
        single_search_retries=max(0, args.single_search_retries),
        single_search_timeout_sec=max(10.0, args.single_search_timeout_sec),
        single_search_http_fallback=not args.disable_single_search_http_fallback,
        detail_timeout_sec=max(10.0, args.detail_timeout_sec),
        detail_retries=max(0, args.detail_retries),
    )

    raw_rows: list[dict[str, Any]] = []
    clean_rows: list[dict[str, Any]] = []

    for idx, post in enumerate(posts, 1):
        if idx == 1 or (args.progress_every > 0 and idx % args.progress_every == 0):
            print(f"processing idx={idx}/{len(posts)} feed_id={post.get('feed_id','')}")

        image_paths = download_images(
            post.get("image_urls", []),
            image_dir=image_dir,
            feed_id=str(post.get("feed_id", "unknown")),
            max_count=args.max_images_per_post,
        )

        try:
            extracted = call_multimodal_extractor(
                model=args.model,
                post=post,
                image_paths=image_paths,
                dry_run=args.dry_run,
                openai_timeout_sec=args.openai_timeout_sec,
                openai_retries=max(0, args.openai_retries),
            )
            error = None
        except Exception as exc:  # noqa: BLE001
            extracted = {}
            error = str(exc)

        raw_row = {
            "keyword": args.keyword,
            "feed_id": post.get("feed_id", ""),
            "source_query": post.get("source_query", args.keyword),
            "source_filter": post.get("source_filter", ""),
            "title": post.get("title", ""),
            "desc": post.get("desc", ""),
            "author": post.get("author", ""),
            "publish_time": post.get("publish_time", ""),
            "image_urls": post.get("image_urls", []),
            "local_images": [str(x) for x in image_paths],
            "extracted": extracted,
            "warning": post.get("warning", ""),
            "error": error,
        }
        raw_rows.append(raw_row)

        if error:
            continue

        clean_rows.append(
            normalize_result_row(
                keyword=args.keyword,
                post=post,
                extracted=extracted,
                image_paths=image_paths,
                confidence_threshold=args.confidence_threshold,
            )
        )

        if idx % 10 == 0:
            print(f"progress={idx}/{len(posts)} extracted={len(clean_rows)}")

    write_jsonl(output_raw, raw_rows)
    write_jsonl(output_jsonl, clean_rows)
    write_csv(output_csv, clean_rows)

    print(f"raw_saved={output_raw}")
    print(f"clean_jsonl_saved={output_jsonl}")
    print(f"clean_csv_saved={output_csv}")
    print(f"posts={len(posts)} extracted={len(clean_rows)} failed={len(posts)-len(clean_rows)}")
    print(f"needs_review={sum(1 for r in clean_rows if r.get('needs_review'))}")


if __name__ == "__main__":
    main()
