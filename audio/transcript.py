"""文字起こしアナライザ。

ローカル Whisper で発話内容を文字起こしし、単語列を
AnalysisResult.data["words"] に、発話区間を features["speech_text"] に記録する。
これによりフィラー/言い直し等の内容ベースのルールが可能になる。
"""
from __future__ import annotations

from audio.transcribe import Word, get_transcriber
from core.analyzer import BaseAnalyzer
from core.models import AnalysisResult, MediaInfo, TimeRange
from core.registry import ANALYZERS


@ANALYZERS.register("transcript")
class TranscriptAnalyzer(BaseAnalyzer):
    feature = "speech_text"

    def analyze(self, media: MediaInfo, result: AnalysisResult) -> None:
        if not media.has_audio:
            return
        transcriber = get_transcriber(self.options)
        words = transcriber.transcribe(media.path)
        result.data["words"] = words
        result.add(self.feature, [TimeRange(w.start, w.end) for w in words])
