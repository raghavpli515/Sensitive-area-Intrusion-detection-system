"""API contract tests.

These run without a real model: pointing IDS_MODEL_PATH at a path that
doesn't exist makes startup log a warning and leave `registry.yolo_detector`
as `None` (see `app.main.lifespan`'s try/except), so the endpoint-shape and
validation tests below stay fast and hermetic. A real end-to-end inference
smoke test (using the actual DVC-tracked weights) is documented in
docs/ARCHITECTURE.md as a manual verification step instead of an automated
test, since it needs the ~100MB model file and is too slow for routine CI.
"""
from __future__ import annotations

import io
import os

import pytest

os.environ.setdefault("IDS_MODEL_PATH", "__no_such_model__.pt")

from fastapi.testclient import TestClient  # noqa: E402

from app.core.config import settings  # noqa: E402
from app.main import app  # noqa: E402


@pytest.fixture
def client():
    with TestClient(app) as test_client:
        yield test_client


def test_root_reports_running(client):
    resp = client.get("/")
    assert resp.status_code == 200
    assert resp.json()["status"] == "OK"


def test_health_reports_model_not_loaded(client):
    resp = client.get("/health/")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "healthy"
    assert body["model_loaded"] is False


def test_video_upload_rejects_unsupported_extension(client):
    resp = client.post(
        "/infer/video",
        files={"file": ("not_a_video.txt", io.BytesIO(b"hello"), "text/plain")},
    )
    assert resp.status_code == 400


def test_video_upload_rejects_file_over_the_configured_limit(client, monkeypatch, tmp_path):
    monkeypatch.setattr(settings, "max_upload_mb", 0)
    # Redirect uploads to a scratch dir so this test can't leave a stray
    # partial file behind in the real data/uploads/.
    monkeypatch.setattr(settings, "upload_dir", tmp_path)

    resp = client.post(
        "/infer/video",
        files={"file": ("clip.mp4", io.BytesIO(b"x" * 2048), "video/mp4")},
    )

    assert resp.status_code == 413
    assert list(tmp_path.iterdir()) == []  # partial upload must not be left on disk


def test_job_status_404_for_unknown_id(client):
    resp = client.get("/infer/video/does-not-exist")
    assert resp.status_code == 404


def test_job_file_404_for_unknown_id(client):
    resp = client.get("/infer/video/does-not-exist/file")
    assert resp.status_code == 404
