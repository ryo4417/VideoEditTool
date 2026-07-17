from core.models import MediaInfo, TimeRange, Timeline


def test_timerange_duration():
    assert TimeRange(1.0, 3.5).duration == 2.5


def test_timerange_overlaps():
    assert TimeRange(0, 2).overlaps(TimeRange(1, 3))
    assert not TimeRange(0, 1).overlaps(TimeRange(1, 2))


def test_keep_segments_is_complement_of_cuts():
    media = MediaInfo(path="x.mp4", duration=10.0)
    tl = Timeline(media=media, cuts=[TimeRange(2, 3), TimeRange(5, 6)])
    keeps = tl.keep_segments()
    assert [(k.start, k.end) for k in keeps] == [(0, 2), (3, 5), (6, 10)]


def test_keep_segments_handles_cut_at_end():
    media = MediaInfo(path="x.mp4", duration=10.0)
    tl = Timeline(media=media, cuts=[TimeRange(8, 10)])
    keeps = tl.keep_segments()
    assert [(k.start, k.end) for k in keeps] == [(0, 8)]
