"""Gradio demo for a free-tier Hugging Face Space: upload a video, get an
annotated result plus an incident-timeline alert log.

Reuses the exact same detect -> track -> rules pipeline as the full
FastAPI + React app in the GitHub repo (`app/core`, `app/services`) —
nothing here is a rewrite. What this demo drops, on purpose, to stay a
single lightweight Gradio app: the async job-polling API and the live
webcam/WebSocket mode. Both are in the full repo.

This Space's free tier only offers ZeroGPU for Gradio Spaces (see
deploy/huggingface-gradio/README.md), which — unlike a plain always-on
CPU/GPU box — attaches a real GPU only for the duration of a function
explicitly decorated with `@spaces.GPU`, and HF's platform checks at
startup that at least one such function exists at all. The model loads on
CPU at import time as usual; `_run_pipeline` below moves it onto the GPU
that's attached only while it's actually running. Locally (outside a real
ZeroGPU Space) `spaces.GPU` is a documented no-op passthrough, so this
behaves identically to plain CPU code in dev.
"""
from __future__ import annotations

import tempfile
from pathlib import Path

import gradio as gr
import spaces
import torch

from app.core import registry
from app.core.detector import YOLODetector
from app.services.jobs import Job
from app.services.pipeline import run_video_job

MODEL_PATH = Path(__file__).parent / "models" / "yolov8_model.pt"

_detector = YOLODetector(model_path=MODEL_PATH, device="cpu")
_detector.load()
registry.yolo_detector = _detector


@spaces.GPU(duration=60)  # short clips finish well under this; smaller asks stretch the free daily quota further
def _run_pipeline(video_path: str, confidence_threshold: float, output_path: Path) -> Job:
    if torch.cuda.is_available():
        _detector.model.to("cuda")
    job = Job(id="demo")
    run_video_job(job, Path(video_path), output_path, confidence_threshold)
    return job


def run_detection(video_path: str | None, confidence_threshold: float):
    if not video_path:
        return None, "Upload a video first."

    output_path = Path(tempfile.mkdtemp()) / "annotated.mp4"

    try:
        job = _run_pipeline(video_path, confidence_threshold, output_path)
    except Exception as exc:  # noqa: BLE001 - surfaced in the UI, not a 500
        return None, f"**Error:** {exc}"

    if not job.alerts:
        alerts_md = "No suspicious activity detected."
    else:
        rows = ["| Frame | Event | Type | Message | Duration |", "|---|---|---|---|---|"]
        for alert in job.alerts[-200:]:
            duration = f"{alert.duration_seconds:.1f}s" if alert.duration_seconds is not None else "—"
            rows.append(f"| {alert.frame} | {alert.event} | {alert.type} | {alert.message} | {duration} |")
        alerts_md = "\n".join(rows)

    return str(job.output_path), alerts_md


with gr.Blocks(title="Sensitive-Area Intrusion Detection") as demo:
    gr.Markdown(
        "# 🚨 Sensitive-Area Intrusion Detection\n"
        "YOLOv8 detection + DeepSORT tracking + rule-based alerting — "
        "restricted-zone intrusion, perimeter-line breach, fast movement, "
        "dropped objects, weapon detection, group gathering — as an "
        "incident timeline (one entry when it starts, one when it ends), "
        "not a ping every frame.\n\n"
        "Runs on this Space's free ZeroGPU tier — a real GPU is attached "
        "only while detection is actually running, so the first request "
        "after a while may pause briefly to attach one. Full source, the "
        "live-webcam mode, architecture notes, and real model metrics: "
        "[GitHub](https://github.com/raghavpli515/Sensitive-area-Intrusion-detection-system)."
    )

    with gr.Row():
        with gr.Column():
            video_input = gr.Video(label="Upload surveillance footage")
            confidence = gr.Slider(0.1, 0.9, value=0.4, step=0.05, label="Confidence threshold")
            submit = gr.Button("Run Detection", variant="primary")
        with gr.Column():
            video_output = gr.Video(label="Annotated result")
            alerts_output = gr.Markdown(label="Alert timeline")

    submit.click(run_detection, inputs=[video_input, confidence], outputs=[video_output, alerts_output])

if __name__ == "__main__":
    demo.queue().launch()
