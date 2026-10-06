"""Health-check waiter for the Windows launcher."""
import requests
import sys
import time

url = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8765/health"
while True:
    try:
        r = requests.get(url, timeout=2)
        if r.status_code == 200:
            sys.exit(0)
    except Exception:
        pass
    time.sleep(1)