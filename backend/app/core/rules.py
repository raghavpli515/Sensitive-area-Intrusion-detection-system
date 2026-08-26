"""Rule-based suspicious-activity detection on top of tracked detections.

"""
from __future__ import annotations

from collections import defaultdict, deque
from dataclasses import dataclass

import numpy as np
from shapely.geometry import LineString, Point, Polygon

from app.schemas.detection import Alert, Detection


@dataclass
class RuleConfig:
    # Restricted zone / perimeter line, expressed as fractions of frame (w, h)
    # so they scale to whatever resolution the source video/camera provides.
    zone_fractions: tuple[tuple[float, float], ...] = (
        (0.15, 0.15), (0.85, 0.15), (0.85, 0.85), (0.15, 0.85),
    )
    line_fractions: tuple[tuple[float, float], tuple[float, float]] = (
        (0.2, 0.5), (0.8, 0.5),
    )

    speed_threshold_px: float = 30.0        # speed threshold in pixels/frame for "fast movement" detection
    stationary_frames: int = 10             # number of consecutive frames to consider for "stationary" detection
    stationary_max_range_px: float = 15.0   # max distance between centers over `stationary_frames` to consider "stationary"
    group_distance_px: float = 100.0        # max distance between centers to consider "group gathering"
    group_min_count: int = 3                # minimum number of objects to consider "group gathering"
    history_len: int = 30                   # length of track history to maintain
    weapon_class_names: frozenset[str] = frozenset({"weapon"})

    # Minimum time between two alerts of the same (track, type) — e.g. a
    # person standing in the restricted zone for 5 seconds produces one
    # alert every `cooldown_seconds`, not one alert per frame. First
    # occurrence of any condition always fires immediately.
    cooldown_seconds: float = 2.0


@dataclass
class _TrackPoint:
    frame: int
    bbox: list[int]
    class_name: str


