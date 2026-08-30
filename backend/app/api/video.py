"""Batch video inference: upload a file, get a job id, poll for progress,
then fetch the annotated result. Processing runs on a background thread so
the upload request returns immediately instead of blocking for the whole
video"""
from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse

from app.core.config import settings
from app.schemas.detection import JobStatus
from app.services.jobs import Job, job_store
from app.services.pipeline import run_video_job
from app.utils.video_io import UploadTooLarge, save_upload

router = APIRouter(prefix="/infer/video", tags=["Video Inference"])

_ALLOWED_EXTENSIONS = {".mp4", ".avi", ".mov"}


@router.post("", response_model=JobStatus)
async def submit_video(file: UploadFile = File(...), confidence_threshold: float = Form(0.4)):
    suffix = Path(file.filename or "").suffix.lower()
    if suffix not in _ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file extension '{suffix or 'unknown'}'. "
                    f"Allowed: {sorted(_ALLOWED_EXTENSIONS)}",
        )

    job = job_store.create()
    input_path = settings.upload_dir / f"{job.id}{suffix}"
    try:
        save_upload(file.file, input_path, max_bytes=settings.max_upload_mb * 1024 * 1024)
    except UploadTooLarge:
        raise HTTPException(
            status_code=413,
            detail=f"File exceeds the {settings.max_upload_mb}MB upload limit",
        ) from None
    output_path = settings.output_dir / f"{job.id}.mp4"

    job_store.run_in_background(
        job, lambda j: run_video_job(j, input_path, output_path, confidence_threshold)
    )

    return _to_status(job)


@router.get("/{job_id}", response_model=JobStatus)
def get_job(job_id: str):
    job = job_store.get(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")
    return _to_status(job)


@router.get("/{job_id}/file")
def get_job_file(job_id: str):
    job = job_store.get(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")
    if job.status != "done" or job.output_path is None:
        raise HTTPException(status_code=409, detail=f"Job is '{job.status}', not ready yet")
    return FileResponse(job.output_path, media_type="video/mp4")


def _to_status(job: Job) -> JobStatus:
    return JobStatus(
        job_id=job.id,
        status=job.status,
        progress=job.progress,
        error=job.error,
        total_frames=job.total_frames or None,
        processed_frames=job.processed_frames,
        alerts=job.alerts,
        output_video_url=f"/infer/video/{job.id}/file" if job.status == "done" else None,
    )
