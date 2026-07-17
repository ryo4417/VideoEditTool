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

# 書き出し形式: json / edl / html（編集確認プレビュー）/ fcpxml（NLE連携）
python -m ui.cli input.mp4 --format html
python -m ui.cli input.mp4 --format fcpxml

# 品質レポート(json) / ffmpeg で実際にカットした動画を書き出し
python -m ui.cli input.mp4 --report
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
- ✅ 無音検出 → 無音カット → タイムライン整形
- ✅ 書き出し: JSON / EDL / HTML（編集確認プレビュー）/ FCPXML / 実カット動画
- ✅ 発話区間解析（無音の補集合）、品質チェッカー（AIなし採点・レポート）
- ✅ config スキーマ検証（設定ミスの早期検出）、案件プロファイル（youtube / interview）
- 🌿 AI 補助の品質採点は `feature/ai-quality` ブランチで骨組み実装中（実プロバイダは選定待ち）
- 🔲 filler / duplicate / restate ルール（ASR/発話内容解析が必要 → 案件確定後）、GUI 詳細
