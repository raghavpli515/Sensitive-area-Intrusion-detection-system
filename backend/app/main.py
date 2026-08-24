"""AI Surveillance Backend — FastAPI entrypoint.

Wires together model loading (at startup), CORS, and the API routers for
batch video inference and live WebSocket streaming.
"""
from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.health import router as health_router
from app.api.stream import router as stream_router
from app.api.video import router as video_router
from app.core import registry
from app.core.config import settings
from app.core.detector import YOLODetector


@asynccontextmanager
async def lifespan(_app: FastAPI):            # this function is called at startup and shutdown of the FastAPI app
    device = settings.resolved_device()
    detector = YOLODetector(model_path=settings.model_path, device=device)
    try:
        detector.load()
        registry.yolo_detector = detector
        print(f"[startup] YOLO model loaded from '{settings.model_path}' on '{device}'")
    except Exception as exc:  # noqa: BLE001 - startup must not crash the app on a missing model
        print(f"[startup] YOLO model NOT loaded: {exc}")
    yield
    registry.yolo_detector = None


app = FastAPI(
    title="AI Surveillance Backend",
    description="Sensitive-area intrusion detection: YOLOv8 detection, "
                "DeepSORT tracking, and rule-based alerting, served over a "
                "batch video API and a live WebSocket stream.",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(     # CORS middleware allows cross-origin requests from specified origins, which is useful for frontend applications hosted on different domains to access the backend API.
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health_router)
app.include_router(video_router)
app.include_router(stream_router)


@app.get("/")
def root():
    return {"message": "AI Surveillance Backend is running", "status": "OK"}
