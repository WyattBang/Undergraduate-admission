#!/usr/bin/env python3
from __future__ import annotations

import argparse
import shutil
from datetime import datetime, timezone
from pathlib import Path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Archive old XHS generated data files to keep workspace tidy")
    parser.add_argument("--archive-root", default="data/archive")
    parser.add_argument("--tag", default=None, help="archive folder suffix; default uses UTC date")
    parser.add_argument("--execute", action="store_true", help="perform archive move; default is dry-run")
    return parser.parse_args()


def should_keep_raw(path: Path) -> bool:
    if path.name in {".gitkeep", "output_with_scores.jsonl"}:
        return True
    if path.name.startswith("xhs_top30_"):
        return True
    if path.is_dir() and path.name == "xhs_ai_images":
        return True
    return False


def should_keep_normalized(path: Path) -> bool:
    if path.name in {
        ".gitkeep",
        "xhs_all_merged_cleaned.jsonl",
        "xhs_all_merged_cleaned.csv",
        "xhs_current_merged_cleaned.jsonl",
        "xhs_current_merged_cleaned.csv",
    }:
        return True
    if path.name.startswith("xhs_top30_"):
        return True
    return False


def main() -> None:
    args = parse_args()
    base = Path(__file__).resolve().parents[1]
    raw_dir = base / "data" / "raw"
    norm_dir = base / "data" / "normalized"
    tag = args.tag or datetime.now(timezone.utc).strftime("%Y%m%d")
    archive_root = base / args.archive_root / f"cleanup_{tag}"
    archive_raw = archive_root / "raw"
    archive_norm = archive_root / "normalized"

    to_move: list[tuple[Path, Path]] = []

    for p in sorted(raw_dir.iterdir()):
        if should_keep_raw(p):
            continue
        if p.name.startswith("."):
            continue
        to_move.append((p, archive_raw / p.name))

    for p in sorted(norm_dir.iterdir()):
        if should_keep_normalized(p):
            continue
        if p.name.startswith("."):
            continue
        to_move.append((p, archive_norm / p.name))

    print(f"dry_run={not args.execute}")
    print(f"archive_root={archive_root}")
    print(f"move_count={len(to_move)}")
    for src, dst in to_move:
        print(f"MOVE {src} -> {dst}")

    if not args.execute:
        return

    for src, dst in to_move:
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(src), str(dst))

    print("archive_done=true")


if __name__ == "__main__":
    main()
