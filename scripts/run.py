"""Universal Downloader Pro — development server runner."""

from __future__ import annotations

import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(ROOT, "src")
if SRC not in sys.path:
    sys.path.insert(0, SRC)

os.environ.setdefault("UDP_API_TOKEN", "phase0test")
os.environ.setdefault("UDP_PORT", "8765")

from udp.app import create_app  # noqa: E402

app = create_app()

if __name__ == "__main__":
    app.run(host="127.0.0.1", port=int(os.environ["UDP_PORT"]), debug=False)
