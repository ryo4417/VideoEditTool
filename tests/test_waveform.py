"""波形抽出の検証（ffmpeg が必要な統合テスト）。"""
import shutil

import pytest

from core import ffmpeg

pytestmark = pytest.mark.skipif(
    shutil.which("ffmpeg") is None or shutil.which("ffprobe") is None,
    reason="ffmpeg/ffprobe が無い環境ではスキップ",
)


def _make_tone(tmp_path):
    out = str(tmp_path / "tone.wav")
    import subprocess
    subprocess.run(
        ["ffmpeg", "-y", "-v", "error", "-f", "lavfi",
         "-i", "sine=frequency=440:duration=2", out],
        check=True,
    )
    return out


def test_waveform_returns_normalized_peaks(tmp_path):
    peaks = ffmpeg.extract_waveform(_make_tone(tmp_path), buckets=100)
    assert 0 < len(peaks) <= 100
    assert all(0.0 <= p <= 1.0 for p in peaks)
    assert max(peaks) == pytest.approx(1.0, abs=1e-6)  # 正規化で最大=1


def test_waveform_zero_buckets():
    assert ffmpeg.extract_waveform("x.mp4", buckets=0) == []
