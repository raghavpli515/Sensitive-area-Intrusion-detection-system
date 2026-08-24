"""Live detection over a WebSocket: the browser sends JPEG-encoded webcam
frames, the backend runs the same detect -> track -> rules pipeline used for
batch video and streams back an annotated frame + alerts per message.

One `ObjectTracker` + `RuleEngine` is created per connection and lives for
its whole lifetime, so track history (and therefore speed/zone/line/stationary
rules) persists correctly across frames. 
"""
from __future__ import annotations

import base64

import cv2
import numpy as np
from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from app.core import registry
from app.core.config import settings
from app.core.rules import RuleEngine
from app.core.tracker import ObjectTracker
from app.services.pipeline import process_frame

router = APIRouter(tags=["Live Stream"])


@router.websocket("/ws/stream")
async def stream_endpoint(websocket: WebSocket):
    await websocket.accept()

    detector = registry.yolo_detector
    if detector is None:
        await websocket.send_json({"error": "Model not loaded on the server"})
        await websocket.close(code=1011)
        return

    tracker = ObjectTracker()
    rule_engine = RuleEngine()
    frame_id = 0

    try:
        while True:
            payload = await websocket.receive_bytes()
            buffer = np.frombuffer(payload, dtype=np.uint8)
            frame = cv2.imdecode(buffer, cv2.IMREAD_COLOR)
            if frame is None:
                await websocket.send_json({"error": "Could not decode frame", "frame": frame_id})
                continue

            annotated, detections, alerts = process_frame(
                frame, detector, tracker, rule_engine, frame_id,
                confidence_threshold=settings.default_confidence_threshold,
            )

            ok, jpeg = cv2.imencode(".jpg", annotated)
            frame_id += 1
            if not ok:
                continue

            await websocket.send_json({
                "frame": frame_id,
                "image_b64": base64.b64encode(jpeg).decode("ascii"),
                "detections": [d.model_dump() for d in detections],
                "alerts": [a.model_dump() for a in alerts],
            })
    except WebSocketDisconnect:
        pass
