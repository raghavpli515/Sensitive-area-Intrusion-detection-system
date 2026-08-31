# Single-container build for the Hugging Face Space: builds the React
# frontend and serves it + the FastAPI API from one uvicorn process on one
# port, instead of the two-service docker-compose.yml setup used for local
# dev (Spaces run exactly one container per app).
#
# Build context must be the repo root, e.g.:
#   docker build -f deploy/huggingface/Dockerfile -t ids-space .
# (this is what deploy/huggingface/sync_and_push.sh does automatically)

FROM node:20-alpine AS frontend-build
WORKDIR /app
COPY frontend/package.json frontend/package-lock.json* ./
RUN npm install
COPY frontend/ .
# Empty, not omitted: frontend and API share an origin in this deploy, so
# the client should make same-origin requests (see src/api/client.ts) —
# omitting this would instead bake in the http://localhost:8000 dev default.
ENV VITE_API_URL=""
RUN npm run build

FROM python:3.11-slim
WORKDIR /srv

# Same system deps as backend/Dockerfile — see it for why each is needed.
RUN apt-get update && apt-get install -y --no-install-recommends \
    libgl1 \
    libglib2.0-0 \
    ffmpeg \
    && rm -rf /var/lib/apt/lists/*

COPY backend/requirements.txt .
# CPU-only torch/torchvision from PyTorch's own index first: the default
# PyPI wheel pulls ~2-3GB of unused nvidia-* CUDA packages, and this Space
# runs on free CPU-only hardware. Installed before requirements.txt so pip
# sees a matching version already satisfied and doesn't try to replace it.
RUN pip install --no-cache-dir torch==2.7.1 torchvision==0.22.1 \
        --index-url https://download.pytorch.org/whl/cpu \
    && pip install --no-cache-dir -r requirements.txt

COPY backend/app ./app
COPY --from=frontend-build /app/dist ./static
# Real weights, not the .dvc pointer: the Space can't run `dvc pull` against
# a personal remote, so sync_and_push.sh copies the actual .pt file in here.
COPY models/yolov8_model.pt ./models/yolov8_model.pt

ENV IDS_MODEL_PATH=/srv/models/yolov8_model.pt \
    IDS_UPLOAD_DIR=/srv/data/uploads \
    IDS_OUTPUT_DIR=/srv/outputs \
    IDS_FRONTEND_DIST_DIR=/srv/static

# Hugging Face Spaces route traffic to port 7860 by default (see README.md's
# `app_port`), unlike backend/Dockerfile's 8000.
EXPOSE 7860
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "7860"]
