"""Thin wrapper around an Ultralytics YOLO model.

Kept deliberately small: this class only knows how to load weights and run
inference on a single frame. Tracking and rule logic live elsewhere so each
piece can be tested/swapped independently.
"""
from __future__ import annotations

from pathlib import Path

import torch
from ultralytics import YOLO


class YOLODetector:
    def __init__(self, model_path: str | Path, device: str | None = None):
        self.model_path = Path(model_path)
        self.device = device or ("cuda" if torch.cuda.is_available() else "cpu")
        self.model: YOLO | None = None

    def load(self) -> None:
        """Load weights from disk. Safe to call more than once (no-op after the first)."""
        if self.model is not None:
            return
        if not self.model_path.exists():
            raise FileNotFoundError(
                f"YOLO model weights not found at '{self.model_path}'. "
                "Run `dvc pull` or place the weights there manually."
            )
        self.model = YOLO(str(self.model_path))
        self.model.to(self.device)

    @property
    def class_names(self) -> dict[int, str]:
        self._ensure_loaded()
        return self.model.names

    def detect(self, frame, confidence_threshold: float = 0.25):
        """Run inference on a single BGR frame and return the raw Ultralytics result."""
        self._ensure_loaded()
        return self.model(frame, conf=confidence_threshold, verbose=False)[0]

    def _ensure_loaded(self) -> None:
        if self.model is None:
            raise RuntimeError("Model not loaded. Call load() first.")
