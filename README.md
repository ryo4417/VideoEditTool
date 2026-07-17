# VideoEditTool

動画のカット編集を効率化する汎用の**動画カット編集支援ツール**。
編集は独自アルゴリズム（ルールエンジン）で行い、AIは補助（品質確認・改善提案）に限定する。

## すぐ試す
```powershell
cd ~\Desktop\VideoEditTool
.\start.ps1 -Sample            # 依存導入＋サンプル生成＋GUI起動
# フィラー/重複/言い直しも試すなら:  .\start.ps1 -WithWhisper -Sample
```
詳しい操作は [docs/使い方.md](docs/使い方.md) を参照。

## 必要環境
- Python 3.11+
- ffmpeg / ffprobe（PATH に通す）

## セットアップ
```bash
python -m pip install -r requirements.txt
```

## 使い方（GUI・推奨）
視覚的な編集確認GUI（ローカルWebアプリ・追加依存なし）:
```bash
python -m ui.web.server        # http://127.0.0.1:8000 が開く
```
動画パスを入力して「解析」→ 色分けタイムライン・動画プレビューで確認し、
候補のチェックで削除率をライブ確認 → 形式を選んで「書き出し」。

## 使い方（CLI）
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

## 実装状況
- ✅ ローカルWeb GUI（編集確認: プレビュー・波形・色分けタイムライン・候補トグル・書き出し）
- ✅ カット編集ルール: 無音 / テンポ(間の短縮) / フィラー / 重複 / 言い直し（すべてconfigでON/OFF）
- ✅ ローカルWhisper文字起こし（内容ベースのルール用）、発話区間解析
- ✅ 書き出し: JSON / EDL(V+音声) / HTML / FCPXML / 実カット動画。CLIは1回の解析で複数形式出力
- ✅ 品質チェッカー（AIなし採点・レポート）、config スキーマ検証、案件プロファイル
- ✅ AI補助の品質採点（ローカルLLM/Ollama・任意・オフライン）
- 🔲 未実装: 案件マニュアル学習（マニュアル提供後）、編集後プレビュー再生・進捗表示・バッチ入力（GUI/CLIの拡張候補）
