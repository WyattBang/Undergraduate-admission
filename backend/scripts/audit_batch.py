#!/usr/bin/env python3
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[1]))

from app.pipeline.quality_gate import audit_and_rollback


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Manual spot-check quality gate for labels")
    parser.add_argument("--normalized-file", required=True)
    parser.add_argument("--audit-csv", required=True, help="CSV with a 'label' column")
    parser.add_argument("--threshold", type=float, default=0.85)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    passed, precision, rejected = audit_and_rollback(
        normalized_file=Path(args.normalized_file),
        audit_csv=Path(args.audit_csv),
        threshold=args.threshold,
    )

    if passed:
        print(f"PASS precision={precision:.4f}")
    else:
        print(f"FAIL precision={precision:.4f} rolled_back_to={rejected}")


if __name__ == "__main__":
    main()
