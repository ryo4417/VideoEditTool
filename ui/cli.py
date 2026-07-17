"""CLI（UI層）。

UIと処理を分離する（仕様書 §4）。ここは引数を受け取り、
Pipeline を呼び、結果を表示するだけ。編集ロジックは持たない。

使い方:
    python -m ui.cli <input> [--profile NAME] [--format json,edl,fcpxml] [--report] [--render] [--transcript]
"""
from __future__ import annotations

import argparse
import sys

from core.config import ConfigError, load_config
from core.ffmpeg import FFmpegNotFound, MediaProbeError
from pipeline import Pipeline
from rules._text import join_words

ALLOWED_FORMATS = ["json", "edl", "html", "fcpxml"]


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="動画カット編集支援ツール")
    parser.add_argument("input", help="入力動画ファイル")
    parser.add_argument("--profile", default=None, help="案件プロファイル名 (config/profiles/*.yaml)")
    parser.add_argument("--format", dest="fmt", default=None,
                        help="書き出し形式。カンマ区切りで複数可 (json,edl,html,fcpxml)。解析は1回のみ実行")
    parser.add_argument("--output-dir", default=None, help="出力先ディレクトリ")
    parser.add_argument("--render", action="store_true", help="ffmpeg で実際にカット動画を書き出す")
    parser.add_argument("--report", action="store_true", help="品質レポート(json)を書き出す")
    parser.add_argument("--transcript", action="store_true", help="文字起こし結果を標準出力に表示")
    return parser


def main(argv: list[str] | None = None) -> int:
    # 端末やパイプのエンコーディングに依存せず日本語を出せるようにする。
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, ValueError):
            pass

    args = build_parser().parse_args(argv)

    formats = [f for f in (args.fmt.split(",") if args.fmt else []) if f]
    bad = [f for f in formats if f not in ALLOWED_FORMATS]
    if bad:
        print(f"[エラー] 未対応の形式: {', '.join(bad)} (許可: {', '.join(ALLOWED_FORMATS)})", file=sys.stderr)
        return 2

    try:
        config = load_config(args.profile)
    except (ConfigError, FileNotFoundError) as e:
        print(f"[設定エラー] {e}", file=sys.stderr)
        return 2

    export_cfg = config.data.setdefault("export", {})
    if not formats:
        formats = [export_cfg.get("format", "json")]
    # プロファイル指定時は出力名に付与して上書き衝突を避ける。
    if args.profile:
        export_cfg["stem_suffix"] = f".{args.profile}"

    try:
        pipe = Pipeline(config)
        result = pipe.analyze(args.input)  # 解析は1回だけ（Whisper等の再実行を避ける）
        outputs: list[str] = []
        for i, fmt in enumerate(formats):
            export_cfg["format"] = fmt
            # レポート・実カットは1回だけ生成する。
            config.data.setdefault("quality", {})["report"] = args.report and i == 0
            export_cfg["render"] = args.render and i == 0
            outputs.extend(pipe.export_result(result, output_dir=args.output_dir))
    except (FFmpegNotFound, MediaProbeError, FileNotFoundError) as e:
        print(f"[エラー] {e}", file=sys.stderr)
        return 2

    r = result.report
    print(f"入力: {result.media.path} ({result.media.duration:.1f}s)")
    print(f"編集候補: {len(result.candidates)} 件 (CUT {r.num_cuts})")
    print(f"残す区間: {r.num_segments} 区間 / 残時間 {r.kept_duration:.1f}s (削除率 {r.removed_ratio:.0%})")
    for w in r.warnings:
        print(f"[警告] {w}")
    if args.transcript:
        words = result.analysis.data.get("words", [])
        text = join_words([w.text for w in words]) if words else "（文字起こしなし）"
        print(f"文字起こし: {text}")
    for out in outputs:
        print(f"出力: {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
