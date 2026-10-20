@echo off
setlocal
set "ROOT=%~dp0.."
set "PYTHON="
if exist "%ROOT%\.venv\Scripts\python.exe" set "PYTHON=%ROOT%\.venv\Scripts\python.exe"
if not defined PYTHON if defined HERMES_PYTHON set "PYTHON=%HERMES_PYTHON%"
if not defined PYTHON for %%P in (python.exe python) do if not defined PYTHON set "PYTHON=%%~$PATH:P"
set "APP_DIR=%ROOT%\src"
set "PORT=8765"

echo [run] Using python: %PYTHON%
"%PYTHON%" --version
echo [run] Starting server...
cd /d "%APP_DIR%"
set PYTHONPATH="%APP_DIR%"
"%PYTHON%" -m flask --app udp.app:create_app() run --host 127.0.0.1 --port %PORT% --no-reload
pause
