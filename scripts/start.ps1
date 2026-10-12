# Aria Local Agent - PowerShell Launcher
$ErrorActionPreference = "Stop"

$repoRoot = Split-Path -Parent $PSScriptRoot
Set-Location $repoRoot

Write-Host "===================================================" -ForegroundColor Cyan
Write-Host " Starting Aria Local Agent (100% Offline & Private)" -ForegroundColor Cyan
Write-Host "===================================================" -ForegroundColor Cyan

$python = Join-Path $repoRoot "backend\.venv\Scripts\python.exe"
if (-not (Test-Path $python)) {
    Write-Host "Error: Python venv not found at backend\.venv" -ForegroundColor Red
    exit 1
}

Write-Host ""
Write-Host "PC Web Access:        http://localhost:8000" -ForegroundColor Green
Write-Host "Mobile Tailscale IP:  http://100.90.33.83:8000" -ForegroundColor Green
Write-Host ""
Write-Host "Starting Uvicorn server on 0.0.0.0:8000 (Press Ctrl+C to stop)..." -ForegroundColor Yellow

& $python -m uvicorn app.main:app --app-dir backend --host 0.0.0.0 --port 8000
