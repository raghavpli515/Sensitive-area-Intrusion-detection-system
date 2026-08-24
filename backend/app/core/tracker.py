"""Thin wrapper around DeepSORT so callers don't depend on its API directly."""
from __future__ import annotations

from deep_sort_realtime.deepsort_tracker import DeepSort


class ObjectTracker:
    def __init__(self, max_age: int = 30, n_init: int = 3, max_iou_distance: float = 0.7):   #max age refers to the number of frames a track is kept alive without detections, n_init is the number of consecutive detections before a track is confirmed, and max_iou_distance is the maximum intersection over union distance for matching detections to existing tracks.
        self.tracker = DeepSort(
            max_age=max_age,
            n_init=n_init,
            max_iou_distance=max_iou_distance,
        )

    def update(self, detections: list, frame):
        """
        detections format: [([x, y, w, h], confidence, class_name), ...]
        Returns confirmed + tentative DeepSort Track objects for this frame.
        """
        return self.tracker.update_tracks(detections, frame=frame)
