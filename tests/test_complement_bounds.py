"""complement_ranges の境界・範囲外クランプの検証（GPTレビュー指摘 #1）。"""
from core.models import TimeRange, complement_ranges


def test_cut_beyond_total_is_ignored():
    # total を超える位置のカットは keep を範囲外へ伸ばさない
    segs = complement_ranges([TimeRange(12, 13)], total=10.0)
    assert [(s.start, s.end) for s in segs] == [(0.0, 10.0)]


def test_cut_partially_beyond_total_is_clamped():
    segs = complement_ranges([TimeRange(9.5, 10.3)], total=10.0)
    assert [(s.start, s.end) for s in segs] == [(0.0, 9.5)]


def test_cut_before_zero_is_clamped():
    segs = complement_ranges([TimeRange(-2, 1)], total=10.0)
    assert [(s.start, s.end) for s in segs] == [(1.0, 10.0)]


def test_overlapping_cuts_merged_in_complement():
    segs = complement_ranges([TimeRange(2, 5), TimeRange(4, 7)], total=10.0)
    assert [(s.start, s.end) for s in segs] == [(0.0, 2.0), (7.0, 10.0)]


def test_all_keep_beyond_range_dropped():
    # 完全に範囲外のカットのみ → 全区間 keep
    segs = complement_ranges([TimeRange(20, 30)], total=10.0)
    assert [(s.start, s.end) for s in segs] == [(0.0, 10.0)]
