#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[1]))

from app.config import settings
from app.ingestion.anonymize import anonymize_normalized_record
from app.ingestion.dedupe import dedupe_records


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Import manually curated cases from CSV into normalized layer")
    parser.add_argument("--csv", required=True, help="CSV path, see backend/data/templates/manual_cases_template.csv")
    parser.add_argument("--output", default=None, help="normalized jsonl output filename")
    return parser.parse_args()


def _parse_profile_items(raw: str) -> list[dict]:
    raw = (raw or "").strip()
    if not raw:
        return []

    items: list[dict] = []
    for chunk in raw.split(";"):
        chunk = chunk.strip()
        if not chunk:
            continue
        title, level, intensity = (chunk.split("|") + ["", "", ""])[:3]
        entry = {"title": title.strip() or "Untitled"}
        if level.strip():
            entry["level"] = level.strip()
        if intensity.strip():
            try:
                entry["intensity"] = float(intensity)
            except ValueError:
                pass
        items.append(entry)
    return items


def _parse_course_scores(raw: str) -> list[dict]:
    raw = (raw or "").strip()
    if not raw:
        return []

    courses: list[dict] = []
    for chunk in raw.split(";"):
        chunk = chunk.strip()
        if not chunk:
            continue
        name, score = (chunk.split(":") + [""])[:2]
        try:
            score_value = float(score)
        except ValueError:
            score_value = 85.0
        courses.append({"course": name.strip() or "Course", "score": score_value})
    return courses


def row_to_record(row: dict[str, str]) -> dict:
    season = int(row.get("season", row.get("grad_year", 2025) or 2025))
    grad_year = int(row.get("grad_year", season) or season)

    record = {
        "source": row.get("source", "manual").strip() or "manual",
        "collected_at": datetime.now(timezone.utc).isoformat(),
        "post_hash": f"manual-{hash(json.dumps(row, ensure_ascii=False))}",
        "applicant": {
            "english_test_type": (row.get("english_test_type", "TOEFL") or "TOEFL").strip(),
            "english_score": float(row.get("english_score", 95) or 95),
            "gpa": float(row.get("gpa", 3.7) or 3.7),
            "curriculum_type": (row.get("curriculum_type", "Other") or "Other").strip(),
            "course_scores": _parse_course_scores(row.get("course_scores", "")),
            "activities": _parse_profile_items(row.get("activities", "")),
            "awards": _parse_profile_items(row.get("awards", "")),
            "research": _parse_profile_items(row.get("research", "")),
            "grad_year": grad_year,
        },
        "applications": [
            {
                "school": row.get("school", "").strip(),
                "major": row.get("major", "CS").strip() or "CS",
                "result": (row.get("result", "reject") or "reject").strip().lower(),
                "season": season,
            }
        ],
    }
    return anonymize_normalized_record(record)


def main() -> None:
    args = parse_args()
    csv_path = Path(args.csv)
    if not csv_path.exists():
        raise FileNotFoundError(csv_path)

    with csv_path.open("r", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))

    records = [row_to_record(row) for row in rows if row.get("school") and row.get("result")]
    unique_records, duplicates = dedupe_records(records)

    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")
    output = settings.normalized_dir / (args.output or f"manual_import_{timestamp}.jsonl")
    output.parent.mkdir(parents=True, exist_ok=True)

    with output.open("w", encoding="utf-8") as handle:
        for row in unique_records:
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")

    print(f"input_rows={len(rows)} imported={len(unique_records)} duplicates={duplicates} output={output}")


if __name__ == "__main__":
    main()
