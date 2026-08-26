"""Rule-based suspicious-activity detection on top of tracked detections.

"""
from __future__ import annotations

from collections import defaultdict, deque
from collections.abc import Callable
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
    history_len: int = 30                   # length of track history to maintain; also how long a track
                                             # may go unseen before its open incidents are force-closed
    weapon_class_names: frozenset[str] = frozenset({"weapon"})


@dataclass
class _TrackPoint:
    frame: int
    bbox: list[int]
    class_name: str


class RuleEngine:
    """Stateful per-video / per-connection rule evaluator.

    Create one instance per video-processing job or per live stream
    connection — never share an instance across independent sources.

    Sustained conditions (zone intrusion, dropped object, weapon visible,
    fast-movement burst, group gathering) are modelled as *incidents*: one
    "started" alert when a condition first becomes true, nothing further
    while it remains true, and one "ended" alert (with a duration) when it
    clears — an incident timeline, not a ping every frame it holds.
    `line_breach` is the exception: crossing a line is a one-off event with
    no "ongoing" state, so it's always just a single "started" alert.
    """

    def __init__(self, config: RuleConfig | None = None, fps: float = 30.0):
        self.config = config or RuleConfig()
        self._fps = fps
        self._history: dict[int, deque[_TrackPoint]] = defaultdict(
            lambda: deque(maxlen=self.config.history_len)
        )
        # (track_id, alert_type) -> frame the incident started on.
        # track_id is None for the one non-per-track rule (group_gathering).
        self._open_incidents: dict[tuple[int | None, str], int] = {}

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
        alerts.extend(self._close_stale_incidents(frame_id))
        return alerts

    def finalize(self, last_frame_id: int) -> list[Alert]:
        """Call once after the final frame (video ended / stream closed) so
        every "started" event has a matching "ended" one, instead of leaving
        still-active incidents silently unresolved."""
        alerts = []
        for (track_id, alert_type), start_frame in list(self._open_incidents.items()):
            duration = (last_frame_id - start_frame) / self._fps
            who = f"track {track_id}" if track_id is not None else "group"
            alerts.append(Alert(
                frame=last_frame_id, type=alert_type, event="ended", track_id=track_id,
                message=f"{_TITLES[alert_type]} still ongoing when processing ended "
                        f"({who}, lasted {duration:.1f}s)",
                duration_seconds=round(duration, 1),
            ))
        self._open_incidents.clear()
        return alerts

    def _evaluate_incident(
        self,
        track_id: int | None,
        alert_type: str,
        is_active: bool,
        frame_id: int,
        ended_message: Callable[[float], str],
        started_message: str | None = None,
    ) -> Alert | None:
        """Turns a per-frame boolean condition into a start/end incident.
        Returns an Alert only on the frame the state actually changes."""
        key = (track_id, alert_type)
        was_open = key in self._open_incidents

        if is_active and not was_open:
            self._open_incidents[key] = frame_id
            return Alert(
                frame=frame_id, type=alert_type, event="started", track_id=track_id,
                message=started_message or f"{_TITLES[alert_type]} started"
                        + (f" (track {track_id})" if track_id is not None else ""),
            )

        if not is_active and was_open:
            start_frame = self._open_incidents.pop(key)
            duration = (frame_id - start_frame) / self._fps
            return Alert(
                frame=frame_id, type=alert_type, event="ended", track_id=track_id,
                message=ended_message(duration), duration_seconds=round(duration, 1),
            )

        return None

    def _close_stale_incidents(self, frame_id: int) -> list[Alert]:
        """A track that stops appearing (occlusion, lost by the tracker)
        never evaluates to condition=False again, so its incidents would
        stay open forever without this: force-close anything whose track
        hasn't been seen in `history_len` frames."""
        alerts = []
        for (track_id, alert_type), start_frame in list(self._open_incidents.items()):
            if track_id is None:
                continue  # group incidents are closed by _evaluate_group_gathering itself
            history = self._history.get(track_id)
            last_seen = history[-1].frame if history else start_frame
            if frame_id - last_seen > self.config.history_len:
                duration = (last_seen - start_frame) / self._fps
                alerts.append(Alert(
                    frame=last_seen, type=alert_type, event="ended", track_id=track_id,
                    message=f"{_TITLES[alert_type]} ended — track {track_id} lost "
                            f"(lasted {duration:.1f}s)",
                    duration_seconds=round(duration, 1),
                ))
                del self._open_incidents[(track_id, alert_type)]
        return alerts

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

        weapon_active = latest.class_name.lower() in self.config.weapon_class_names
        alert = self._evaluate_incident(
            track_id, "weapon_detected", weapon_active, frame_id,
            ended_message=lambda d: f"Weapon no longer visible (track {track_id}, was visible for {d:.1f}s)",
        )
        if alert:
            alerts.append(alert)

        zone_active = self._inside_zone(curr_center, zone)
        alert = self._evaluate_incident(
            track_id, "zone_intrusion", zone_active, frame_id,
            ended_message=lambda d: f"Restricted zone intrusion ended (track {track_id}, lasted {d:.1f}s)",
        )
        if alert:
            alerts.append(alert)

        if len(history) >= 2:
            prev_center = self._center(history[-2].bbox)
            speed = float(np.linalg.norm(np.array(curr_center) - np.array(prev_center)))

            fast_active = speed > self.config.speed_threshold_px and latest.class_name.lower() == "person"
            alert = self._evaluate_incident(
                track_id, "fast_movement", fast_active, frame_id,
                started_message=f"Fast movement started (track {track_id}, ~{speed:.0f}px/frame)",
                ended_message=lambda d: f"Fast movement ended (track {track_id}, lasted {d:.1f}s)",
            )
            if alert:
                alerts.append(alert)

            # Not an incident: crossing a line is a one-off geometric event
            # (prev/curr straddling it), not a sustained condition — there's
            # no "ended" state to pair it with.
            if self._line_crossed(prev_center, curr_center, line):
                alerts.append(Alert(
                    frame=frame_id, type="line_breach",
                    message=f"Perimeter line crossed (track {track_id})", track_id=track_id,
                ))

        if len(history) >= self.config.stationary_frames:
            recent = list(history)[-self.config.stationary_frames:]
            centers = np.array([self._center(p.bbox) for p in recent])
            stationary_active = bool(np.all(np.ptp(centers, axis=0) < self.config.stationary_max_range_px))
            alert = self._evaluate_incident(
                track_id, "dropped_object", stationary_active, frame_id,
                started_message=f"Object stationary for {self.config.stationary_frames}+ frames "
                                 f"(track {track_id}) — possibly dropped/abandoned",
                ended_message=lambda d: f"Previously dropped/abandoned object moved again "
                                         f"(track {track_id}, was stationary for {d:.1f}s)",
            )
            if alert:
                alerts.append(alert)

        return alerts

    def _evaluate_group_gathering(self, detections: list[Detection], frame_id: int) -> list[Alert]:
        is_active = False
        representative_center: tuple[float, float] | None = None

        if len(detections) >= self.config.group_min_count:
            centers = [self._center(d.bbox) for d in detections]
            for i, center in enumerate(centers):
                nearby = sum(
                    1 for j, other in enumerate(centers)
                    if j != i
                    and np.linalg.norm(np.array(center) - np.array(other)) < self.config.group_distance_px
                )
                if nearby + 1 >= self.config.group_min_count:
                    is_active = True
                    representative_center = center
                    break

        started_message = (
            f"Group gathering detected near ({representative_center[0]:.0f}, {representative_center[1]:.0f})"
            if representative_center else None
        )
        alert = self._evaluate_incident(
            None, "group_gathering", is_active, frame_id,
            started_message=started_message,
            ended_message=lambda d: f"Group gathering dispersed (lasted {d:.1f}s)",
        )
        return [alert] if alert else []

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


_TITLES = {
    "weapon_detected": "Weapon detection",
    "zone_intrusion": "Restricted zone intrusion",
    "fast_movement": "Fast movement",
    "dropped_object": "Dropped/abandoned object",
    "group_gathering": "Group gathering",
}


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
