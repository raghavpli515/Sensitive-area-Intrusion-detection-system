FROM python:3.11-slim

WORKDIR /srv

# libgl1/libglib2.0-0: shared libs the full opencv-python wheel needs
# (see requirements.txt for why it's opencv-python, not -headless).
# ffmpeg: re-encodes processed videos to real H.264 so browsers can play them
# — see services/pipeline._transcode_to_browser_compatible_mp4.
RUN apt-get update && apt-get install -y --no-install-recommends \
    libgl1 \
    libglib2.0-0 \
    ffmpeg \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app ./app

ENV IDS_MODEL_PATH=/srv/models/yolov8_model.pt \
    IDS_UPLOAD_DIR=/srv/data/uploads \
    IDS_OUTPUT_DIR=/srv/outputs

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
