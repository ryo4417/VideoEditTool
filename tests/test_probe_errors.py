import shutil

import pytest

from core import ffmpeg
from core.ffmpeg import MediaProbeError

pytestmark = pytest.mark.skipif(
    shutil.which("ffprobe") is None, reason="ffprobe が無い環境ではスキップ"
)


def test_probe_missing_file_raises_clean_error():
    with pytest.raises(MediaProbeError):
        ffmpeg.probe("does_not_exist_12345.mp4")


def test_probe_non_media_file_raises_clean_error(tmp_path):
    f = tmp_path / "notavideo.txt"
    f.write_text("hello", encoding="utf-8")
    with pytest.raises(MediaProbeError):
        ffmpeg.probe(str(f))
