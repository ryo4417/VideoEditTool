"""CLI（UI層）。

UIと処理を分離する（仕様書 §4）。ここは引数を受け取り、
Pipeline を呼び、結果を表示するだけ。編集ロジックは持たない。

使い方:
    python -m ui.cli <input> [--profile NAME] [--format json|edl] [--render]
"""
from __future__ import annotations

import argparse
import sys

from core.config import load_config
from core.ffmpeg import FFmpegNotFound
from pipeline import Pipeline


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="動画カット編集支援ツール")
    parser.add_argument("input", help="入力動画ファイル")
    parser.add_argument("--profile", default=None, help="案件プロファイル名 (config/profiles/*.yaml)")
    parser.add_argument("--format", dest="fmt", default=None, choices=["json", "edl"],
                        help="書き出し形式（config を上書き）")
    parser.add_argument("--output-dir", default=None, help="出力先ディレクトリ")
    parser.add_argument("--render", action="store_true", help="ffmpeg で実際にカット動画を書き出す")
    parser.add_argument("--report", action="store_true", help="品質レポート(json)を書き出す")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)

    config = load_config(args.profile)
    if args.fmt:
        config.data.setdefault("export", {})["format"] = args.fmt
    if args.render:
        config.data.setdefault("export", {})["render"] = True
    if args.report:
        config.data.setdefault("quality", {})["report"] = True

    try:
        result = Pipeline(config).run(args.input, output_dir=args.output_dir)
    except FFmpegNotFound as e:
        print(f"[エラー] {e}", file=sys.stderr)
        return 2
    except FileNotFoundError as e:
        print(f"[エラー] {e}", file=sys.stderr)
        return 2

    r = result.report
    print(f"入力: {result.media.path} ({result.media.duration:.1f}s)")
    print(f"編集候補: {len(result.candidates)} 件 (CUT {r.num_cuts})")
    print(f"残す区間: {r.num_segments} 区間 / 残時間 {r.kept_duration:.1f}s (削除率 {r.removed_ratio:.0%})")
    for w in r.warnings:
        print(f"[警告] {w}")
    for out in result.outputs:
        print(f"出力: {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
