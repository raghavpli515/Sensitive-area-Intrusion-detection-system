"""Central application settings.

All paths are resolved relative to the repository root (not the process's
current working directory), so the backend behaves the same whether it's
started from `backend/`, the repo root, or inside Docker.
"""
from __future__ import annotations

from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

# backend/app/core/config.py -> core -> app -> backend -> <repo root>
BASE_DIR = Path(__file__).resolve().parents[3]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="IDS_",
        env_file=str(BASE_DIR / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # -- Model --
    model_path: Path = BASE_DIR / "models" / "yolov8_model.pt"
    device: str = "auto"  # "auto" | "cpu" | "cuda"
    default_confidence_threshold: float = 0.4

    # -- Storage --
    upload_dir: Path = BASE_DIR / "data" / "uploads"
    output_dir: Path = BASE_DIR / "outputs"
    max_upload_mb: int = 500  # rejects mid-stream; see utils/video_io.save_upload

    # -- API --
    cors_origins: list[str] = [
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ]

    # Single-container deploys (e.g. the Hugging Face Space) build the
    # frontend into a static bundle and point this at it; main.py mounts it
    # if set. Unset (the default) preserves the normal setup — frontend and
    # backend as separate processes/services (local dev, Docker Compose).
    frontend_dist_dir: Path | None = None

    def resolved_device(self) -> str:
        if self.device != "auto":
            return self.device
        import torch

        return "cuda" if torch.cuda.is_available() else "cpu"


settings = Settings()
settings.upload_dir.mkdir(parents=True, exist_ok=True)
settings.output_dir.mkdir(parents=True, exist_ok=True)
