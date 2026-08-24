FROM python:3.11-slim

WORKDIR /srv

# OpenCV needs a couple of shared libs even in headless mode.
RUN apt-get update && apt-get install -y --no-install-recommends \
    libgl1 \
    libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app ./app

ENV IDS_MODEL_PATH=/srv/models/yolov8_model.pt \
    IDS_UPLOAD_DIR=/srv/data/uploads \
    IDS_OUTPUT_DIR=/srv/outputs

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
