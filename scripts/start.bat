@echo off
title Aria Local Agent
echo ===================================================
echo  Starting Aria Local Agent (100%% Offline ^& Private)
echo ===================================================

cd /d "%~dp0\.."

if not exist "backend\.venv\Scripts\python.exe" (
    echo Error: Python virtual environment not found in backend\.venv
    pause
    exit /b 1
)

echo.
echo PC Web Access:        http://localhost:8000
echo Mobile Tailscale IP:  http://100.90.33.83:8000
echo.
echo Starting server... Press Ctrl+C to stop.
echo.

"backend\.venv\Scripts\python.exe" -m uvicorn app.main:app --app-dir backend --host 0.0.0.0 --port 8000
pause
