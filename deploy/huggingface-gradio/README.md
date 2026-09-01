---
title: Sensitive Area Intrusion Detection
emoji: 🚨
colorFrom: red
colorTo: blue
sdk: gradio
sdk_version: 6.26.0
app_file: demo.py
pinned: false
license: mit
short_description: YOLOv8 + DeepSORT intrusion detection with live alerts
---

# Sensitive-Area Intrusion Detection System

Upload a video (or use one of the examples) to run YOLOv8 detection,
DeepSORT tracking, and rule-based alerting — restricted-zone intrusion,
perimeter-line breach, fast movement, dropped objects, weapon detection,
group gathering — presented as an incident timeline: one entry when a
condition starts, one when it ends, not a ping every frame.

**Runs on this Space's free ZeroGPU tier** — a real GPU is attached only
for the duration of each detection run, so the first request after a
period of inactivity may pause briefly while one is attached.

This Gradio demo covers the upload flow only. The full project — including
a live-webcam mode, an async job-polling API, Docker Compose, tests, and
CI — is the real deliverable:
**[github.com/raghavpli515/Sensitive-area-Intrusion-detection-system](https://github.com/raghavpli515/Sensitive-area-Intrusion-detection-system)**
