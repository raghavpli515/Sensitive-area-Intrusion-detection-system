"""Fine-tune the IDS detector on the 4-class dataset (Person, Drone, Weapon,
Vehicle). Parameterized version of the run that actually produced the
shipped model (`models/yolov8_model.pt`, ex `experiments/ids_finetune_v13_safe`).

Usage:
    python scripts/train.py --data data/ids_finetune_v1/data.yaml
    python scripts/train.py --resume-from experiments/ids_finetune_v13_safe/weights/last.pt
"""
from __future__ import annotations

import argparse
import multiprocessing as mp

import torch
from ultralytics import YOLO


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data", default="data/ids_finetune_v1/data.yaml")
    parser.add_argument(
        "--weights", default="yolov8n.pt",
        help="Starting weights: a base checkpoint, or the same path as --resume-from to continue a run.",
    )
    parser.add_argument("--resume-from", default=None, help="Checkpoint to resume an interrupted run from.")
    parser.add_argument("--epochs", type=int, default=50)
    parser.add_argument("--imgsz", type=int, default=1024)
    parser.add_argument("--batch", type=int, default=8)
    parser.add_argument("--device", default="0", help="'0' for first GPU, 'cpu' for CPU-only.")
    parser.add_argument("--workers", type=int, default=2)
    parser.add_argument("--patience", type=int, default=7)
    parser.add_argument("--project", default="experiments")
    parser.add_argument("--name", default="ids_finetune")
    return parser.parse_args()


def main() -> None:
    args = parse_args()

    print("Torch:", torch.__version__)
    print("CUDA available:", torch.cuda.is_available())
    if torch.cuda.is_available():
        print("GPU:", torch.cuda.get_device_name(0))

    model = YOLO(args.resume_from or args.weights)

    model.train(
        data=args.data,
        resume=bool(args.resume_from),
        epochs=args.epochs,
        imgsz=args.imgsz,
        batch=args.batch,
        device=args.device,
        workers=args.workers,
        # Optimizer — AdamW with a low LR worked best for fine-tuning from a
        # pretrained checkpoint rather than training from scratch.
        optimizer="AdamW",
        lr0=1e-4,
        lrf=0.01,
        weight_decay=0.01,
        # Strategy
        freeze=0,
        patience=args.patience,
        multi_scale=True,
        close_mosaic=7,  # avoids a late-training memory spike on this dataset
        # Augmentation tuned for weapon / night / long-distance surveillance footage
        hsv_h=0.015,
        hsv_s=0.7,
        hsv_v=0.4,
        scale=0.5,
        translate=0.1,
        fliplr=0.5,
        mosaic=0.8,
        mixup=0.1,
        copy_paste=0.05,
        # Logging
        project=args.project,
        name=args.name,
        save=True,
        save_period=5,
        verbose=True,
        val=True,
        plots=True,
    )


if __name__ == "__main__":
    mp.freeze_support()
    main()
