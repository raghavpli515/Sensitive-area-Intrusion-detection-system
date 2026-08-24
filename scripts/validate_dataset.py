"""Sanity-check a YOLO-format dataset split: every image should have a
matching label file and vice versa. Run before kicking off a training run —
catches silently-mismatched pairs that would otherwise just get skipped or
under-supervised by Ultralytics.

Usage:
    python scripts/validate_dataset.py --dataset-dir data/ids_finetune_v1
    python scripts/validate_dataset.py --dataset-dir data/ids_finetune_v1 --split train
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset-dir", default="data/ids_finetune_v1")
    parser.add_argument(
        "--split", choices=["train", "val", "test", "all"], default="all",
    )
    return parser.parse_args()


def check_split(dataset_dir: Path, split: str) -> bool:
    img_dir = dataset_dir / split / "images"
    label_dir = dataset_dir / split / "labels"

    if not img_dir.exists() or not label_dir.exists():
        print(f"[{split}] skipped — {img_dir} or {label_dir} does not exist")
        return True

    images = {p.stem for p in img_dir.iterdir() if p.is_file()}
    labels = {p.stem for p in label_dir.iterdir() if p.suffix == ".txt"}

    missing_labels = sorted(images - labels)
    extra_labels = sorted(labels - images)

    print(f"[{split}] images={len(images)} labels={len(labels)} "
          f"missing_labels={len(missing_labels)} extra_labels={len(extra_labels)}")

    for name in missing_labels[:10]:
        print(f"  missing label for image: {name}")
    for name in extra_labels[:10]:
        print(f"  label with no image: {name}")

    return not missing_labels and not extra_labels


def main() -> None:
    args = parse_args()
    dataset_dir = Path(args.dataset_dir)
    splits = ["train", "val", "test"] if args.split == "all" else [args.split]

    ok = all(check_split(dataset_dir, split) for split in splits)
    if not ok:
        sys.exit(1)
    print("Dataset OK: every image has a matching label and vice versa.")


if __name__ == "__main__":
    main()
