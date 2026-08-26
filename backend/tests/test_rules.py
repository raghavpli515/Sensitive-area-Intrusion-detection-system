from app.core.rules import RuleConfig, RuleEngine, is_arms_flaring
from app.schemas.detection import Detection


def make_engine(**overrides) -> RuleEngine:
    return RuleEngine(RuleConfig(**overrides))


def test_weapon_detection_fires_immediately():
    engine = make_engine()
    dets = [Detection(track_id=1, class_name="Weapon", confidence=0.9, bbox=[10, 10, 20, 20])]

    alerts = engine.process_frame(0, dets, frame_width=640, frame_height=480)

    assert any(a.type == "weapon_detected" for a in alerts)


def test_fast_movement_detected_for_large_displacement():
    engine = make_engine(speed_threshold_px=10)
    engine.process_frame(
        0, [Detection(track_id=1, class_name="person", confidence=0.9, bbox=[0, 0, 10, 10])], 640, 480
    )

    alerts = engine.process_frame(
        1, [Detection(track_id=1, class_name="person", confidence=0.9, bbox=[200, 200, 210, 210])], 640, 480
    )

    assert any(a.type == "fast_movement" for a in alerts)


def test_no_fast_movement_for_small_displacement():
    engine = make_engine(speed_threshold_px=1000)
    engine.process_frame(
        0, [Detection(track_id=1, class_name="person", confidence=0.9, bbox=[0, 0, 10, 10])], 640, 480
    )

    alerts = engine.process_frame(
        1, [Detection(track_id=1, class_name="person", confidence=0.9, bbox=[1, 1, 11, 11])], 640, 480
    )

    assert not any(a.type == "fast_movement" for a in alerts)


def test_zone_intrusion_detected_inside_configured_zone():
    whole_frame_zone = ((0.0, 0.0), (1.0, 0.0), (1.0, 1.0), (0.0, 1.0))
    engine = make_engine(zone_fractions=whole_frame_zone)
    dets = [Detection(track_id=1, class_name="person", confidence=0.9, bbox=[100, 100, 120, 120])]

    alerts = engine.process_frame(0, dets, 640, 480)

    assert any(a.type == "zone_intrusion" for a in alerts)


def test_no_zone_intrusion_outside_configured_zone():
    tiny_zone = ((0.0, 0.0), (0.01, 0.0), (0.01, 0.01), (0.0, 0.01))
    engine = make_engine(zone_fractions=tiny_zone)
    dets = [Detection(track_id=1, class_name="person", confidence=0.9, bbox=[300, 300, 320, 320])]

    alerts = engine.process_frame(0, dets, 640, 480)

    assert not any(a.type == "zone_intrusion" for a in alerts)


def test_line_breach_detected_when_track_crosses_the_line():
    # Horizontal line at mid-height; track moves from above it to below it.
    engine = make_engine(line_fractions=((0.0, 0.5), (1.0, 0.5)))
    engine.process_frame(
        0, [Detection(track_id=1, class_name="person", confidence=0.9, bbox=[100, 100, 110, 110])], 640, 480
    )

    alerts = engine.process_frame(
        1, [Detection(track_id=1, class_name="person", confidence=0.9, bbox=[100, 400, 110, 410])], 640, 480
    )

    assert any(a.type == "line_breach" for a in alerts)


def test_dropped_object_after_prolonged_stationarity():
    engine = make_engine(stationary_frames=3, stationary_max_range_px=5)
    alerts = []
    for frame in range(3):
        alerts = engine.process_frame(
            frame, [Detection(track_id=1, class_name="person", confidence=0.9, bbox=[50, 50, 60, 60])], 640, 480
        )

    assert any(a.type == "dropped_object" for a in alerts)


