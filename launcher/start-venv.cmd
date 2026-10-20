@echo off
setlocal
rem Resolve the project root from this script's own location.
set "ROOT=%~dp0.."
set "PYTHON="
if exist "%ROOT%\.venv\Scripts\python.exe" set "PYTHON=%ROOT%\.venv\Scripts\python.exe"
if not defined PYTHON if defined HERMES_PYTHON set "PYTHON=%HERMES_PYTHON%"
if not defined PYTHON for %%P in (python.exe python) do if not defined PYTHON set "PYTHON=%%~$PATH:P"

if not defined PYTHON (
  echo [launcher] No Python interpreter found.
  echo [launcher] Create a virtualenv at "%ROOT%\.venv" or set HERMES_PYTHON.
  pause
  exit /b 1
)
echo [launcher] Using python: %PYTHON%
echo [launcher] Starting server...
"%PYTHON%" "%ROOT%\scripts\run_udp_server.py"
pause
endlocal
