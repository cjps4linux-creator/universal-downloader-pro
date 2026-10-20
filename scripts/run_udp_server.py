import os
import sys
import secrets
from pathlib import Path

APP_DIR = Path(__file__).resolve().parent.parent
os.chdir(APP_DIR / "src")
os.environ["PYTHONPATH"] = str(APP_DIR / "src")
if not os.environ.get("UDP_API_TOKEN"):
    os.environ["UDP_API_TOKEN"] = secrets.token_urlsafe(32)

print(f"[launcher] Using python: {sys.executable}")
print(f"[launcher] Token: {os.environ['UDP_API_TOKEN']}")

try:
    from udp.app import create_app
except Exception as exc:
    print(f"[launcher] Import failed: {exc}")
    sys.exit(1)

app = create_app()
print("[launcher] Starting Flask on http://127.0.0.1:8765")
app.run(host="127.0.0.1", port=8765, use_reloader=False)
