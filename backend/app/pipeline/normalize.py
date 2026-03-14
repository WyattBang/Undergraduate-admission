from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from app.config import settings
from app.ingestion.anonymize import anonymize_normalized_record, anonymize_raw_record
from app.ingestion.dedupe import dedupe_records
from app.ingestion.extract import normalize_raw_post


@dataclass
class NormalizeSummary:
    total_raw: int
    parsed: int
    deduped: int
    duplicates: int


def _read_jsonl(path: Path) -> list[dict]:
    rows = []
    if not path.exists():
        return rows
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            rows.append(json.loads(line))
    return rows


def _write_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")


def normalize_raw_file(raw_file: Path, normalized_file: Path) -> NormalizeSummary:
    raw_rows = _read_jsonl(raw_file)
    parsed_records: list[dict] = []

    for row in raw_rows:
        anonymized_raw = anonymize_raw_record(row)
        normalized = normalize_raw_post(anonymized_raw)
        if not normalized:
            continue
        parsed_records.append(anonymize_normalized_record(normalized))

    unique_records, duplicates = dedupe_records(parsed_records)
    _write_jsonl(normalized_file, unique_records)

    return NormalizeSummary(
        total_raw=len(raw_rows),
        parsed=len(parsed_records),
        deduped=len(unique_records),
        duplicates=duplicates,
    )


def evaluate_label_quality(
    machine_labels: list[str],
    manual_labels: list[str],
    pass_threshold: float = 0.85,
) -> tuple[bool, float]:
    if not machine_labels or not manual_labels:
        return False, 0.0

    n = min(len(machine_labels), len(manual_labels))
    matched = sum(
        1
        for idx in range(n)
        if machine_labels[idx].strip().lower() == manual_labels[idx].strip().lower()
    )
    precision = matched / float(n)
    return precision >= pass_threshold, precision


def normalize_latest_batch() -> NormalizeSummary:
    candidates = sorted(settings.raw_dir.glob("*.jsonl"))
    if not candidates:
        raise FileNotFoundError("No raw batches found under backend/data/raw")

    latest = candidates[-1]
    normalized_path = settings.normalized_dir / latest.name
    return normalize_raw_file(latest, normalized_path)
