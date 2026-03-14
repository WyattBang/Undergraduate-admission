from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path

import pandas as pd

from app.pipeline.normalize import evaluate_label_quality


def _machine_labels_from_normalized(normalized_file: Path) -> list[str]:
    labels: list[str] = []
    for line in normalized_file.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        row = json.loads(line)
        applications = row.get("applications", [])
        if not applications:
            continue
        labels.append(str(applications[0].get("result", "")).lower())
    return labels


def _manual_labels_from_csv(audit_csv: Path) -> list[str]:
    frame = pd.read_csv(audit_csv)
    if "label" not in frame.columns:
        raise ValueError("audit csv must contain a 'label' column")
    return [str(value).lower() for value in frame["label"].tolist()]


def audit_and_rollback(
    normalized_file: Path,
    audit_csv: Path,
    threshold: float = 0.85,
) -> tuple[bool, float, Path | None]:
    machine_labels = _machine_labels_from_normalized(normalized_file)
    manual_labels = _manual_labels_from_csv(audit_csv)

    passed, precision = evaluate_label_quality(
        machine_labels=machine_labels,
        manual_labels=manual_labels,
        pass_threshold=threshold,
    )

    if passed:
        return True, precision, None

    rejected = normalized_file.with_suffix(
        f".rejected.{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}.jsonl"
    )
    normalized_file.rename(rejected)
    return False, precision, rejected
