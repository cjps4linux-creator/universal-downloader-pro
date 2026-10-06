@echo off
setlocal
cd /d "C:\Users\user\Projects\universal-downloader-pro"
set "PYTHON=C:\Users\user\Projects\universal-downloader-pro\.venv\Scripts\python.exe"
if not exist "%PYTHON%" (
  echo [launcher] Venv Python not found: %PYTHON%
  pause
  exit /b 1
)
echo [launcher] Using python: %PYTHON%
echo [launcher] Starting server...
"%PYTHON%" "C:\Users\user\Projects\universal-downloader-pro\scripts\run_udp_server.py"
pause
