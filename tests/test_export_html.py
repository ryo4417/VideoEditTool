from core.models import EditAction, EditCandidate, MediaInfo, TimeRange
from export.exporters import build_html


def _report():
    return {
        "total_duration": 10.0, "kept_duration": 8.0, "removed_ratio": 0.2,
        "num_cuts": 1, "num_segments": 2, "warnings": ["短い残り区間が 1 件あります"],
    }


def test_build_html_contains_core_elements():
    media = MediaInfo(path="dir/sample.mp4", duration=10.0)
    candidates = [EditCandidate(TimeRange(4, 6), EditAction.CUT, rule="silence", reason="無音 2.0s")]
    keep = [TimeRange(0, 4), TimeRange(6, 10)]
    doc = build_html(media, candidates, keep, _report())

    assert "<!doctype html>" in doc
    assert "sample.mp4" in doc
    assert "無音 2.0s" in doc          # 候補テーブル
    assert "短い残り区間" in doc        # 警告
    assert "seg keep" in doc and "seg cut" in doc  # タイムライン帯
    assert "20%" in doc                # 削除率


def test_build_html_escapes_reason():
    media = MediaInfo(path="x.mp4", duration=10.0)
    candidates = [EditCandidate(TimeRange(1, 2), EditAction.CUT, rule="r", reason="<script>")]
    doc = build_html(media, candidates, [TimeRange(0, 1)], _report())
    assert "<script>" not in doc
    assert "&lt;script&gt;" in doc
