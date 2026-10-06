@echo off
cd /d C:\Users\user\Projects\universal-downloader-pro\src
echo [server] Using python: "C:\Users\user\Projects\universal-downloader-pro\.venv\Scripts\python.exe" > "C:\Users\user\Projects\universal-downloader-pro\launcher\server_launch.log" 2>&1
"C:\Users\user\Projects\universal-downloader-pro\.venv\Scripts\python.exe" --version >> "C:\Users\user\Projects\universal-downloader-pro\launcher\server_launch.log" 2>&1
where "C:\Users\user\Projects\universal-downloader-pro\.venv\Scripts\python.exe" >> "C:\Users\user\Projects\universal-downloader-pro\launcher\server_launch.log" 2>&1
"C:\Users\user\Projects\universal-downloader-pro\.venv\Scripts\python.exe" -m flask --app "udp.app:create_app()" run --host 127.0.0.1 --port 8765 --no-reload >> "C:\Users\user\Projects\universal-downloader-pro\launcher\server_launch.log" 2>&1
pause
