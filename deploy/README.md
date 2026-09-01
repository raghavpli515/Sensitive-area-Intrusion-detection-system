# Deploy targets

Two self-contained deployment packages, each assembling only what it needs
from `backend/`/`frontend/` and pushing a snapshot to its own remote — see
each one's `sync_and_push.sh` for exactly what gets included.

- **[huggingface-gradio/](huggingface-gradio/)** — what's actually live:
  https://huggingface.co/spaces/PimoLee5/intrusion-detection-system. A
  Gradio UI wrapping the same `app/core`/`app/services` pipeline, running on
  Hugging Face's free ZeroGPU tier. Covers the upload flow only.

- **[huggingface/](huggingface/)** — a single-container FastAPI + React
  build (the full app, one Docker image) for a Space on the **Docker** SDK.
  Built, run, and verified locally (real upload → job → playable annotated
  video, confirmed with Playwright) but not deployed: Docker Spaces are a
  paid-tier feature on the account this project used. Kept here, tested and
  ready, for a paid tier or a Docker-friendly host (Render, Fly.io, etc.).
