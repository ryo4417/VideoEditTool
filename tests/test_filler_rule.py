from audio.transcribe import Word
from core.models import AnalysisResult, EditAction, MediaInfo
from rules.filler_rule import FillerRule


def _analysis_with_words(words):
    media = MediaInfo(path="x.mp4", duration=100.0, has_audio=True)
    result = AnalysisResult(media=media)
    result.data["words"] = words
    return result


def test_detects_filler_words():
    words = [
        Word(0.0, 0.5, "えー"),
        Word(0.5, 1.0, "今日"),
        Word(1.0, 1.4, "は"),
        Word(1.4, 1.9, "あの"),
        Word(1.9, 2.5, "晴れ"),
    ]
    candidates = FillerRule({"words": ["えー", "あの"]}).apply(_analysis_with_words(words))
    assert len(candidates) == 2
    assert all(c.action == EditAction.CUT and c.rule == "filler" for c in candidates)
    assert candidates[0].time_range.start == 0.0 and candidates[0].time_range.end == 0.5


def test_normalization_ignores_punctuation_and_case():
    words = [Word(0.0, 0.5, "えー、"), Word(1.0, 1.3, "UM")]
    candidates = FillerRule({"words": ["えー", "um"]}).apply(_analysis_with_words(words))
    assert len(candidates) == 2


def test_padding_applied():
    words = [Word(2.0, 2.4, "えっと")]
    candidates = FillerRule({"words": ["えっと"], "padding_sec": 0.1}).apply(_analysis_with_words(words))
    assert candidates[0].time_range.start == 1.9
    assert round(candidates[0].time_range.end, 3) == 2.5


def test_no_words_no_candidates():
    media = MediaInfo(path="x.mp4", duration=10.0, has_audio=True)
    assert FillerRule().apply(AnalysisResult(media=media)) == []
