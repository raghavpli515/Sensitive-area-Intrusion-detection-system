"""API-facing data shapes. Kept separate from the internal core/ logic so the
wire format can evolve independently of the detection/tracking internals."""
from __future__ import annotations

from pydantic import BaseModel


class Detection(BaseModel):
    track_id: int
    class_name: str
    confidence: float
    bbox: list[int]  # [x1, y1, x2, y2]


class Alert(BaseModel):
    frame: int
    type: str
    message: str
    track_id: int | None = None
    # "started": a condition (e.g. zone intrusion) just began.
    # "ended": it just stopped — either the condition cleared, the track
    # was lost, or processing ended while it was still active.
    # One-off events (line_breach) are always "started" with no matching
    # "ended", since there's no sustained state to close.
    event: str = "started"
    duration_seconds: float | None = None  # set only on "ended" events


class JobStatus(BaseModel):
    job_id: str
    status: str  # queued | running | done | error
    progress: float = 0.0
    error: str | None = None
    total_frames: int | None = None
    processed_frames: int = 0
    alerts: list[Alert] = []
    output_video_url: str | None = None


class StreamFrameResult(BaseModel):
    frame: int
    image_b64: str
    detections: list[Detection]
    alerts: list[Alert]
