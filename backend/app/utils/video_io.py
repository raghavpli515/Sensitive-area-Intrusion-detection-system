"""Small IO helpers shared by the upload and processing paths."""
from __future__ import annotations

import shutil
from pathlib import Path
from typing import BinaryIO


def save_upload(file_obj: BinaryIO, destination: Path) -> Path:
    """Stream an uploaded file to disk without loading it fully into memory."""
    destination.parent.mkdir(parents=True, exist_ok=True)
    with destination.open("wb") as out:    
        shutil.copyfileobj(file_obj, out)  
    return destination
