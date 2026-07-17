# VideoEditTool

動画のカット編集を効率化する汎用の**動画カット編集支援ツール**。
編集は独自アルゴリズム（ルールエンジン）で行い、AIは補助（品質確認・改善提案）に限定する。

## 必要環境
- Python 3.11+
- ffmpeg / ffprobe（PATH に通す）

## セットアップ
```bash
python -m pip install -r requirements.txt
```

## 使い方
```bash
# 解析 → 編集候補 → 書き出し（既定は JSON のカットリスト）
python -m ui.cli input.mp4

# 案件プロファイル適用（config/profiles/*.yaml）
python -m ui.cli input.mp4 --profile youtube

# EDL 出力 / ffmpeg で実際にカットした動画を書き出し
python -m ui.cli input.mp4 --format edl
python -m ui.cli input.mp4 --render
```

## テスト
```bash
python -m pytest
```

## 構成と設計思想
[`CLAUDE.md`](CLAUDE.md) に設計理念・ディレクトリ構成・拡張方法を記載。
仕様は [`docs/仕様書.md`](docs/仕様書.md)、開発体制は [`docs/開発環境整備.md`](docs/開発環境整備.md) を参照。

編集条件はすべて `config/*.yaml` で管理し、コードを変更せずに閾値変更・ルールの ON/OFF・
プロファイル追加ができる。新しい解析やルールはレジストリに登録するだけで追加できる。

## 実装状況（MVP）
- ✅ 無音検出 → 無音カット → タイムライン整形 → JSON/EDL/実カット出力、案件プロファイル
- 🔲 filler / duplicate / restate ルール、speech 解析、AI 補助、GUI、NLE 連携（拡張点として枠のみ）
