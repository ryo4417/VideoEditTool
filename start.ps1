<#
.SYNOPSIS
    VideoEditTool を起動する（GUI）。依存を確認し、ローカルWebアプリを開く。
.EXAMPLE
    .\start.ps1                     # 依存を入れてGUIを起動（ブラウザが開く）
.EXAMPLE
    .\start.ps1 -WithWhisper        # ローカルWhisper(faster-whisper)も導入
.EXAMPLE
    .\start.ps1 -Sample             # 試用サンプル動画も生成して起動
.EXAMPLE
    .\start.ps1 -Port 8080 -NoBrowser
#>
param(
    [int]$Port = 8000,
    [switch]$WithWhisper,
    [switch]$Sample,
    [switch]$NoBrowser
)
$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

function Info($m) { Write-Host "[start] $m" -ForegroundColor Cyan }

if (-not (Get-Command python -ErrorAction SilentlyContinue)) {
    Write-Error "Python が見つかりません。Python 3.11+ をインストールしてください。"; exit 1
}
if (-not (Get-Command ffmpeg -ErrorAction SilentlyContinue)) {
    Write-Warning "ffmpeg が PATH にありません。動画処理に必須です（winget install Gyan.FFmpeg 等）。"
}

Info "依存を確認中（PyYAML）..."
python -m pip install --quiet --disable-pip-version-check PyYAML | Out-Null

if ($WithWhisper) {
    Info "ローカルWhisper(faster-whisper)を導入中...（初回は時間がかかります）"
    python -m pip install --quiet --disable-pip-version-check faster-whisper | Out-Null
}

if ($Sample) {
    Info "試用サンプル動画 sample.mp4 を生成中..."
    python scripts\make_sample.py sample.mp4
}

Info "GUIを起動します: http://127.0.0.1:$Port  （Ctrl+C で終了）"
$serverArgs = @("-m", "ui.web.server", "--port", "$Port")
if ($NoBrowser) { $serverArgs += "--no-browser" }
python @serverArgs
