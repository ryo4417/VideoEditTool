"""無音検出アナライザ。

ffmpeg の silencedetect を用いて無音区間を検出し、
AnalysisResult に "silence" 特徴として記録する。AIは使わない（仕様書 §9）。
"""
from __future__ import annotations

from core import ffmpeg
from core.analyzer import BaseAnalyzer
from core.models import AnalysisResult, MediaInfo
from core.registry import ANALYZERS

# 既定値（config 未指定時のフォールバック）。マジックナンバーは定数化する。
DEFAULT_NOISE_DB = -30.0
DEFAULT_MIN_SILENCE_SEC = 0.5


@ANALYZERS.register("silence")
class SilenceAnalyzer(BaseAnalyzer):
    feature = "silence"

    def analyze(self, media: MediaInfo, result: AnalysisResult) -> None:
        if not media.has_audio:
            return
        noise_db = float(self.options.get("noise_threshold_db", DEFAULT_NOISE_DB))
        min_sec = float(self.options.get("min_silence_sec", DEFAULT_MIN_SILENCE_SEC))
        silences = ffmpeg.detect_silence(media.path, noise_db, min_sec)
        result.add(self.feature, silences)