class RuleEngine:
    """Stateful per-video / per-connection rule evaluator.

    Create one instance per video-processing job or per live stream
    connection — never share an instance across independent sources.
    """

    def __init__(self, config: RuleConfig | None = None, fps: float = 30.0):
        self.config = config or RuleConfig()
        self._history: dict[int, deque[_TrackPoint]] = defaultdict(
            lambda: deque(maxlen=self.config.history_len)
        )
        # Cooldown is expressed in seconds in config (human-meaningful) but
        # tracked in frames internally, since that's what we're actually
        # counting. `fps` only needs to be approximately right — see the
        # call sites in services/pipeline.py (real fps from the video) and
        # api/stream.py (assumed fps matching the frontend's capture rate).
        self._cooldown_frames = max(1, round(self.config.cooldown_seconds * fps))
        self._last_alert_frame: dict[tuple[int | None, str], int] = {}

    def process_frame(
        self,
        frame_id: int,
        detections: list[Detection],
        frame_width: int,
        frame_height: int,
    ) -> list[Alert]:
        zone = self._scaled_polygon(frame_width, frame_height)
        line = self._scaled_line(frame_width, frame_height)

        for det in detections:
            self._history[det.track_id].append(
                _TrackPoint(frame=frame_id, bbox=det.bbox, class_name=det.class_name)
            )

        alerts: list[Alert] = []
        for track_id, history in self._history.items():
            if not history or history[-1].frame != frame_id:
                continue  # this track wasn't seen in the current frame
            alerts.extend(self._evaluate_track(track_id, history, zone, line, frame_id))

        alerts.extend(self._evaluate_group_gathering(detections, frame_id))
        return alerts

    def _should_emit(self, track_id: int | None, alert_type: str, frame_id: int) -> bool:
        """Rate-limits repeated alerts of the same (track, type): the first
        occurrence always fires, later ones only after `cooldown_seconds`
        has passed — so a condition that holds for many frames produces
        periodic re-notifications instead of one alert per frame."""
        key = (track_id, alert_type)
        last = self._last_alert_frame.get(key)
        if last is not None and frame_id - last < self._cooldown_frames:
            return False
        self._last_alert_frame[key] = frame_id
        return True

    # -- per-track rules ----------------------------------------------------

    def _evaluate_track(
        self,
        track_id: int,
        history: deque[_TrackPoint],
        zone: Polygon,
        line: LineString,
        frame_id: int,
    ) -> list[Alert]:
        alerts: list[Alert] = []
        latest = history[-1]
        curr_center = self._center(latest.bbox)

        if latest.class_name.lower() in self.config.weapon_class_names \
                and self._should_emit(track_id, "weapon_detected", frame_id):
            alerts.append(Alert(
                frame=frame_id, type="weapon_detected",
                message=f"Weapon detected (track {track_id})", track_id=track_id,
            ))

        if self._inside_zone(curr_center, zone) \
                and self._should_emit(track_id, "zone_intrusion", frame_id):
            alerts.append(Alert(
                frame=frame_id, type="zone_intrusion",
                message=f"Restricted zone intrusion (track {track_id})", track_id=track_id,
            ))

        if len(history) >= 2:
            prev_center = self._center(history[-2].bbox)
            speed = float(np.linalg.norm(np.array(curr_center) - np.array(prev_center)))

            if speed > self.config.speed_threshold_px and latest.class_name.lower() == "person" \
                    and self._should_emit(track_id, "fast_movement", frame_id):
                alerts.append(Alert(
                    frame=frame_id, type="fast_movement",
                    message=f"Fast movement detected (track {track_id}, "
                            f"~{speed:.0f}px/frame)",
                    track_id=track_id,
                ))

            # Not rate-limited: crossing a line is a one-off geometric event
            # (prev/curr straddling it), not a sustained condition, so it
            # can't repeat every frame the way the others can.
            if self._line_crossed(prev_center, curr_center, line):
                alerts.append(Alert(
                    frame=frame_id, type="line_breach",
                    message=f"Perimeter line crossed (track {track_id})", track_id=track_id,
                ))

        if len(history) >= self.config.stationary_frames:
            recent = list(history)[-self.config.stationary_frames:]
            centers = np.array([self._center(p.bbox) for p in recent])
            if np.all(np.ptp(centers, axis=0) < self.config.stationary_max_range_px) \
                    and self._should_emit(track_id, "dropped_object", frame_id):
                alerts.append(Alert(
                    frame=frame_id, type="dropped_object",
                    message=f"Object stationary for {self.config.stationary_frames}+ frames "
                            f"(track {track_id}) — possibly dropped/abandoned",
                    track_id=track_id,
                ))

        return alerts

    def _evaluate_group_gathering(self, detections: list[Detection], frame_id: int) -> list[Alert]:
        if len(detections) < self.config.group_min_count:
            return []

        centers = [self._center(d.bbox) for d in detections]
        for i, center in enumerate(centers):
            nearby = sum(
                1 for j, other in enumerate(centers)
                if j != i
                and np.linalg.norm(np.array(center) - np.array(other)) < self.config.group_distance_px
            )
            if nearby + 1 >= self.config.group_min_count:
                if not self._should_emit(None, "group_gathering", frame_id):
                    return []
                return [Alert(
                    frame=frame_id, type="group_gathering",
                    message=f"Group gathering detected near "
                            f"({center[0]:.0f}, {center[1]:.0f})",
                )]
        return []

    # -- geometry helpers -----------------------------------------------------

    @staticmethod
    def _center(bbox: list[int]) -> tuple[float, float]:
        x1, y1, x2, y2 = bbox
        return ((x1 + x2) / 2, (y1 + y2) / 2)

    def _scaled_polygon(self, width: int, height: int) -> Polygon:
        return Polygon([(fx * width, fy * height) for fx, fy in self.config.zone_fractions])

    def _scaled_line(self, width: int, height: int) -> LineString:
        (x1f, y1f), (x2f, y2f) = self.config.line_fractions
        return LineString([(x1f * width, y1f * height), (x2f * width, y2f * height)])

    @staticmethod
    def _inside_zone(point: tuple[float, float], zone: Polygon) -> bool:
        return zone.contains(Point(point))

    @staticmethod
    def _line_crossed(prev: tuple[float, float], curr: tuple[float, float], line: LineString) -> bool:
        if prev == curr:
            return False
        return LineString([prev, curr]).crosses(line)


# ---------------------------------------------------------------------------
# Pose-based rule — documented future extension, not wired into RuleEngine.
# ---------------------------------------------------------------------------

def is_arms_flaring(pose_keypoints: dict) -> bool:
    """Pure function, ready to wire in once a pose-estimation model is added.

    Expects `pose_keypoints` with (x, y) tuples for at least
    'left_wrist', 'right_wrist', 'left_shoulder', 'right_shoulder'.
    """
    try:
        left_wrist = pose_keypoints.get("left_wrist")
        right_wrist = pose_keypoints.get("right_wrist")
        left_shoulder = pose_keypoints.get("left_shoulder")
        right_shoulder = pose_keypoints.get("right_shoulder")

        if not all([left_wrist, right_wrist, left_shoulder, right_shoulder]):
            return False

        left_flared = left_wrist[1] < left_shoulder[1]   # wrists are above shoulders in image coordinates
        right_flared = right_wrist[1] < right_shoulder[1]
        return left_flared and right_flared
    except (TypeError, IndexError, KeyError):
        return False
