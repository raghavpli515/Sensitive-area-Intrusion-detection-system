"""Process-wide handle to the loaded model.

A plain module-level variable avoids circular imports between `main.py`
(which loads the model at startup) and the API routers (which need to reach
it on every request/connection) without needing a DI framework for a
single-model service.
"""
from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.core.detector import YOLODetector

yolo_detector: YOLODetector | None = None
