"""In-memory async job store for the batch video-processing endpoint.

This is intentionally simple: a dict guarded by a lock, with each job run on
a daemon thread. It's enough to demo real async processing (upload -> job id
-> poll -> result) without a message broker.

Known limitation (documented, not hidden): job state is process-local and
in-memory, so it does not survive a restart and won't work if the backend is
ever scaled to multiple processes/replicas. A production deployment would
swap this for Celery/RQ + Redis or similar, without changing the API shape
(`create`, `get`, `run_in_background`) that the rest of the app depends on.
"""
from __future__ import annotations

import threading
import uuid
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path

from app.schemas.detection import Alert


@dataclass
class Job:
    id: str
    status: str = "queued"  # queued | running | done | error
    progress: float = 0.0
    total_frames: int = 0
    processed_frames: int = 0
    alerts: list[Alert] = field(default_factory=list)
    output_path: Path | None = None
    error: str | None = None


class JobStore:                       # this class is a simple in-memory job store that manages the lifecycle of jobs. It allows for creating new jobs, retrieving existing jobs by their ID, and running jobs in the background using threads. The job store uses a lock to ensure thread safety when accessing the internal job dictionary.
    def __init__(self) -> None:
        self._jobs: dict[str, Job] = {}
        self._lock = threading.Lock()

    def create(self) -> Job:
        job = Job(id=uuid.uuid4().hex)
        with self._lock:
            self._jobs[job.id] = job
        return job

    def get(self, job_id: str) -> Job | None:
        with self._lock:
            return self._jobs.get(job_id)

    def run_in_background(self, job: Job, target: Callable[[Job], None]) -> None:
        thread = threading.Thread(target=self._run, args=(job, target), daemon=True)
        thread.start()

    @staticmethod
    def _run(job: Job, target: Callable[[Job], None]) -> None:
        job.status = "running"
        try:
            target(job)
            job.status = "done"
            job.progress = 1.0
        except Exception as exc:  # noqa: BLE001 - surfaced to the client via job.error
            job.status = "error"
            job.error = str(exc)


job_store = JobStore()
