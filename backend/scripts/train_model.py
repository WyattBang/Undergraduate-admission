#!/usr/bin/env python3
from __future__ import annotations

import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[1]))

from app.config import settings
from app.pipeline.train import train_and_save


def main() -> None:
    training_csv = settings.training_dir / "training_set.csv"
    if not training_csv.exists():
        raise FileNotFoundError(f"training set missing at {training_csv}")

    metrics = train_and_save(training_csv, settings.model_dir / "admit_model.joblib")
    print(metrics)


if __name__ == "__main__":
    main()
