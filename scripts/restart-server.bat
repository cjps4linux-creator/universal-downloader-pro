@echo off
setlocal
set "PYTHON=C:\Users\user\Projects\universal-downloader-pro\.venv\Scripts\python.exe"
set "APP_DIR=C:\Users\user\Projects\universal-downloader-pro\src"
set "PORT=8765"

echo [restart] Killing old server on %PORT%...
for /f "tokens=5" %%a in ('netstat -ano ^| findstr :%PORT% ^| findstr LISTENING') do (
  echo [restart] Killing PID %%a
  taskkill /F /PID %%a >nul 2>&1
)
timeout /t 1 >nul

echo [restart] Starting server with venv Python...
start "UDP Backend" cmd /C "cd /d %APP_DIR% && set PYTHONPATH=%APP_DIR% && %PYTHON% -m flask --app udp.app:create_app() run --host 127.0.0.1 --port %PORT% --no-reload"

echo [restart] Waiting for health...
powershell -ExecutionPolicy Bypass -File "C:\Users\user\Projects\universal-downloader-pro\scripts\wait_for_health.ps1" "http://127.0.0.1:%PORT%/health"
if errorlevel 1 (
  echo [restart] ERROR: server did not become healthy
  pause
  exit /b 1
)

echo [restart] Server healthy on %PORT%
pause
