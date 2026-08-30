import io

import pytest

from app.utils.video_io import UploadTooLarge, save_upload


def test_save_upload_writes_file_within_limit(tmp_path):
    destination = tmp_path / "video.mp4"
    save_upload(io.BytesIO(b"x" * 100), destination, max_bytes=1000)

    assert destination.exists()
    assert destination.read_bytes() == b"x" * 100


def test_save_upload_rejects_oversized_file_and_cleans_up(tmp_path):
    destination = tmp_path / "video.mp4"

    with pytest.raises(UploadTooLarge):
        save_upload(io.BytesIO(b"x" * 5_000_000), destination, max_bytes=1_000_000)

    # The partial file must not be left behind on disk.
    assert not destination.exists()


def test_save_upload_with_no_limit_accepts_anything(tmp_path):
    destination = tmp_path / "video.mp4"
    save_upload(io.BytesIO(b"x" * 5_000_000), destination, max_bytes=None)

    assert destination.stat().st_size == 5_000_000
