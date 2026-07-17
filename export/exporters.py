"""書き出しエンジン。

編集結果を各種フォーマットへ出力する。format ごとに独立し交換可能。
- json : keep/cut 区間の一覧（他ツール連携・確認用）
- edl  : CMX3600 風の簡易 EDL
- ffmpeg: keep 区間を実際に連結して動画出力（render=true 時）
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import List

from core import ffmpeg
from core.models import EditCandidate, MediaInfo, TimeRange


def _timecode(seconds: float, fps: float) -> str:
    """秒を HH:MM:SS:FF に変換（fps 不明時は 25 と仮定）。"""
    fps = fps if fps and fps > 0 else 25.0
    total_frames = round(seconds * fps)
    frames = int(total_frames % round(fps))
    total_sec = total_frames // round(fps)
    s = total_sec % 60
    m = (total_sec // 60) % 60
    h = total_sec // 3600
    return f"{h:02d}:{m:02d}:{s:02d}:{frames:02d}"


def export_json(
    media: MediaInfo,
    candidates: List[EditCandidate],
    keep_segments: List[TimeRange],
    output_path: str,
) -> str:
    payload = {
        "source": media.path,
        "duration": media.duration,
        "keep_segments": [
            {"start": s.start, "end": s.end, "duration": s.duration}
            for s in keep_segments
        ],
        "candidates": [
            {
                "action": c.action.value,
                "rule": c.rule,
                "start": c.time_range.start,
                "end": c.time_range.end,
                "reason": c.reason,
                "confidence": c.confidence,
            }
            for c in candidates
        ],
    }
    Path(output_path).write_text(
        json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return output_path


def export_report(report_dict: dict, output_path: str) -> str:
    Path(output_path).write_text(
        json.dumps(report_dict, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return output_path


def export_edl(media: MediaInfo, keep_segments: List[TimeRange], output_path: str) -> str:
    lines = ["TITLE: VideoEditTool Export", "FCM: NON-DROP FRAME", ""]
    record = 0.0
    for i, seg in enumerate(keep_segments, start=1):
        src_in = _timecode(seg.start, media.fps)
        src_out = _timecode(seg.end, media.fps)
        rec_in = _timecode(record, media.fps)
        rec_out = _timecode(record + seg.duration, media.fps)
        lines.append(f"{i:03d}  AX       V     C        {src_in} {src_out} {rec_in} {rec_out}")
        record += seg.duration
    Path(output_path).write_text("\n".join(lines) + "\n", encoding="utf-8")
    return output_path


def render(media: MediaInfo, keep_segments: List[TimeRange], output_path: str) -> str:
    ffmpeg.render_cuts(media.path, keep_segments, output_path)
    return output_path
