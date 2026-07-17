"""EDL のフレーム整合性（Agent#1 #2: src長とrec長の不一致を防ぐ）。"""
import re

from core.models import MediaInfo, TimeRange
from export.exporters import _fps_int, _frames_to_tc, export_edl


def _tc_to_frames(tc: str, fps_i: int) -> int:
    h, m, s, f = (int(x) for x in tc.split(":"))
    return ((h * 3600 + m * 60 + s) * fps_i) + f


def test_edl_src_length_equals_rec_length(tmp_path):
    # 端数のある区間でも src長==rec長（フレーム単位）を保証する
    media = MediaInfo(path="x.mp4", duration=10.0, fps=25.0)
    keep = [TimeRange(0, 1.017), TimeRange(2.033, 3.55), TimeRange(4.1, 5.62)]
    out = str(tmp_path / "x.edl")
    export_edl(media, keep, out)
    text = open(out, encoding="utf-8").read()

    fps_i = _fps_int(25.0)
    edit_lines = [ln for ln in text.splitlines() if re.match(r"^\d{3}\s", ln)]
    assert len(edit_lines) == 3
    for ln in edit_lines:
        tcs = re.findall(r"\d{2}:\d{2}:\d{2}:\d{2}", ln)
        src_in, src_out, rec_in, rec_out = tcs
        src_len = _tc_to_frames(src_out, fps_i) - _tc_to_frames(src_in, fps_i)
        rec_len = _tc_to_frames(rec_out, fps_i) - _tc_to_frames(rec_in, fps_i)
        assert src_len == rec_len  # プレーンカットは長さ一致が必須


def test_edl_records_are_contiguous(tmp_path):
    media = MediaInfo(path="x.mp4", duration=10.0, fps=30.0)
    keep = [TimeRange(0, 2.0), TimeRange(5.0, 6.5)]
    out = str(tmp_path / "x.edl")
    export_edl(media, keep, out)
    text = open(out, encoding="utf-8").read()
    fps_i = _fps_int(30.0)
    recs = []
    for ln in text.splitlines():
        if re.match(r"^\d{3}\s", ln):
            tcs = re.findall(r"\d{2}:\d{2}:\d{2}:\d{2}", ln)
            recs.append((_tc_to_frames(tcs[2], fps_i), _tc_to_frames(tcs[3], fps_i)))
    # 記録トラックは隙間なく連続（前のrec_out == 次のrec_in）
    for (_, prev_out), (nxt_in, _) in zip(recs, recs[1:]):
        assert prev_out == nxt_in
