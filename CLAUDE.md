# VideoEditTool — 動画カット編集支援ツール

汎用の動画カット編集支援ツール。編集は**独自アルゴリズム（ルールエンジン）**で行い、
AIは補助（品質評価・編集漏れ検出・改善提案）に限定する。詳細は
[`docs/仕様書.md`](docs/仕様書.md) と [`docs/開発環境整備.md`](docs/開発環境整備.md) を参照。

## 基本フロー（仕様書 §5）
```
読み込み → 解析 → 編集候補生成 → 編集確認 → 書き出し
（probe）  （analyzer）（rule engine）（keep区間）（json/edl/ffmpeg）
```

## ディレクトリ構成
```
VideoEditTool/
├── core/        # 共通層。models / config / ffmpeg / registry / analyzer・rule基底。他に依存しない
├── audio/       # 音声解析アナライザ（silence 実装済み）
├── rules/       # 編集ルール + RuleEngine（silence 実装済み）
├── timeline/    # keep区間の導出・整形（近接マージ・短区間除去）
├── export/      # 書き出し（json / edl / ffmpegレンダリング）
├── plugins/     # 組み込みプラグイン登録（builtin.py）+ 将来の外部プラグイン
├── ui/          # CLI（UIと処理を分離）
├── config/      # 全設定。default.yaml + profiles/ + clients/rules/templates
├── scripts/     # 補助スクリプト
├── tests/       # pytest
├── pipeline.py  # アプリ配線層（各モジュールを組み合わせる）
└── docs/        # 仕様書・設計資料
```

## 実行 / テスト
```bash
# 依存: PyYAML（必須） + ffmpeg/ffprobe（PATH）。開発に pytest。
python -m pip install -r requirements.txt

# 解析→編集候補→書き出し（json）
python -m ui.cli input.mp4

# 案件プロファイル適用 / EDL出力 / 実カット
python -m ui.cli input.mp4 --profile youtube --format edl
python -m ui.cli input.mp4 --render

# テスト（ffmpeg不要の純ロジック）
python -m pytest
```

## 設計理念（仕様書 §4・§12 — 厳守）
- **拡張性・保守性を最優先**。コードの短さより拡張性。
- **config駆動**: 編集条件は全て `config/*.yaml`。閾値・ON/OFF・ルール追加はコード変更なしで行う。
- **プラグイン構造**: アナライザ／ルールは `core/registry.py` に名前登録するだけで追加・差し替え可能。
- **モジュール間依存は最小限**: 各モジュールは `core` にのみ依存。core は他に依存しない。
- **UIと処理を分離**: `ui/` はPipelineを呼ぶだけ。編集ロジックを持たない。
- **単一責務**: 1関数1責務。ffmpeg呼び出しは `core/ffmpeg.py` に局所化。
- **AIは補助のみ**: 既定オフ。AIなしでも編集完結（`config.ai.enabled`）。

## コーディング規約（開発環境整備 §Cloud Codeへのルール）
- 1コミット1機能／必ずテストを書く／設計変更時は理由を書く
- 仕様が曖昧なら実装しない → **拡張ポイントとして用意**（例: config に enabled:false のルール枠）
- ハードコード・マジックナンバー禁止（定数化 or config化）
- コメントより命名を優先／処理速度を考慮

## 拡張の入口（新しい編集ルールを足す例）
1. `rules/xxx_rule.py` に `BaseRule` を継承し `@RULES.register("xxx")` を付ける
2. `config/default.yaml` の `rules:` に `xxx: {enabled: true, ...}` を追加
3. `plugins/builtin.py` に import を1行追加
4. `tests/` にテストを追加
→ エンジンや他モジュールの変更は不要。

## 開発の進め方（監督者方針）
- 各機能は**まず「最低限動く」形を `main`** に載せる。`main` は常に動く基準線を保つ。
- 機能改善で**方向性が分かれるときは、既存方針で動くものを先に `main`** に作り、
  **改善案版は `feature/<名前>` ブランチ**で開発する（例: AIありの品質採点は `feature/ai-quality`）。
- 迷って決められない場合は、各案を最低限動く形にして**ブランチで並走**させ、`main` は選んだ案で進める。
- エージェントは継続的に棚卸しする（下記）。**監督者が管理できる範囲**の数に抑える。

## サブエージェント（`.claude/agents/`）— 計11種
- **役割別（実装/管理）**: `project-manager` / `core-architect` / `audio-analyzer` / `rule-engine` / `timeline-engine` / `export-engine` / `ui-engineer` / `qa-agent`（バグ探し） / `doc-agent` / `design-reviewer`（設計全体）
- **改善提案（汎用・提案のみ）**: `improver` — 対象機能を指定して使う（例:「improver で audio を改善」）。
  「課題→改善案→期待効果→影響範囲→優先度」で上位3件を提示。
- 方針: 監督者が管理できる範囲に数を抑える。不要になったものは畳み、必要な領域だけ増やす。

## 現状（MVP）
- 実装済み（main）:
  - **ローカルWeb GUI**（`ui/web/`, 追加依存なし）: 動画プレビュー・色分けタイムライン・
    候補トグルで削除率ライブ更新・書き出し。起動 `python -m ui.web.server`。
  - カット編集ルール（内容/無音ベース・すべてconfigでON/OFF）:
    無音 / テンポ(間の短縮) / フィラー(複数語句可) / 重複 / 言い直し(方式B)
  - **ローカルWhisper文字起こし**（`audio/transcribe.py`+`transcript.py`, faster-whisper任意依存・モデルキャッシュ）
  - 書き出し: json / edl(V+音声) / html / fcpxml / 実カット動画。CLIは解析1回で複数形式出力
  - 発話区間解析、品質チェッカー（`quality/`, `--report`）、config スキーマ検証（型・未知キー・負値・不正format）
  - **AI品質採点（ローカルLLM / Ollama）**（`quality/ai_assist.py`, 既定オフ・オフライン・補助）
  - 案件プロファイル（youtube / interview）。GUI: 波形・解析オプション・言語選択・文字起こし可視化。
  - テスト件数は `python -m pytest` を参照（CIでも実行）。
- 保留: 案件マニュアル学習（マニュアル未提供）、編集後プレビュー再生・進捗表示・バッチ入力（拡張候補）。

## パイプラインAPI（`pipeline.Pipeline`）
- `analyze(path)` → 書き出さず解析結果を返す（GUI用）
- `recompute(result, enabled_indices)` → 候補の採否で keep/report を再計算
- `export_result(result, out_dir)` / `run(path, out_dir)` → 書き出し
