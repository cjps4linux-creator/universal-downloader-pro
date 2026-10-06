Set WshShell = CreateObject("WScript.Shell")
WshShell.Run "cmd /c cd /d C:\Users\user\Projects\universal-downloader-pro\src && ""C:\Users\user\Projects\universal-downloader-pro\.venv\Scripts\python.exe"" -m flask --app ""udp.app:create_app()"" run --host 127.0.0.1 --port 8765 --no-reload", 0, False
