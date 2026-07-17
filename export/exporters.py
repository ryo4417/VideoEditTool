"""書き出しエンジン。

編集結果を各種フォーマットへ出力する。format ごとに独立し交換可能。
- json : keep/cut 区間の一覧（他ツール連携・確認用）
- edl  : CMX3600 風の簡易 EDL
- ffmpeg: keep 区間を実際に連結して動画出力（render=true 時）
"""
from __future__ import annotations

import html
import json
from pathlib import Path
from typing import List

from core import ffmpeg
from core.models import EditAction, EditCandidate, MediaInfo, TimeRange


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


def _pct(value: float, total: float) -> float:
    return (value / total * 100.0) if total > 0 else 0.0


def build_html(
    media: MediaInfo,
    candidates: List[EditCandidate],
    keep_segments: List[TimeRange],
    report_dict: dict,
) -> str:
    """編集確認用の自己完結HTMLを組み立てて返す（外部依存なし）。"""
    total = media.duration or 1.0

    # タイムライン帯: keep(緑)/cut(赤) を割合配置。
    bars: List[str] = []
    for seg in keep_segments:
        bars.append(
            f'<div class="seg keep" style="left:{_pct(seg.start, total):.3f}%;'
            f'width:{_pct(seg.duration, total):.3f}%" title="残す {seg.start:.2f}-{seg.end:.2f}s"></div>'
        )
    for c in candidates:
        if c.action == EditAction.CUT:
            bars.append(
                f'<div class="seg cut" style="left:{_pct(c.time_range.start, total):.3f}%;'
                f'width:{_pct(c.time_range.duration, total):.3f}%" '
                f'title="カット {c.time_range.start:.2f}-{c.time_range.end:.2f}s"></div>'
            )

    rows: List[str] = []
    for c in candidates:
        rows.append(
            "<tr>"
            f"<td>{html.escape(c.action.value)}</td>"
            f"<td>{html.escape(c.rule)}</td>"
            f"<td>{c.time_range.start:.2f}</td>"
            f"<td>{c.time_range.end:.2f}</td>"
            f"<td>{c.time_range.duration:.2f}</td>"
            f"<td>{html.escape(c.reason)}</td>"
            "</tr>"
        )

    warnings = "".join(f"<li>{html.escape(w)}</li>" for w in report_dict.get("warnings", []))
    warnings_block = f'<ul class="warn">{warnings}</ul>' if warnings else '<p class="ok">警告なし</p>'

    return f"""<!doctype html>
<html lang="ja"><head><meta charset="utf-8">
<title>編集レポート — {html.escape(Path(media.path).name)}</title>
<style>
  body {{ font-family: system-ui, sans-serif; margin: 2rem; color: #1a1a1a; }}
  h1 {{ font-size: 1.3rem; }}
  .bar {{ position: relative; height: 34px; background: #e5e7eb; border-radius: 6px; overflow: hidden; margin: 1rem 0; }}
  .seg {{ position: absolute; top: 0; height: 100%; }}
  .seg.keep {{ background: #16a34a; }}
  .seg.cut {{ background: #dc2626; }}
  .legend span {{ display:inline-block; margin-right:1rem; font-size:.85rem; }}
  .sw {{ display:inline-block; width:12px; height:12px; border-radius:2px; vertical-align:middle; margin-right:4px; }}
  table {{ border-collapse: collapse; width: 100%; font-size:.9rem; }}
  th, td {{ border: 1px solid #d1d5db; padding: 4px 8px; text-align: left; }}
  th {{ background: #f3f4f6; }}
  .warn {{ color: #b45309; }} .ok {{ color: #16a34a; }}
  .metrics {{ display:flex; gap:1.5rem; flex-wrap:wrap; }}
  .metrics div {{ background:#f9fafb; border:1px solid #e5e7eb; border-radius:6px; padding:.5rem .9rem; }}
</style></head><body>
<h1>編集レポート: {html.escape(Path(media.path).name)}</h1>
<div class="metrics">
  <div>総尺 <b>{report_dict.get('total_duration', 0):.1f}s</b></div>
  <div>残時間 <b>{report_dict.get('kept_duration', 0):.1f}s</b></div>
  <div>削除率 <b>{report_dict.get('removed_ratio', 0):.0%}</b></div>
  <div>カット <b>{report_dict.get('num_cuts', 0)}</b></div>
  <div>残区間 <b>{report_dict.get('num_segments', 0)}</b></div>
</div>
<div class="bar">{''.join(bars)}</div>
<div class="legend"><span><i class="sw" style="background:#16a34a"></i>残す</span>
<span><i class="sw" style="background:#dc2626"></i>カット</span></div>
<h2 style="font-size:1rem">品質チェック</h2>
{warnings_block}
<h2 style="font-size:1rem">編集候補</h2>
<table><thead><tr><th>操作</th><th>ルール</th><th>開始</th><th>終了</th><th>長さ</th><th>理由</th></tr></thead>
<tbody>{''.join(rows) or '<tr><td colspan=6>候補なし</td></tr>'}</tbody></table>
</body></html>
"""


def export_html(
    media: MediaInfo,
    candidates: List[EditCandidate],
    keep_segments: List[TimeRange],
    report_dict: dict,
    output_path: str,
) -> str:
    Path(output_path).write_text(
        build_html(media, candidates, keep_segments, report_dict), encoding="utf-8"
    )
    return output_path
