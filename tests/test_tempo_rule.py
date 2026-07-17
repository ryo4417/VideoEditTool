from core.models import AnalysisResult, EditAction, MediaInfo, TimeRange
from rules.tempo_rule import TempoRule


def _analysis_with_silences(*ranges):
    media = MediaInfo(path="x.mp4", duration=100.0, has_audio=True)
    r = AnalysisResult(media=media)
    r.add("silence", [TimeRange(a, b) for a, b in ranges])
    return r


def test_long_gap_trimmed_to_target():
    rule = TempoRule({"target_pause_sec": 0.4, "min_gap_sec": 0.6})
    cands = rule.apply(_analysis_with_silences((3.0, 5.0)))  # 2秒の間
    assert len(cands) == 1
    c = cands[0]
    assert c.action == EditAction.CUT and c.rule == "tempo"
    assert round(c.time_range.start, 3) == 3.4   # 先頭に0.4残す
    assert c.time_range.end == 5.0


def test_short_gap_not_touched():
    rule = TempoRule({"target_pause_sec": 0.4, "min_gap_sec": 0.6})
    assert rule.apply(_analysis_with_silences((3.0, 3.5))) == []  # 0.5s <= min_gap


def test_no_silence_no_candidates():
    media = MediaInfo(path="x.mp4", duration=10.0, has_audio=True)
    assert TempoRule().apply(AnalysisResult(media=media)) == []
