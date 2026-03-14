#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


DEFAULT_TOP30_SCHOOLS = [
    "Harvard",
    "Stanford",
    "MIT",
    "Yale",
    "Princeton",
    "Columbia",
    "UChicago",
    "UPenn",
    "Caltech",
    "Duke",
    "Northwestern",
    "Johns Hopkins",
    "Brown",
    "Cornell",
    "Dartmouth",
    "Vanderbilt",
    "Rice",
    "Notre Dame",
    "UCLA",
    "UC Berkeley",
    "University of Michigan",
    "Carnegie Mellon",
    "Emory",
    "Georgetown",
    "University of Virginia",
    "UNC Chapel Hill",
    "USC",
    "NYU",
    "Tufts",
    "Wake Forest",
]

TOP30_ZH_NAMES = {
    "Harvard": "哈佛",
    "Stanford": "斯坦福",
    "MIT": "麻省理工",
    "Yale": "耶鲁",
    "Princeton": "普林斯顿",
    "Columbia": "哥伦比亚",
    "UChicago": "芝加哥大学",
    "UPenn": "宾夕法尼亚大学",
    "Caltech": "加州理工",
    "Duke": "杜克",
    "Northwestern": "西北大学",
    "Johns Hopkins": "约翰霍普金斯",
    "Brown": "布朗",
    "Cornell": "康奈尔",
    "Dartmouth": "达特茅斯",
    "Vanderbilt": "范德堡",
    "Rice": "莱斯",
    "Notre Dame": "圣母大学",
    "UCLA": "加州大学洛杉矶",
    "UC Berkeley": "加州大学伯克利",
    "University of Michigan": "密歇根大学安娜堡",
    "Carnegie Mellon": "卡内基梅隆",
    "Emory": "埃默里",
    "Georgetown": "乔治城",
    "University of Virginia": "弗吉尼亚大学",
    "UNC Chapel Hill": "北卡教堂山",
    "USC": "南加州大学",
    "NYU": "纽约大学",
    "Tufts": "塔夫茨",
    "Wake Forest": "维克森林",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run school-specific source queries and merge cleaned outputs")
    parser.add_argument("--top-n", type=int, default=30)
    parser.add_argument("--limit-per-query", type=int, default=6)
    parser.add_argument("--target-raw-per-query", type=int, default=0)
    parser.add_argument("--max-search-calls-per-query", type=int, default=24)
    parser.add_argument("--max-images-per-post", type=int, default=1)
    parser.add_argument("--model", default="gpt-4.1-mini")
    parser.add_argument("--openai-timeout-sec", type=float, default=45.0)
    parser.add_argument("--openai-retries", type=int, default=1)
    parser.add_argument("--single-search-retries", type=int, default=2)
    parser.add_argument("--single-search-timeout-sec", type=float, default=90.0)
    parser.add_argument("--query-retries", type=int, default=1)
    parser.add_argument("--stream-child-output", action="store_true")
    parser.add_argument("--query-suffix", default="录取背景 美本")
    parser.add_argument("--school-name-variant", choices=["en", "zh", "both"], default="en")
    parser.add_argument("--output-prefix", default="xhs_top30")
    parser.add_argument("--raw-dir", default="data/raw")
    parser.add_argument("--normalized-dir", default="data/normalized")
    parser.add_argument("--dry-run", action="store_true")
    return parser.parse_args()


def safe_filename(raw: str) -> str:
    out = []
    for ch in raw:
        if ch.isascii() and (ch.isalnum() or ch in ("_", "-")):
            out.append(ch)
        else:
            out.append("_")
    text = "".join(out).strip("_")
    digest = hashlib.md5(raw.encode("utf-8")).hexdigest()[:8]
    base = text[:90] if text else "query"
    return f"{base}_{digest}"


def build_queries(top_n: int, suffix: str, school_name_variant: str) -> list[str]:
    schools = DEFAULT_TOP30_SCHOOLS[: max(1, min(top_n, len(DEFAULT_TOP30_SCHOOLS)))]
    queries: list[str] = []
    for s in schools:
        if school_name_variant in ("en", "both"):
            queries.append(f"{s} {suffix}".strip())
        if school_name_variant in ("zh", "both"):
            zh = TOP30_ZH_NAMES.get(s, "")
            if zh:
                queries.append(f"{zh} {suffix}".strip())
    if school_name_variant in ("en", "both") and any("UC Berkeley" in q for q in queries):
        queries.append(f"ucberkley {suffix}".strip())
    return queries


def merge_clean_files(paths: list[Path], out_jsonl: Path, out_csv: Path) -> dict[str, Any]:
    rows: list[dict[str, Any]] = []
    for path in paths:
        if not path.exists():
            continue
        rows.extend(json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip())

    seen_feed_ids: set[str] = set()
    merged: list[dict[str, Any]] = []
    for row in rows:
        feed_id = str(row.get("feed_id", "")).strip()
        if not feed_id:
            continue
        if feed_id in seen_feed_ids:
            continue
        seen_feed_ids.add(feed_id)
        merged.append(row)

    out_jsonl.parent.mkdir(parents=True, exist_ok=True)
    out_jsonl.write_text("\n".join(json.dumps(r, ensure_ascii=False) for r in merged) + ("\n" if merged else ""), encoding="utf-8")
    if merged:
        with out_csv.open("w", encoding="utf-8", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=list(merged[0].keys()))
            writer.writeheader()
            writer.writerows(merged)

    needs_review = sum(1 for r in merged if r.get("needs_review"))
    return {
        "rows": len(merged),
        "needs_review": needs_review,
        "review_rate": round(needs_review / len(merged), 4) if merged else 0.0,
    }


def main() -> None:
    args = parse_args()
    base_dir = Path(__file__).resolve().parents[1]
    extractor = base_dir / "scripts" / "xhs_ai_extract_to_table.py"
    raw_dir = base_dir / args.raw_dir
    normalized_dir = base_dir / args.normalized_dir
    raw_dir.mkdir(parents=True, exist_ok=True)
    normalized_dir.mkdir(parents=True, exist_ok=True)

    queries = build_queries(args.top_n, args.query_suffix, args.school_name_variant)
    cleaned_files: list[Path] = []
    manifest: list[dict[str, Any]] = []

    for idx, query in enumerate(queries, 1):
        suffix = safe_filename(query)
        raw_path = raw_dir / f"{args.output_prefix}_{suffix}_raw.jsonl"
        jsonl_path = normalized_dir / f"{args.output_prefix}_{suffix}_cleaned.jsonl"
        csv_path = normalized_dir / f"{args.output_prefix}_{suffix}_cleaned.csv"

        cmd = [
            sys.executable,
            str(extractor),
            "--keyword",
            query,
            "--limit",
            str(args.limit_per_query),
            "--max-images-per-post",
            str(args.max_images_per_post),
            "--model",
            args.model,
            "--openai-timeout-sec",
            str(args.openai_timeout_sec),
            "--openai-retries",
            str(args.openai_retries),
            "--single-search-retries",
            str(args.single_search_retries),
            "--single-search-timeout-sec",
            str(args.single_search_timeout_sec),
            "--output-raw-jsonl",
            str(raw_path.relative_to(base_dir)),
            "--output-jsonl",
            str(jsonl_path.relative_to(base_dir)),
            "--output-csv",
            str(csv_path.relative_to(base_dir)),
        ]
        if args.target_raw_per_query > 0:
            cmd.extend(
                [
                    "--target-raw",
                    str(args.target_raw_per_query),
                    "--max-search-calls",
                    str(args.max_search_calls_per_query),
                ]
            )
        if args.dry_run:
            cmd.append("--dry-run")

        print(f"[{idx}/{len(queries)}] running query={query}")
        result = None
        attempts = max(0, args.query_retries) + 1
        for attempt in range(1, attempts + 1):
            result = subprocess.run(
                cmd,
                cwd=base_dir,
                text=True,
                capture_output=not args.stream_child_output,
            )
            if result.returncode == 0:
                break
            print(f"[{idx}/{len(queries)}] retry={attempt}/{attempts} failed query={query}")

        row = {
            "query": query,
            "raw_path": str(raw_path),
            "jsonl_path": str(jsonl_path),
            "csv_path": str(csv_path),
            "ok": result.returncode == 0,
            "returncode": result.returncode,
            "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        }
        if result.returncode != 0:
            row["stderr_tail"] = "\n".join(result.stderr.splitlines()[-30:])
            row["stdout_tail"] = "\n".join(result.stdout.splitlines()[-30:])
            print(f"[{idx}/{len(queries)}] failed query={query}")
        else:
            cleaned_files.append(jsonl_path)
            print(f"[{idx}/{len(queries)}] success query={query}")
        manifest.append(row)

    merged_jsonl = normalized_dir / f"{args.output_prefix}_merged_cleaned.jsonl"
    merged_csv = normalized_dir / f"{args.output_prefix}_merged_cleaned.csv"
    summary = merge_clean_files(cleaned_files, merged_jsonl, merged_csv)

    manifest_path = normalized_dir / f"{args.output_prefix}_run_manifest.json"
    manifest_path.write_text(
        json.dumps(
            {
                "generated_at_utc": datetime.now(timezone.utc).isoformat(),
                "query_count": len(queries),
                "success_count": sum(1 for r in manifest if r["ok"]),
                "fail_count": sum(1 for r in manifest if not r["ok"]),
                "summary": summary,
                "runs": manifest,
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    print(f"manifest={manifest_path}")
    print(f"merged_jsonl={merged_jsonl}")
    print(f"merged_csv={merged_csv}")
    print(f"merged_rows={summary['rows']}")
    print(f"needs_review={summary['needs_review']}")


if __name__ == "__main__":
    main()
