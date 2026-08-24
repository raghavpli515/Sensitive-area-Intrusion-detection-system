"""Regression test for the silent-broken-video bug: a video job that
completed successfully but produced a file browsers couldn't play (MPEG-4
Part 2 instead of H.264), with no error surfaced anywhere. The fix must fail
loudly instead."""
from __future__ import annotations

from unittest.mock import patch

import pytest

from app.services.pipeline import _transcode_to_browser_compatible_mp4


def test_transcode_raises_clear_error_when_ffmpeg_missing(tmp_path):
    raw_path = tmp_path / "raw.mp4"
    raw_path.write_bytes(b"placeholder - content doesn't matter for this test")
    output_path = tmp_path / "out.mp4"

    with patch("app.services.pipeline.shutil.which", return_value=None):
        with pytest.raises(RuntimeError, match="ffmpeg is required"):
            _transcode_to_browser_compatible_mp4(raw_path, output_path)


def test_transcode_raises_on_ffmpeg_failure(tmp_path):
    raw_path = tmp_path / "raw.mp4"
    raw_path.write_bytes(b"not a real video - ffmpeg should reject this")
    output_path = tmp_path / "out.mp4"

    with pytest.raises(RuntimeError, match="ffmpeg transcode"):
        _transcode_to_browser_compatible_mp4(raw_path, output_path)

    assert not output_path.exists()
