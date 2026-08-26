"""Single shared frame-processing pipeline: detect -> track -> apply rules.

Both the batch video-upload path (`api/video.py`) and the live WebSocket path
(`api/stream.py`) call `process_frame` for every frame. 
"""
from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import cv2

from app.core.detector import YOLODetector
from app.core.rules import RuleEngine
from app.core.tracker import ObjectTracker
from app.schemas.detection import Alert, Detection

_BOX_COLOR = (0, 255, 0)


def process_frame(
    frame,
    detector: YOLODetector,
    tracker: ObjectTracker,
    rule_engine: RuleEngine,
    frame_id: int,
    confidence_threshold: float = 0.4,
    draw: bool = True,
) -> tuple[object, list[Detection], list[Alert]]:
    """Run one frame through the full pipeline. Mutates `frame` in place when
    `draw=True` and also returns it, so callers can chain calls easily."""
    height, width = frame.shape[:2]
    results = detector.detect(frame, confidence_threshold)

    yolo_dets = []
    for box in results.boxes:
        conf = float(box.conf[0])
        x1, y1, x2, y2 = map(int, box.xyxy[0])
        cls_id = int(box.cls[0])
        cls_name = results.names[cls_id]
        yolo_dets.append(([x1, y1, x2 - x1, y2 - y1], conf, cls_name))

    tracks = tracker.update(yolo_dets, frame)

    detections: list[Detection] = []
    for track in tracks:
        if not track.is_confirmed():
            continue

        bx1, by1, bx2, by2 = map(int, track.to_ltrb())
        cls_name = track.get_det_class() or "unknown"
        conf = track.get_det_conf() or 0.0

        detections.append(Detection(
            track_id=int(track.track_id),
            class_name=cls_name,
            confidence=round(float(conf), 3),
            bbox=[bx1, by1, bx2, by2],
        ))

        if draw:
            cv2.rectangle(frame, (bx1, by1), (bx2, by2), _BOX_COLOR, 2)
            cv2.putText(
                frame, f"{cls_name} #{track.track_id}", (bx1, max(by1 - 8, 0)),
                cv2.FONT_HERSHEY_SIMPLEX, 0.55, _BOX_COLOR, 2,
            )

    alerts = rule_engine.process_frame(frame_id, detections, width, height)
    return frame, detections, alerts


def run_video_job(job, input_path: Path, output_path: Path, confidence_threshold: float) -> None:
    """Process an entire video file for a background job, updating `job` in
    place as frames complete so `GET /infer/video/{id}` can report progress."""
    from app.core import registry  # deferred: avoids a circular import at module load

    detector = registry.yolo_detector
    if detector is None:
        raise RuntimeError("Detector not initialized — model failed to load at startup")

    tracker = ObjectTracker()

    cap = cv2.VideoCapture(str(input_path))
    if not cap.isOpened():
        raise ValueError(f"Cannot open video: {input_path}")

    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    fps = cap.get(cv2.CAP_PROP_FPS) or 25.0
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    # Real fps from the source video, so alert cooldowns are wall-clock
    # accurate (e.g. "at most one zone_intrusion alert per 2 seconds")
    # rather than an arbitrary frame count.
    rule_engine = RuleEngine(fps=fps)
    job.total_frames = total_frames

    output_path.parent.mkdir(parents=True, exist_ok=True)
    # OpenCV's own encoder writes here first; see _transcode_to_browser_compatible_mp4
    # for why this can't be the file we actually serve.
    raw_path = output_path.with_suffix(".raw.mp4")
    writer = cv2.VideoWriter(str(raw_path), cv2.VideoWriter_fourcc(*"mp4v"), fps, (width, height))
    if not writer.isOpened():
        cap.release()
        raise RuntimeError(
            f"Could not open a video writer for '{raw_path}' — the OpenCV build "
            "on this machine may be missing codec support."
        )

    frame_id = 0
    try:
        while True:
            ok, frame = cap.read()
            if not ok:
                break

            annotated, _detections, alerts = process_frame(
                frame, detector, tracker, rule_engine, frame_id, confidence_threshold,
            )
            writer.write(annotated)
            job.alerts.extend(alerts)

            frame_id += 1
            job.processed_frames = frame_id
            if total_frames:
                job.progress = min(frame_id / total_frames, 0.99)
    finally:
        cap.release()
        writer.release()

    _transcode_to_browser_compatible_mp4(raw_path, output_path)
    raw_path.unlink(missing_ok=True)
    job.output_path = output_path


def _transcode_to_browser_compatible_mp4(raw_path: Path, output_path: Path) -> None:
    """Re-encode to real H.264.

    `cv2.VideoWriter_fourcc(*"mp4v")` writes MPEG-4 Part 2 (fourcc 'mp4v') —
    a valid, playable video file, but not one Chrome/Firefox/Safari's native
    <video> element will decode; browsers only play H.264/AVC, VP8/9, or AV1
    inside an mp4/webm container. Without this step the job completes and the
    file downloads fine, but the frontend's <video> tag silently shows
    nothing — the bug this function fixes.
    """
    if shutil.which("ffmpeg") is None:
        raise RuntimeError(
            "ffmpeg is required to produce a browser-playable video but was not "
            "found on PATH. Install it (the backend Docker image already does; "
            "for local dev install ffmpeg and ensure it's on PATH)."
        )

    result = subprocess.run(
        [
            "ffmpeg", "-y", "-loglevel", "error",
            "-i", str(raw_path),
            "-vcodec", "libx264", "-pix_fmt", "yuv420p", "-movflags", "+faststart",
            str(output_path),
        ],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0 or not output_path.exists():
        raise RuntimeError(f"ffmpeg transcode to H.264 failed: {result.stderr.strip()[:500]}")
