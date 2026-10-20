@echo off
setlocal
rem Resolve the project root from this script's own location.
set "ROOT=%~dp0.."
set "APP_DIR=%ROOT%\src"
set "LOG=%ROOT%\launcher\server_launch.log"

set "PYTHON="
if exist "%ROOT%\.venv\Scripts\python.exe" set "PYTHON=%ROOT%\.venv\Scripts\python.exe"
if not defined PYTHON if defined HERMES_PYTHON set "PYTHON=%HERMES_PYTHON%"
if not defined PYTHON for %%P in (python.exe python) do if not defined PYTHON set "PYTHON=%%~$PATH:P"

if not defined PYTHON (
  echo [server] No Python interpreter found.
  echo [server] Create a virtualenv at "%ROOT%\.venv" or set HERMES_PYTHON.
  pause
  exit /b 1
)

cd /d "%APP_DIR%"
echo [server] Using python: "%PYTHON%" > "%LOG%" 2>&1
"%PYTHON%" --version >> "%LOG%" 2>&1
where "%PYTHON%" >> "%LOG%" 2>&1
"%PYTHON%" -m flask --app "udp.app:create_app()" run --host 127.0.0.1 --port 8765 --no-reload >> "%LOG%" 2>&1
pause
endlocal
