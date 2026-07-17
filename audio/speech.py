"""発話区間アナライザ（最低限動く版）。

発話 = 無音の補集合、として発話区間を求める。AIは使わない（仕様書 §9）。
将来は VAD / エネルギー解析へ差し替え可能（改善は improve-audio 参照）。
"""
from __future__ import annotations

from core import ffmpeg
from core.analyzer import BaseAnalyzer
from core.models import AnalysisResult, MediaInfo, complement_ranges
from core.registry import ANALYZERS

DEFAULT_NOISE_DB = -30.0
DEFAULT_MIN_SILENCE_SEC = 0.5
DEFAULT_MIN_SPEECH_SEC = 0.2


@ANALYZERS.register("speech")
class SpeechAnalyzer(BaseAnalyzer):
    feature = "speech"

    def analyze(self, media: MediaInfo, result: AnalysisResult) -> None:
        if not media.has_audio:
            return
        # 既に silence アナライザが走っていればその結果を再利用（重複処理回避）。
        silences = result.get("silence")
        if not silences:
            noise_db = float(self.options.get("noise_threshold_db", DEFAULT_NOISE_DB))
            min_sec = float(self.options.get("min_silence_sec", DEFAULT_MIN_SILENCE_SEC))
            silences = ffmpeg.detect_silence(media.path, noise_db, min_sec)

        min_speech = float(self.options.get("min_speech_sec", DEFAULT_MIN_SPEECH_SEC))
        speech = [
            seg
            for seg in complement_ranges(silences, media.duration)
            if seg.duration >= min_speech
        ]
        result.add(self.feature, speech)
