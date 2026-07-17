from core.models import EditAction, EditCandidate, MediaInfo, TimeRange
from quality.checker import QualityChecker


def _cut(a, b):
    return EditCandidate(TimeRange(a, b), EditAction.CUT, rule="silence")


def test_report_basic_metrics():
    media = MediaInfo(path="x.mp4", duration=10.0)
    keep = [TimeRange(0, 4), TimeRange(6, 10)]  # 8s 残す, 2s 削除
    report = QualityChecker().check(media, [_cut(4, 6)], keep)
    assert report.kept_duration == 8.0
    assert report.removed_duration == 2.0
    assert report.removed_ratio == 0.2
    assert report.num_cuts == 1
    assert report.num_segments == 2
    assert report.shortest_segment == 4.0
    assert report.warnings == []


def test_warns_on_high_removed_ratio():
    media = MediaInfo(path="x.mp4", duration=10.0)
    keep = [TimeRange(0, 2)]  # 8s 削除 = 80%
    report = QualityChecker({"max_removed_ratio": 0.6}).check(media, [_cut(2, 10)], keep)
    assert any("削除率" in w for w in report.warnings)


def test_warns_on_all_cut():
    media = MediaInfo(path="x.mp4", duration=10.0)
    report = QualityChecker().check(media, [_cut(0, 10)], [])
    assert any("全カット" in w for w in report.warnings)


def test_warns_on_short_segments():
    media = MediaInfo(path="x.mp4", duration=10.0)
    keep = [TimeRange(0, 9.7), TimeRange(9.7, 10.0)]  # 0.3s の短区間
    report = QualityChecker({"warn_min_segment_sec": 0.5}).check(media, [], keep)
    assert any("短い残り区間" in w for w in report.warnings)


def test_report_serializable():
    media = MediaInfo(path="x.mp4", duration=10.0)
    d = QualityChecker().check(media, [], [TimeRange(0, 10)]).to_dict()
    assert d["ai_assisted"] is False
    assert d["num_segments"] == 1
