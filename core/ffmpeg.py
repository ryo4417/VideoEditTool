"""ffmpeg / ffprobe ラッパー。

外部プロセス呼び出しをこの1箇所に閉じ込める。
他モジュールは ffmpeg のコマンド仕様を知らなくてよい（責務の局所化）。
"""
from __future__ import annotations

import array
import json
import re
import shutil
import subprocess
from typing import List

from core.models import MediaInfo, TimeRange

FFMPEG = "ffmpeg"
FFPROBE = "ffprobe"


class FFmpegNotFound(RuntimeError):
    pass


class MediaProbeError(RuntimeError):
    """メディアを読めない（破損・非対応・動画でない等）。"""


def _run(cmd, timeout, **kw):
    """タイムアウト付きで外部プロセスを実行（ハング防止）。超過は分かりやすく失敗。"""
    try:
        return subprocess.run(cmd, timeout=timeout, **kw)
    except subprocess.TimeoutExpired as e:
        raise MediaProbeError(f"処理がタイムアウトしました（{timeout}s）: {cmd[0]}") from e


def ensure_available() -> None:
    """ffmpeg / ffprobe が PATH 上にあることを確認する。"""
    for exe in (FFMPEG, FFPROBE):
        if shutil.which(exe) is None:
            raise FFmpegNotFound(
                f"{exe} が見つかりません。ffmpeg をインストールし PATH を通してください。"
            )


def probe(path: str) -> MediaInfo:
    """ffprobe でメディア情報を取得する。"""
    ensure_available()
    cmd = [
        FFPROBE, "-v", "error", "-print_format", "json",
        "-show_format", "-show_streams", path,
    ]
    # ffprobe は UTF-8 で出力する。text=True 既定のロケール(cp932 等)復号だと
    # 日本語を含むパスで JSON が壊れるため、UTF-8 を明示する。
    proc = _run(cmd, 120, capture_output=True, text=True, encoding="utf-8", errors="replace")
    if proc.returncode != 0:
        # 生のffmpeg英語エラーは補足に留め、分かりやすい日本語を主メッセージにする。
        detail = (proc.stderr or "").strip().splitlines()[-1:] or ["ffprobe が失敗しました"]
        raise MediaProbeError(
            f"このファイルは動画として読めませんでした: {path}\n"
            f"  対応形式の動画（mp4 / mov / mkv など）を指定してください。\n"
            f"  詳細: {detail[0]}"
        )
    try:
        data = json.loads(proc.stdout)
    except json.JSONDecodeError as e:
        raise MediaProbeError(f"メディア情報の解析に失敗: {path} ({e})") from e

    duration = float(data.get("format", {}).get("duration", 0.0) or 0.0)
    info = MediaInfo(path=path, duration=duration)
    for stream in data.get("streams", []):
        codec_type = stream.get("codec_type")
        if codec_type == "audio":
            info.has_audio = True
        elif codec_type == "video":
            info.has_video = True
            info.width = int(stream.get("width", 0) or 0)
            info.height = int(stream.get("height", 0) or 0)
            info.fps = _parse_fraction(stream.get("avg_frame_rate", "0/0"))
    return info


def _parse_fraction(value: str) -> float:
    try:
        num, _, den = value.partition("/")
        den_f = float(den) if den else 0.0
        return float(num) / den_f if den_f else 0.0
    except (ValueError, ZeroDivisionError):
        return 0.0


_SILENCE_START = re.compile(r"silence_start:\s*(-?\d+(?:\.\d+)?)")
_SILENCE_END = re.compile(r"silence_end:\s*(-?\d+(?:\.\d+)?)")


def detect_silence(path: str, noise_db: float, min_silence_sec: float) -> List[TimeRange]:
    """ffmpeg silencedetect フィルタで無音区間を検出する。

    noise_db: これ以下(dB)を無音とみなす閾値（例 -30）。
    min_silence_sec: これ以上続く無音のみ検出。
    """
    ensure_available()
    cmd = [
        FFMPEG, "-i", path,
        "-af", f"silencedetect=noise={noise_db}dB:d={min_silence_sec}",
        "-f", "null", "-",
    ]
    # silencedetect は stderr にログを出す。UTF-8 を明示（日本語パス対策）。
    result = _run(cmd, 1800, capture_output=True, text=True, encoding="utf-8", errors="replace")
    return _parse_silence_log(result.stderr)


