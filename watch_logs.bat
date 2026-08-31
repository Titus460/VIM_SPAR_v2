@echo off
title VIM Live Logs
color 0A
chcp 65001 >nul
powershell -NoProfile -ExecutionPolicy Bypass -Command ^
  "[Console]::OutputEncoding = [System.Text.Encoding]::UTF8;" ^
  "$OutputEncoding = [System.Text.Encoding]::UTF8;" ^
  "$host.UI.RawUI.WindowTitle = 'VIM Live Logs';" ^
  "Write-Host '================================================' -ForegroundColor Cyan;" ^
  "Write-Host '  VIM Real-Time Log Viewer' -ForegroundColor Cyan;" ^
  "Write-Host '  File: logs\vim.log' -ForegroundColor Gray;" ^
  "Write-Host '  Press Ctrl+C to stop.' -ForegroundColor Gray;" ^
  "Write-Host '================================================' -ForegroundColor Cyan;" ^
  "Write-Host '';" ^
  "$logPath = Join-Path '%~dp0' 'logs\vim.log';" ^
  "if (-not (Test-Path $logPath)) { New-Item -ItemType Directory -Force -Path (Split-Path $logPath) | Out-Null; New-Item -ItemType File -Force -Path $logPath | Out-Null };" ^
  "Get-Content -Path $logPath -Encoding utf8 -Wait | ForEach-Object {" ^
  "  if ($_ -match 'ERROR|CRITICAL') { Write-Host $_ -ForegroundColor Red }" ^
  "  elseif ($_ -match 'WARNING') { Write-Host $_ -ForegroundColor Yellow }" ^
  "  elseif ($_ -match 'PIPELINE START|PIPELINE END|VALIDATION.*Run complete|DB INSERT.*Done') { Write-Host $_ -ForegroundColor Green }" ^
  "  elseif ($_ -match 'STEP \d|ENGINE.*Stage|RESULT.*Committed') { Write-Host $_ -ForegroundColor Cyan }" ^
  "  else { Write-Host $_ -ForegroundColor White }" ^
  "}"
pause
