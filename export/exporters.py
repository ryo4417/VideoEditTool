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
from xml.sax.saxutils import quoteattr

from core import ffmpeg
from core.models import EditAction, EditCandidate, MediaInfo, TimeRange


DEFAULT_FPS = 25  # fps 不明時のフォールバック


def _fps_int(fps: float) -> int:
    return int(round(fps)) if fps and fps > 0 else DEFAULT_FPS


def _frames_to_tc(total_frames: int, fps_i: int) -> str:
    """フレーム数を HH:MM:SS:FF に変換。"""
    frames = total_frames % fps_i
    total_sec = total_frames // fps_i
    return f"{total_sec // 3600:02d}:{(total_sec // 60) % 60:02d}:{total_sec % 60:02d}:{frames:02d}"


def _timecode(seconds: float, fps: float) -> str:
    """秒を HH:MM:SS:FF に変換（fps 不明時は DEFAULT_FPS）。"""
    fps_i = _fps_int(fps)
    return _frames_to_tc(round(seconds * fps_i), fps_i)


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
    fps_i = _fps_int(media.fps)
    lines = ["TITLE: VideoEditTool Export", "FCM: NON-DROP FRAME", ""]
    rec_frames = 0
    for i, seg in enumerate(keep_segments, start=1):
        src_in_f = round(seg.start * fps_i)
        src_out_f = round(seg.end * fps_i)
        length_f = src_out_f - src_in_f  # 記録側の長さはソース側フレーム長から導出（一致保証）
        src_in = _frames_to_tc(src_in_f, fps_i)
        src_out = _frames_to_tc(src_out_f, fps_i)
        rec_in = _frames_to_tc(rec_frames, fps_i)
        rec_out = _frames_to_tc(rec_frames + length_f, fps_i)
        lines.append(f"{i:03d}  AX       V     C        {src_in} {src_out} {rec_in} {rec_out}")
        rec_frames += length_f
    Path(output_path).write_text("\n".join(lines) + "\n", encoding="utf-8")
    return output_path


def _file_uri(path: str) -> str:
    try:
        return Path(path).absolute().as_uri()
    except (ValueError, OSError):
        return path


def build_fcpxml(media: MediaInfo, keep_segments: List[TimeRange]) -> str:
    """簡易 FCPXML(v1.9) を組み立てる（NLE連携の最低限動く版）。

    keep 区間を spine 上の asset-clip として並べる。offset=タイムライン位置、
    start=素材の頭出し、duration=区間長。時間は秒(小数)表記。
    """
    fps = _fps_int(media.fps)
    name = Path(media.path).stem
    width = media.width or 1920
    height = media.height or 1080

    # FCPXML は有理数時刻(N/fps s)＝フレーム境界に厳格。小数秒累積のドリフトを避ける。
    clips: List[str] = []
    offset_f = 0
    for seg in keep_segments:
        start_f = round(seg.start * fps)
        length_f = round(seg.end * fps) - start_f
        clips.append(
            f'        <asset-clip ref="r2" name={quoteattr(name)} '
            f'offset="{offset_f}/{fps}s" start="{start_f}/{fps}s" duration="{length_f}/{fps}s"/>'
        )
        offset_f += length_f
    total_f = offset_f
    dur_f = round(media.duration * fps)

    return (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        "<!DOCTYPE fcpxml>\n"
        '<fcpxml version="1.9">\n'
        "  <resources>\n"
        f'    <format id="r1" name="FFVideoFormat" frameDuration="1/{fps}s" '
        f'width="{width}" height="{height}"/>\n'
        f'    <asset id="r2" name={quoteattr(name)} start="0s" '
        f'duration="{dur_f}/{fps}s" hasVideo="1" hasAudio="1" format="r1">\n'
        f"      <media-rep kind=\"original-media\" src={quoteattr(_file_uri(media.path))}/>\n"
        "    </asset>\n"
        "  </resources>\n"
        "  <library>\n"
        '    <event name="VideoEditTool">\n'
        f"      <project name={quoteattr(name + ' (edited)')}>\n"
        f'        <sequence format="r1" duration="{total_f}/{fps}s">\n'
        "          <spine>\n"
        + "\n".join(clips)
        + "\n          </spine>\n"
        "        </sequence>\n"
        "      </project>\n"
        "    </event>\n"
        "  </library>\n"
        "</fcpxml>\n"
    )


def export_fcpxml(media: MediaInfo, keep_segments: List[TimeRange], output_path: str) -> str:
    Path(output_path).write_text(build_fcpxml(media, keep_segments), encoding="utf-8")
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
