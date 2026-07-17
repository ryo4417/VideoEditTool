from core.models import AnalysisResult, MediaInfo, TimeRange, complement_ranges
from audio.speech import SpeechAnalyzer


def test_complement_ranges_basic():
    silences = [TimeRange(2, 3), TimeRange(5, 6)]
    speech = complement_ranges(silences, total=10.0)
    assert [(s.start, s.end) for s in speech] == [(0, 2), (3, 5), (6, 10)]


def test_complement_ranges_empty():
    # 無音なし → 全区間が発話
    assert [(s.start, s.end) for s in complement_ranges([], 10.0)] == [(0.0, 10.0)]


def test_speech_analyzer_reuses_silence():
    media = MediaInfo(path="x.mp4", duration=10.0, has_audio=True)
    result = AnalysisResult(media=media)
    result.add("silence", [TimeRange(2, 3), TimeRange(5, 6)])
    SpeechAnalyzer({"min_speech_sec": 0.2}).analyze(media, result)
    speech = result.get("speech")
    assert [(s.start, s.end) for s in speech] == [(0, 2), (3, 5), (6, 10)]


def test_speech_analyzer_filters_short_fragments():
    media = MediaInfo(path="x.mp4", duration=10.0, has_audio=True)
    result = AnalysisResult(media=media)
    # 無音 2-2.1, 2.2-10 → 発話 0-2, 2.1-2.2(0.1s 除外)
    result.add("silence", [TimeRange(2.0, 2.1), TimeRange(2.2, 10.0)])
    SpeechAnalyzer({"min_speech_sec": 0.2}).analyze(media, result)
    speech = result.get("speech")
    assert [(round(s.start, 1), round(s.end, 1)) for s in speech] == [(0.0, 2.0)]


def test_speech_analyzer_skips_when_no_audio():
    media = MediaInfo(path="x.mp4", duration=10.0, has_audio=False)
    result = AnalysisResult(media=media)
    SpeechAnalyzer().analyze(media, result)
    assert result.get("speech") == []
