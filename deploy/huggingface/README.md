---
title: Sensitive Area Intrusion Detection
emoji: 🚨
colorFrom: red
colorTo: blue
sdk: docker
app_port: 7860
pinned: false
license: mit
short_description: YOLOv8 + DeepSORT intrusion detection with live alerts
---

# Sensitive-Area Intrusion Detection System

Live demo of a YOLOv8 + DeepSORT intrusion-detection pipeline: upload a
video (or use your webcam) to get object detection, multi-object tracking,
and rule-based alerts (restricted-zone intrusion, perimeter-line breach,
fast movement, dropped objects, weapon detection, group gathering) as an
incident timeline — not a ping every frame.

**This Space runs on free CPU hardware**, so video processing is slower
than the GPU numbers in the full write-up below. A short clip (a few
hundred frames) typically finishes in under a minute.

Full source, architecture notes, model metrics, and local/Docker setup:
**[github.com/raghavpli515/Sensitive-area-Intrusion-detection-system](https://github.com/raghavpli515/Sensitive-area-Intrusion-detection-system)**
