#!/usr/bin/env python3
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import pandas as pd

sys.path.append(str(Path(__file__).resolve().parents[1]))

from app.constants import HOT_MAJORS, TOP30_SCHOOLS


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Report school/major coverage gaps for data collection")
    parser.add_argument("--training-csv", default="data/training/training_set.csv")
    parser.add_argument("--min-samples", type=int, default=80)
    parser.add_argument("--top", type=int, default=30)
    parser.add_argument("--out", default="data/training/gap_report.csv")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    training_csv = Path(args.training_csv)
    if not training_csv.exists():
        raise FileNotFoundError(f"training csv not found: {training_csv}")

    frame = pd.read_csv(training_csv)
    grouped = (
        frame.groupby(["target_school", "target_major"], dropna=False)
        .agg(samples=("label_admit", "count"), admit_rate=("label_admit", "mean"))
        .reset_index()
    )

    expected = pd.MultiIndex.from_product(
        [TOP30_SCHOOLS, HOT_MAJORS], names=["target_school", "target_major"]
    ).to_frame(index=False)

    merged = expected.merge(grouped, how="left", on=["target_school", "target_major"])
    merged["samples"] = merged["samples"].fillna(0).astype(int)
    merged["admit_rate"] = merged["admit_rate"].fillna(0.0)
    merged["gap_to_target"] = (args.min_samples - merged["samples"]).clip(lower=0)
    merged = merged.sort_values(["gap_to_target", "samples"], ascending=[False, True])

    merged["collection_query"] = (
        merged["target_school"]
        + " "
        + merged["target_major"]
        + " offer profile GPA TOEFL"
    )

    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    merged.to_csv(out_path, index=False)

    print(f"saved={out_path}")
    print(f"rows={len(merged)} min_samples={args.min_samples}")
    print("Top gaps:")
    preview = merged.head(args.top)[["target_school", "target_major", "samples", "gap_to_target", "collection_query"]]
    print(preview.to_string(index=False))


if __name__ == "__main__":
    main()
