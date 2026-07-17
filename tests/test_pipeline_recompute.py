from core.config import load_config
from core.models import AnalysisResult, EditAction, EditCandidate, MediaInfo, TimeRange
from pipeline import Pipeline, PipelineResult
from quality.checker import QualityChecker


def _result(media, candidates):
    keep = [TimeRange(0, media.duration)]
    report = QualityChecker().check(media, candidates, keep)
    return PipelineResult(media=media, analysis=AnalysisResult(media=media),
                          candidates=candidates, keep_segments=keep, report=report)


def test_recompute_keeps_only_enabled_candidates():
    media = MediaInfo(path="x.mp4", duration=10.0)
    cands = [
        EditCandidate(TimeRange(2, 3), EditAction.CUT, "silence"),
        EditCandidate(TimeRange(5, 6), EditAction.CUT, "silence"),
    ]
    pipe = Pipeline(load_config())
    result = _result(media, cands)

    # index 0 のみ有効 → keep は 0-2, 3-10（5-6 はカットしない）
    recomputed = pipe.recompute(result, [0])
    assert len(recomputed.candidates) == 1
    segs = [(round(s.start, 1), round(s.end, 1)) for s in recomputed.keep_segments]
    assert segs == [(0.0, 2.0), (3.0, 10.0)]


def test_recompute_none_enabled_keeps_full_clip():
    media = MediaInfo(path="x.mp4", duration=10.0)
    cands = [EditCandidate(TimeRange(2, 3), EditAction.CUT, "silence")]
    recomputed = Pipeline(load_config()).recompute(_result(media, cands), [])
    assert recomputed.candidates == []
    assert [(s.start, s.end) for s in recomputed.keep_segments] == [(0.0, 10.0)]


def test_recompute_ignores_out_of_range_indices():
    media = MediaInfo(path="x.mp4", duration=10.0)
    cands = [EditCandidate(TimeRange(2, 3), EditAction.CUT, "silence")]
    recomputed = Pipeline(load_config()).recompute(_result(media, cands), [0, 99])
    assert len(recomputed.candidates) == 1