def _parse_silence_log(stderr: str) -> List[TimeRange]:
    ranges: List[TimeRange] = []
    pending_start: float | None = None
    for line in stderr.splitlines():
        m_start = _SILENCE_START.search(line)
        if m_start:
            pending_start = float(m_start.group(1))
            continue
        m_end = _SILENCE_END.search(line)
        if m_end and pending_start is not None:
            end = float(m_end.group(1))
            ranges.append(TimeRange(max(0.0, pending_start), max(0.0, end)))
            pending_start = None
    return ranges


def extract_waveform(path: str, buckets: int = 400, sample_rate: int = 4000) -> List[float]:
    """音声の振幅エンベロープ（0..1 に正規化した peak 列）を返す。

    GUI のタイムライン背景に波形を描くための軽量データ。numpy 非依存
    （array モジュールで s16le mono を集計）。音声が無い/無音なら空/ゼロ列。
    """
    ensure_available()
    if buckets <= 0:
        return []
    cmd = [FFMPEG, "-v", "error", "-i", path, "-ac", "1", "-ar", str(sample_rate),
           "-f", "s16le", "-"]
    proc = _run(cmd, 600, capture_output=True)
    raw = proc.stdout
    if not raw:
        return []
    samples = array.array("h")
    samples.frombytes(raw[: len(raw) - (len(raw) % 2)])
    n = len(samples)
    if n == 0:
        return []
    # ちょうど buckets 個に均等分割し、全尺をカバーする（末尾欠落を防ぐ）。
    peaks: List[float] = []
    for i in range(buckets):
        a = i * n // buckets
        b = max(a + 1, (i + 1) * n // buckets)
        chunk = samples[a:b]
        peaks.append(max((abs(s) for s in chunk), default=0) / 32768.0)
    peak_max = max(peaks) if peaks else 0.0
    if peak_max > 0:
        peaks = [round(p / peak_max, 4) for p in peaks]
    return peaks


def render_cuts(
    path: str, keep_segments: List[TimeRange], output_path: str, audio_fade_sec: float = 0.0
) -> None:
    """keep_segments のみを連結して書き出す（実カット）。

    trim/atrim フィルタで各区間を切り出し concat する。
    audio_fade_sec>0 のとき各区間の音声先頭/末尾に極短フェードを掛け、
    カット境界のクリック音（プツ音）を抑える（尺は不変）。
    """
    ensure_available()
    if not keep_segments:
        raise ValueError("keep_segments が空です。書き出す区間がありません。")

    filters: List[str] = []
    concat_inputs: List[str] = []
    for i, seg in enumerate(keep_segments):
        filters.append(
            f"[0:v]trim=start={seg.start}:end={seg.end},setpts=PTS-STARTPTS[v{i}]"
        )
        afilter = f"[0:a]atrim=start={seg.start}:end={seg.end},asetpts=PTS-STARTPTS"
        fade = min(audio_fade_sec, seg.duration / 2) if audio_fade_sec > 0 else 0.0
        if fade > 0:
            afilter += f",afade=t=in:st=0:d={fade:.4f},afade=t=out:st={seg.duration - fade:.4f}:d={fade:.4f}"
        filters.append(f"{afilter}[a{i}]")
        concat_inputs.append(f"[v{i}][a{i}]")
    n = len(keep_segments)
    filters.append("".join(concat_inputs) + f"concat=n={n}:v=1:a=1[outv][outa]")
    filter_complex = ";".join(filters)

    # カット数が多いとコマンド引数が長くなり Windows の上限に達するため、
    # フィルタは一時ファイルに書き -filter_complex_script で渡す。
    import os
    import tempfile

    fd, script_path = tempfile.mkstemp(suffix=".txt", prefix="vet_filter_")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(filter_complex)
        cmd = [
            FFMPEG, "-y", "-i", path,
            "-filter_complex_script", script_path,
            "-map", "[outv]", "-map", "[outa]",
            output_path,
        ]
        _run(cmd, 3600, capture_output=True, text=True, encoding="utf-8",
             errors="replace", check=True)
    finally:
        try:
            os.remove(script_path)
        except OSError:
            pass
