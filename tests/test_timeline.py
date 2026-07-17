from core.models import EditAction, EditCandidate, MediaInfo, TimeRange
from timeline.manager import TimelineManager


def _cut(a, b):
    return EditCandidate(TimeRange(a, b), EditAction.CUT, rule="silence")


def test_build_and_refine_removes_short_segments():
    media = MediaInfo(path="x.mp4", duration=10.0)
    mgr = TimelineManager({"merge_gap_sec": 0.0, "min_segment_sec": 0.5})
    # cut 0-2, 2.1-9.9 → keep: 2-2.1(0.1s 除去), 9.9-10(0.1s 除去) だけ残らない
    tl = mgr.build(media, [_cut(0, 2), _cut(2.1, 9.9)])
    keeps = mgr.refine_keep_segments(tl)
    assert keeps == []


def test_merge_close_segments():
    media = MediaInfo(path="x.mp4", duration=10.0)
    mgr = TimelineManager({"merge_gap_sec": 0.3, "min_segment_sec": 0.0})
    # cut 2-2.2 のみ → keep 0-2, 2.2-10。gap 0.2 <= 0.3 なので結合され 0-10
    tl = mgr.build(media, [_cut(2.0, 2.2)])
    keeps = mgr.refine_keep_segments(tl)
    assert [(k.start, k.end) for k in keeps] == [(0.0, 10.0)]
