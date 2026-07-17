from core.models import AnalysisResult, EditAction, MediaInfo, TimeRange
from rules.silence_rule import SilenceRule


def _analysis_with_silences(*ranges):
    media = MediaInfo(path="x.mp4", duration=100.0, has_audio=True)
    result = AnalysisResult(media=media)
    result.add("silence", [TimeRange(a, b) for a, b in ranges])
    return result


def test_long_silence_becomes_cut():
    rule = SilenceRule({"min_cut_sec": 0.5, "keep_padding_sec": 0.1})
    candidates = rule.apply(_analysis_with_silences((10.0, 12.0)))
    assert len(candidates) == 1
    c = candidates[0]
    assert c.action == EditAction.CUT
    # padding 分内側に寄る
    assert c.time_range.start == 10.1
    assert c.time_range.end == 11.9


def test_short_silence_ignored():
    rule = SilenceRule({"min_cut_sec": 0.5, "keep_padding_sec": 0.1})
    # padding 差引後 0.3s < 0.5s → 除外
    candidates = rule.apply(_analysis_with_silences((10.0, 10.5)))
    assert candidates == []


def test_padding_respects_config():
    rule = SilenceRule({"min_cut_sec": 0.1, "keep_padding_sec": 0.0})
    candidates = rule.apply(_analysis_with_silences((5.0, 6.0)))
    assert candidates[0].time_range.start == 5.0
    assert candidates[0].time_range.end == 6.0