def test_group_gathering_detected_for_close_cluster():
    engine = make_engine(group_distance_px=50, group_min_count=3)
    dets = [
        Detection(track_id=1, class_name="person", confidence=0.9, bbox=[100, 100, 110, 110]),
        Detection(track_id=2, class_name="person", confidence=0.9, bbox=[105, 100, 115, 110]),
        Detection(track_id=3, class_name="person", confidence=0.9, bbox=[110, 105, 120, 115]),
    ]

    alerts = engine.process_frame(0, dets, 640, 480)

    assert any(a.type == "group_gathering" for a in alerts)


def test_no_group_gathering_below_minimum_count():
    engine = make_engine(group_distance_px=50, group_min_count=3)
    dets = [
        Detection(track_id=1, class_name="person", confidence=0.9, bbox=[100, 100, 110, 110]),
        Detection(track_id=2, class_name="person", confidence=0.9, bbox=[105, 100, 115, 110]),
    ]

    alerts = engine.process_frame(0, dets, 640, 480)

    assert not any(a.type == "group_gathering" for a in alerts)


def test_separate_engines_do_not_share_track_history():
    """Regression test for the bug this replaces: the original script kept
    track history in module-level globals, so two videos processed in the
    same process leaked state into each other."""
    engine_a = make_engine()
    engine_b = make_engine()

    engine_a.process_frame(
        0, [Detection(track_id=1, class_name="person", confidence=0.9, bbox=[0, 0, 10, 10])], 640, 480
    )

    assert engine_b._history == {}  # noqa: SLF001 - verifying isolation is the point of this test


def test_zone_intrusion_does_not_repeat_every_frame_within_cooldown():
    """Regression test: a sustained condition used to fire one alert per
    frame (e.g. ~150 near-identical alerts for a 5s intrusion at 30fps).
    It should now fire once, then stay quiet until the cooldown elapses."""
    whole_frame_zone = ((0.0, 0.0), (1.0, 0.0), (1.0, 1.0), (0.0, 1.0))
    config = RuleConfig(zone_fractions=whole_frame_zone, cooldown_seconds=1.0)
    engine = RuleEngine(config, fps=10.0)  # cooldown = 10 frames
    det = [Detection(track_id=1, class_name="person", confidence=0.9, bbox=[100, 100, 120, 120])]

    fire_counts = []
    for frame in range(25):
        alerts = engine.process_frame(frame, det, 640, 480)
        fire_counts.append(sum(1 for a in alerts if a.type == "zone_intrusion"))

    # Fires on frame 0 (first occurrence) and again on frame 10 (cooldown
    # elapsed), not on every one of the 25 frames.
    assert fire_counts[0] == 1
    assert sum(fire_counts[1:10]) == 0
    assert fire_counts[10] == 1
    assert sum(fire_counts) < 5  # nowhere near "one per frame"


def test_different_tracks_have_independent_cooldowns():
    whole_frame_zone = ((0.0, 0.0), (1.0, 0.0), (1.0, 1.0), (0.0, 1.0))
    engine = RuleEngine(RuleConfig(zone_fractions=whole_frame_zone, cooldown_seconds=10.0), fps=30.0)
    dets = [
        Detection(track_id=1, class_name="person", confidence=0.9, bbox=[10, 10, 20, 20]),
        Detection(track_id=2, class_name="person", confidence=0.9, bbox=[30, 30, 40, 40]),
    ]

    alerts = engine.process_frame(0, dets, 640, 480)

    zone_alert_track_ids = {a.track_id for a in alerts if a.type == "zone_intrusion"}
    assert zone_alert_track_ids == {1, 2}  # both fire on first occurrence, independently


def test_is_arms_flaring_pure_function():
    flared = {
        "left_wrist": (10, 5), "right_wrist": (90, 5),
        "left_shoulder": (20, 50), "right_shoulder": (80, 50),
    }
    not_flared = {
        "left_wrist": (10, 60), "right_wrist": (90, 60),
        "left_shoulder": (20, 50), "right_shoulder": (80, 50),
    }

    assert is_arms_flaring(flared) is True
    assert is_arms_flaring(not_flared) is False
    assert is_arms_flaring({}) is False
