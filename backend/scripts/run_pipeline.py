#!/usr/bin/env python3
from __future__ import annotations

import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[1]))

from app.pipeline.normalize import normalize_latest_batch
from app.pipeline.train import train_latest_training_set
from app.pipeline.training_set import build_latest_training_set


def main() -> None:
    normalize_summary = normalize_latest_batch()
    print(
        "normalize_summary",
        {
            "total_raw": normalize_summary.total_raw,
            "parsed": normalize_summary.parsed,
            "deduped": normalize_summary.deduped,
            "duplicates": normalize_summary.duplicates,
        },
    )

    training_path = build_latest_training_set()
    print("training_set", training_path)

    metrics = train_latest_training_set()
    print("train_metrics", metrics)


if __name__ == "__main__":
    main()
