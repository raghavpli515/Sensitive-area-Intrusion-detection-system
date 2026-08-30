"""Small IO helpers shared by the upload and processing paths."""
from __future__ import annotations

from pathlib import Path
from typing import BinaryIO

_CHUNK_SIZE = 1024 * 1024  # 1 MiB


class UploadTooLarge(Exception):
    """Raised mid-stream, before the whole oversized file is ever fully
    written to disk."""


def save_upload(file_obj: BinaryIO, destination: Path, max_bytes: int | None = None) -> Path:
    """Stream an uploaded file to disk without loading it fully into memory.

    Enforces `max_bytes` (if given) as it streams, rather than checking the
    size only after the whole file has already landed on disk — an
    unauthenticated upload endpoint with no cap at all is a disk-exhaustion
    vector, and checking only after-the-fact still writes the full oversized
    file first.
    """
    destination.parent.mkdir(parents=True, exist_ok=True)
    written = 0
    try:
        with destination.open("wb") as out:
            while chunk := file_obj.read(_CHUNK_SIZE):
                written += len(chunk)
                if max_bytes is not None and written > max_bytes:
                    raise UploadTooLarge(
                        f"Upload exceeds the {max_bytes / (1024 * 1024):.0f}MB limit"
                    )
                out.write(chunk)
    except UploadTooLarge:
        destination.unlink(missing_ok=True)
        raise
    return destination
