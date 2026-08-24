"""Split a folder of hard-negative images (frames with no target objects,
used to teach the detector what *not* to fire on) into train/val, each
paired with an empty YOLO label file.

Usage:
    python scripts/prepare_hard_negatives.py \\
        --source data/Hard_negative_images \\
        --dataset-dir data/ids_finetune_v1
"""
from __future__ import annotations

import argparse
import random
import shutil
from pathlib import Path

SUPPORTED_EXTS = {".jpg", ".jpeg", ".png"}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", default="data/Hard_negative_images")
    parser.add_argument("--dataset-dir", default="data/ids_finetune_v1")
    parser.add_argument("--train-ratio", type=float, default=0.8)
    parser.add_argument("--seed", type=int, default=42)
    return parser.parse_args()


def copy_with_empty_label(img_name: str, source_dir: Path, img_dst: Path, label_dst: Path) -> None:
    shutil.copy2(source_dir / img_name, img_dst / img_name)
    label_path = label_dst / f"{Path(img_name).stem}.txt"
    if not label_path.exists():
        label_path.touch()


def main() -> None:
    args = parse_args()
    random.seed(args.seed)

    source_dir = Path(args.source)
    dataset_dir = Path(args.dataset_dir)
    train_img_dir = dataset_dir / "train" / "images"
    train_label_dir = dataset_dir / "train" / "labels"
    val_img_dir = dataset_dir / "val" / "images"
    val_label_dir = dataset_dir / "val" / "labels"

    for directory in (train_img_dir, train_label_dir, val_img_dir, val_label_dir):
        directory.mkdir(parents=True, exist_ok=True)

    images = [f.name for f in source_dir.iterdir() if f.suffix.lower() in SUPPORTED_EXTS]
    random.shuffle(images)

    split_at = int(len(images) * args.train_ratio)
    train_images, val_images = images[:split_at], images[split_at:]

    print(f"Total images       : {len(images)}")
    print(f"Train images ({args.train_ratio:.0%}) : {len(train_images)}")
    print(f"Val images ({1 - args.train_ratio:.0%})   : {len(val_images)}")

    for name in train_images:
        copy_with_empty_label(name, source_dir, train_img_dir, train_label_dir)
    for name in val_images:
        copy_with_empty_label(name, source_dir, val_img_dir, val_label_dir)

    print("Hard-negative images distributed and empty labels created.")


if __name__ == "__main__":
    main()
