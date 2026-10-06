@echo off
setlocal

set "PYTHON=C:\Users\user\Projects\universal-downloader-pro\.venv\Scripts\python.exe"
set "APP_DIR=C:\Users\user\Projects\universal-downloader-pro\src"
set "PORT=8765"
set "HEALTH_URL=http://127.0.0.1:%PORT%/health"
set "APP_URL=http://127.0.0.1:%PORT%/"
set "PATH=%USERPROFILE%\Projects\universal-downloader-pro\.venv\Scripts;%PATH%"

echo [launcher] Starting Universal Downloader Pro...

if not exist "%PYTHON%" (
  echo [launcher] ERROR: venv python not found at %PYTHON%
  pause
  exit /b 1
)

echo [launcher] Ensuring dependencies...
"%PYTHON%" -m pip install -q --upgrade pip
if errorlevel 1 (
  echo [launcher] ERROR: pip upgrade failed
  pause
  exit /b 1
)

"%PYTHON%" -m pip install -q flask requests curl-cffi beautifulsoup4 yt-dlp nh3 cryptography keyring tenacity tqdm pdfplumber python-docx sqlalchemy
if errorlevel 1 (
  echo [launcher] ERROR: dependency install failed
  pause
  exit /b 1
)

echo [launcher] Initializing database...
"%PYTHON%" "C:\Users\user\Projects\universal-downloader-pro\scripts\init_db.py"
if errorlevel 1 (
  echo [launcher] ERROR: database init failed
  pause
  exit /b 1
)

echo [launcher] Killing any old server on %PORT%...
for /f "tokens=5" %%a in ('netstat -ano ^| findstr :%PORT% ^| findstr LISTENING') do (
  echo [launcher] Killing PID %%a
  taskkill /F /PID %%a >nul 2>&1
)

echo [launcher] Generating API token...
set "UDP_API_TOKEN=udp_%RANDOM%%RANDOM%%RANDOM%"
set "UDP_API_TOKEN=%UDP_API_TOKEN: =%"
echo [launcher] API Token: %UDP_API_TOKEN%
echo [launcher] Paste this token in the app header when prompted.
echo [launcher] 
echo [launcher] IMPORTANT: Copy the token above before closing this window.
echo [launcher] 

echo [launcher] Starting server...
echo [launcher] Using python: %PYTHON%
echo [launcher] Token: %UDP_API_TOKEN%
echo [launcher] Opening browser...
start "" "%APP_URL%"
echo [launcher] Ready. Keep this window open. Token: %UDP_API_TOKEN%
echo [launcher] Press Ctrl+C to stop the server.
"%PYTHON%" -m flask --app "udp.app:create_app()" run --host 127.0.0.1 --port %PORT% --no-reload
pause
