from __future__ import annotations

import hashlib
from datetime import datetime


def _safe_parse_dt(value: str | None) -> datetime:
    if not value:
        return datetime(1970, 1, 1)
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except Exception:  # noqa: BLE001
        return datetime(1970, 1, 1)


def fingerprint(record: dict) -> str:
    applicant = record.get("applicant", {})
    applications = record.get("applications", [])

    english = applicant.get("english_score", "")
    gpa = applicant.get("gpa", "")
    curriculum = applicant.get("curriculum_type", "")
    grad_year = applicant.get("grad_year", "")
    activities = applicant.get("activities", [])

    activity_titles = ",".join(
        sorted(item.get("title", "").strip().lower() for item in activities)[:5]
    )

    app_signature = ",".join(
        sorted(
            f"{x.get('school','')}|{x.get('major','')}|{x.get('result','')}|{x.get('season','')}"
            for x in applications
        )
    )

    collected = _safe_parse_dt(record.get("collected_at"))
    quarter = (collected.month - 1) // 3 + 1

    raw = f"{english}|{gpa}|{curriculum}|{grad_year}|{activity_titles}|{app_signature}|Q{quarter}-{collected.year}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def dedupe_records(records: list[dict]) -> tuple[list[dict], int]:
    seen: set[str] = set()
    unique: list[dict] = []
    duplicates = 0

    for record in records:
        key = fingerprint(record)
        if key in seen:
            duplicates += 1
            continue
        seen.add(key)
        unique.append(record)

    return unique, duplicates
