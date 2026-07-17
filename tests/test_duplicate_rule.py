from audio.transcribe import Word
from core.models import AnalysisResult, EditAction, MediaInfo
from rules.duplicate_rule import DuplicateRule


def _analysis(words):
    media = MediaInfo(path="x.mp4", duration=100.0, has_audio=True)
    r = AnalysisResult(media=media)
    r.data["words"] = words
    return r


def test_single_word_repeat():
    words = [Word(0.0, 0.4, "これ"), Word(0.4, 0.8, "これ"), Word(0.8, 1.2, "は")]
    cands = DuplicateRule().apply(_analysis(words))
    assert len(cands) == 1
    assert cands[0].action == EditAction.CUT
    assert cands[0].time_range.start == 0.0 and cands[0].time_range.end == 0.4


def test_multi_word_phrase_repeat():
    words = [Word(0, 0.5, "今日"), Word(0.5, 0.8, "は"),
             Word(0.8, 1.3, "今日"), Word(1.3, 1.6, "は"), Word(1.6, 2.0, "晴れ")]
    cands = DuplicateRule().apply(_analysis(words))
    assert len(cands) == 1
    # 最初の "今日は" をカット
    assert cands[0].time_range.start == 0.0 and cands[0].time_range.end == 0.8
    assert "今日は" in cands[0].reason


def test_no_duplicate():
    words = [Word(0, 0.5, "今日"), Word(0.5, 1.0, "は"), Word(1.0, 1.5, "晴れ")]
    assert DuplicateRule().apply(_analysis(words)) == []


def test_triple_repeat_yields_two_cuts():
    words = [Word(0, 0.4, "あ"), Word(0.4, 0.8, "あ"), Word(0.8, 1.2, "あ")]
    # 1語重複を順次: (0,1)をカット→iは1へ、(1,2)は? i+=w=1 → i=1: words[1],words[2] "あ"=="あ" → もう1件
    cands = DuplicateRule({"max_words": 1}).apply(_analysis(words))
    assert len(cands) == 2
