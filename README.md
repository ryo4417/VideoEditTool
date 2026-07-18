# VideoEditTool

動画のカット編集を効率化する汎用の**動画カット編集支援ツール**。
編集は独自アルゴリズム（ルールエンジン）で行い、AIは補助（品質確認・改善提案）に限定する。
ローカルWeb GUI で、複数動画をまとめて解析・確認・手直し・書き出しできる。

## すぐ試す
```powershell
cd ~\Desktop\VideoEditTool
.\start.ps1 -Sample            # 依存導入＋サンプル生成＋GUI起動
# フィラー/重複/言い直しも試すなら:  .\start.ps1 -WithWhisper -Sample
```
ダブルクリック起動なら `start.bat`。ブラウザで `http://127.0.0.1:8000` が開く。
詳しい操作は [docs/使い方.md](docs/使い方.md) を参照。

## 必要環境
- **必須**: Python 3.11+ / ffmpeg・ffprobe（PATH に通す）
- **任意**:
  - `faster-whisper` … ローカル文字起こし（内容ベースのルール用）。`start.ps1 -WithWhisper` で導入。
  - `yt-dlp` … YouTube 等の URL からの動画取り込み（`pip install yt-dlp`）。
  - Ollama … AI 品質採点（ローカルLLM・完全オフライン・既定オフ）。

## セットアップ
```bash
python -m pip install -r requirements.txt
```

## 使い方（GUI・推奨）
ローカルWebアプリ（追加依存なし）で起動:
```bash
python -m ui.web.server        # http://127.0.0.1:8000 が開く
```
- **複数動画プロジェクト**: 動画をまとめて追加し、一覧で切り替え。各動画の編集内容は独立して保持される。
- **動画の追加**: ドラッグ&ドロップ / ファイル選択 / パス入力 / お試し動画 / **YouTube 等の URL 取り込み**（yt-dlp）。
- 「解析」→ 色分けタイムライン・動画プレビューで確認。候補チェックで削除率をライブ確認 → 形式を選んで「書き出し」。
- **波形ズーム＋単語トラック**: 波形の下に文字起こしを時間軸で表示し、カットされる語は取り消し線で示す。
- **手編集**: タイムラインでカットをドラッグ移動 / 伸縮 / 削除 / 追加、一覧で秒数を微調整。
  **Undo・自動カットに戻す・自動検出との二段表示**、編集後プレビュー、解析中オーバーレイに対応。
- 出力先の指定、**Google ドライブ**（デスクトップ版マウント）からの入力・への出力に対応。

## 使い方（CLI）
```bash
# 解析 → 編集候補 → 書き出し（既定は JSON のカットリスト）
python -m ui.cli input.mp4

# 複数入力（ワイルドカード可）
python -m ui.cli "clips/*.mp4"

# 案件プロファイル適用（config/profiles/*.yaml）
python -m ui.cli input.mp4 --profile youtube

# 書き出し形式: json / edl(V+音声) / html（編集確認プレビュー）/ fcpxml（NLE連携）
# 複数形式はカンマ区切りで指定（解析は1回だけ実行される）
python -m ui.cli input.mp4 --format html,fcpxml,json

# 品質レポート(json) / ffmpeg で実際にカットした動画を書き出し / 文字起こし結果を出力
python -m ui.cli input.mp4 --report
python -m ui.cli input.mp4 --render
python -m ui.cli input.mp4 --transcript
```

## テスト
```bash
python -m pytest
```
CI では ffmpeg を含めて pytest を実行する。

## 構成と設計思想
[`CLAUDE.md`](CLAUDE.md) に設計理念・ディレクトリ構成・拡張方法を記載。
仕様は [`docs/仕様書.md`](docs/仕様書.md)、開発体制は [`docs/開発環境整備.md`](docs/開発環境整備.md) を参照。

編集条件はすべて `config/*.yaml` で管理し、コードを変更せずに閾値変更・ルールの ON/OFF・
プロファイル追加ができる。config はスキーマ検証（型・未知キー・負値・不正 format）で守られる。
新しい解析やルールはレジストリに登録するだけで追加できる。AI は補助のみで既定オフ、AI なしでも編集は完結する。

## 実装状況
- ✅ ローカルWeb GUI（`start.bat` / `start.ps1` 起動）: プレビュー・波形ズーム・色分けタイムライン・候補トグルで削除率ライブ更新・書き出し
- ✅ **複数動画プロジェクト**: まとめて追加・一覧切替・各動画の編集を独立保持
- ✅ 動画追加: ドラッグ&ドロップ / 選択 / パス入力 / お試し動画 / **YouTube 等 URL 取り込み**（yt-dlp）
- ✅ カット編集ルール（すべて config で ON/OFF）: 無音 / テンポ(間の短縮) / フィラー / 重複 / 言い直し
- ✅ ローカルWhisper文字起こし: 精度 tiny〜large-v3・言語選択・VAD で幻聴抑制（内容ベースのルール用）
- ✅ **単語トラック**: 波形下に文字起こしを時間軸表示、カット語は取り消し線
- ✅ 手編集: ドラッグ移動 / 伸縮 / 削除 / 追加・秒数微調整、**Undo・自動カットに戻す・二段表示**、編集後プレビュー、解析中オーバーレイ
- ✅ 書き出し: json / edl(V+音声) / html / fcpxml / 実カット動画（境界のクリック音フェード）。出力先指定・**Google ドライブ**入出力
- ✅ 品質チェッカー（`--report`）、config スキーマ検証、案件プロファイル（youtube / interview・説明表示）
- ✅ **AI品質採点**（ローカルLLM / Ollama・任意・オフライン・補助）
- ✅ CLI: 複数入力（ワイルドカード）・複数形式 1 回解析・`--transcript` 等。CI（ffmpeg 込み）で pytest
- 🔲 未実装 / 保留: 案件マニュアル学習（マニュアル提供後）、真のクロスフェード / カット境界スナップ（実素材での調整が必要）
