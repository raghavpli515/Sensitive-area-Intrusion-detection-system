# Architecture

## Pipeline

Both entry points — batch video upload and the live camera feed — run the
exact same three-stage pipeline (`backend/app/services/pipeline.py`):
**detect → track → apply rules**. Nothing is duplicated between them; only
the I/O around the pipeline differs (a video file processed frame-by-frame on
a background thread vs. JPEG frames pushed over a WebSocket).

```mermaid
flowchart LR
    subgraph Client["Browser (React)"]
        U["Upload page<br/>file input"]
        L["Live page<br/>getUserMedia + canvas"]
    end

    subgraph API["FastAPI backend"]
        V["POST /infer/video<br/>→ job id"]
        J["GET /infer/video/{id}<br/>poll status"]
        F["GET /infer/video/{id}/file<br/>annotated mp4"]
        WS["WS /ws/stream<br/>one connection = one session"]

        subgraph Pipeline["services/pipeline.process_frame"]
            D["YOLOv8 detector<br/>core/detector.py"]
            T["DeepSORT tracker<br/>core/tracker.py"]
            R["Rule engine<br/>core/rules.py"]
        end
    end

    U -->|multipart upload| V --> J --> F
    L -->|binary JPEG frames| WS
    V -.->|background thread| Pipeline
    WS -.->|per-connection state| Pipeline
    D --> T --> R
    R -->|alerts + annotated frame| J
    R -->|alerts + annotated frame| WS
```

## Design decisions worth calling out

**One shared pipeline function, two thin transports.** The original
prototype had detect/track/annotate logic duplicated (and drifting) across
`utils/inference.py` and `backend/app/api/inference.py`. There's now exactly
one implementation (`process_frame`), used by both the job runner and the
WebSocket handler.

**Per-session tracker + rule-engine state.** `RuleEngine` and `ObjectTracker`
are instantiated once per video-processing job or per live WebSocket
connection — never shared globally. The original rule script kept track
history in module-level `defaultdict`s, so two videos processed in the same
process silently leaked state into each other. `backend/tests/test_rules.py`
has a regression test for this (`test_separate_engines_do_not_share_track_history`).

**Async job store for video uploads.** `POST /infer/video` returns a job id
immediately; a background thread does the work while the client polls
`GET /infer/video/{id}`. This is an intentionally minimal in-memory
implementation (`services/jobs.py`) — it does not survive a process restart
and won't work across multiple backend replicas. A real deployment would
swap it for Celery/RQ + Redis behind the same three-method interface
(`create`, `get`, `run_in_background`), without touching the API routes.

**Output video is re-encoded to real H.264, not served as OpenCV writes it.**
`cv2.VideoWriter` with fourcc `mp4v` produces MPEG-4 Part 2 — a valid mp4
file that downloads and even plays in some desktop players, but that
Chrome/Firefox/Safari's native `<video>` element silently refuses to decode
(they require H.264/AVC, VP8/9, or AV1). This was caught by actually running
the finished stack end-to-end: jobs completed successfully and alerts
populated correctly, but the browser showed no playable video — a real bug
that unit tests and API-contract tests alone couldn't have caught, since
both the file and the API response were "correct." `run_video_job` now
writes to a temporary file, then re-encodes with `ffmpeg -vcodec libx264`
(`services/pipeline._transcode_to_browser_compatible_mp4`) before serving
it. If `ffmpeg` is missing, the job fails loudly with a clear error instead
of silently shipping an unplayable file.

**Alerts are incidents with a start and end, not a ping every frame.**
The first version fired a fresh alert on every single frame a condition
held — a person standing in the restricted zone for 5 seconds at 30fps
produced ~150 near-identical `zone_intrusion` alerts for one real event. A
first pass fixed the spam with a periodic cooldown/heartbeat (fire at most
once per N seconds while active), which worked but still only produced a
stream of "still happening" pings, not something that reads as a timeline.
`RuleEngine` now models each sustained condition as an *incident*
(`_evaluate_incident`): one `event="started"` alert the frame a (track_id,
alert_type) condition first becomes true, nothing further while it stays
true, and one `event="ended"` alert — carrying `duration_seconds` — the
frame it clears. Three ways an incident closes, all handled: the condition
becomes false while the track is still visible; the track stops appearing
entirely, force-closed by `_close_stale_incidents` once it's been unseen for
`RuleConfig.history_len` frames (a track lost to the tracker never evaluates
to "false" again — it just vanishes); or processing ends while it's still
open, closed by `finalize()`, called once after the last frame in
`services/pipeline.run_video_job`. `line_breach` is deliberately exempt —
crossing a line is a one-off geometric event with no "ongoing" state to
close. Verified on the sample video: 815 alerts with the naive version, 16
with the cooldown, 8 with the incident model — and those 8 read as an actual
story (zone intrusion started at frame 2 / a dropped object started at
frame 212 on track 4, was lost 30 frames later, and reappeared as track 5 —
a real DeepSORT ID switch the timeline surfaces rather than hides / both
still-open incidents closed out when the video ended). The frontend
(`AlertFeed.tsx`) computes which incidents are still open by replaying
started/ended pairs client-side and renders them in a distinct "Active now"
section above the chronological timeline.

**Zone/line geometry scales with frame size.** The restricted-zone polygon
and perimeter line in `RuleConfig` are fractions of frame width/height, not
absolute pixels, so the same config works for a 640×360 webcam and a
3840×2160 drone clip. The original script hardcoded pixel coordinates tuned
for one specific resolution.

## Known limitations (stated on purpose, not hidden)

- **In-memory job store**: restarting the backend loses in-flight/completed
  job records (the annotated video files on disk are untouched, just the
  index to them). Fine for a demo/single-instance deployment; not for a
  multi-replica one.
- **CPU-only live inference is slow.** The live page throttles capture to
  ~5 fps for this reason. With a CUDA GPU (auto-detected at startup) it's
  comfortably real-time.
- **Pose-based "arms flaring" detection is not wired in.** `is_arms_flaring()`
  exists in `core/rules.py` as a tested pure function, but no pose-estimation
  model is part of this pipeline (the shipped model is a plain YOLOv8
  detector), so it would never receive real keypoints. Future work: add a
  YOLOv8-pose model alongside the detection model and feed its keypoints in.
- **Single fixed model.** There's no A/B or hot-swap mechanism — the model
  path is set once at startup via `IDS_MODEL_PATH`.
