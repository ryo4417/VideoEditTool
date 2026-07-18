@echo off
REM VideoEditTool 起動（ダブルクリックでOK）
REM PowerShellのスクリプト実行ブロックを回避して start.ps1 を実行します。
cd /d "%~dp0"
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0start.ps1" %*
pause
