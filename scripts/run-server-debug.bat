@echo off
setlocal
set "PYTHON=C:\Users\user\Projects\universal-downloader-pro\.venv\Scripts\python.exe"
set "APP_DIR=C:\Users\user\Projects\universal-downloader-pro\src"
set "PORT=8765"

echo [run] Using python: %PYTHON%
"%PYTHON%" --version
echo [run] Starting server...
cd /d "%APP_DIR%"
set PYTHONPATH="%APP_DIR%"
"%PYTHON%" -m flask --app udp.app:create_app() run --host 127.0.0.1 --port %PORT% --no-reload
pause
