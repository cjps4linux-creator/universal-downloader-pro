"""Universal Downloader Pro — app-scoped network tunnel sidecar.

Note: app-level tunnel sidecar is not currently operational on this build.
This module preserves the control-plane API surface, but tunnel operations
report unavailable unless an externally provided proxy URL is configured.
"""

from __future__ import annotations

import json
import os
import secrets
import shutil
import socket
import subprocess
import threading
import time
from pathlib import Path
from typing import Optional

from udp.utils.paths import data_dir

TUNNEL_DIR = data_dir() / "tunnel"
TUNNEL_DIR.mkdir(parents=True, exist_ok=True)

CONF_PATH = TUNNEL_DIR / "wireproxy.conf"
LOG_PATH = TUNNEL_DIR / "wireproxy.log"
PID_PATH = TUNNEL_DIR / "wireproxy.pid"
PORT_PATH = TUNNEL_DIR / "wireproxy.port"
PROXY_URL_PATH = TUNNEL_DIR / "proxy_url.txt"


class TunnelError(Exception):
    pass


def wireproxy_path() -> Path:
    local = Path(__file__).resolve().parent.parent.parent.parent / "scripts" / "wireproxy.exe"
    if local.exists():
        return local
    exe = shutil.which("wireproxy")
    if exe:
        return Path(exe)
    raise TunnelError("wireproxy not found; expected scripts/wireproxy.exe")


def build_conf(port: int, upstream: str) -> str:
    private_key = __import__("base64").b64encode(secrets.token_bytes(32)).decode("ascii")
    return f"""
[Interface]
PrivateKey = {private_key}
Address = 10.0.0.2/32
DNS = 1.1.1.1

[Peer]
PublicKey = dummy
Endpoint = {upstream}
AllowedIPs = 0.0.0.0/0, ::/0
""".strip() + "\n"


def start_tunnel(upstream: str, port: Optional[int] = None) -> dict:
    raise TunnelError("App-sidecar tunnel is unavailable in this build. Use a manual proxy URL instead.")


def stop_tunnel() -> None:
    for marker in [PID_PATH, PORT_PATH]:
        marker.unlink(missing_ok=True)
    if PID_PATH.exists():
        try:
            pid = int(PID_PATH.read_text(encoding="utf-8"))
            os.kill(pid, 9)
        except Exception:
            pass


def tunnel_port() -> Optional[int]:
    if PORT_PATH.exists():
        try:
            return int(PORT_PATH.read_text(encoding="utf-8").strip())
        except ValueError:
            return None
    return None


def tunnel_proxy_url() -> Optional[str]:
    url = None
    if PROXY_URL_PATH.exists():
        try:
            url = PROXY_URL_PATH.read_text(encoding="utf-8").strip()
        except Exception:
            url = None
    if not url:
        return None
    return url


def set_proxy_url(url: Optional[str]) -> None:
    if url:
        PROXY_URL_PATH.write_text(url.strip(), encoding="utf-8")
    else:
        PROXY_URL_PATH.unlink(missing_ok=True)


def tunnel_running() -> bool:
    return tunnel_proxy_url() is not None


def ensure_tunnel(upstream: str) -> dict:
    raise TunnelError("App-sidecar tunnel is unavailable in this build. Use a manual proxy URL instead.")


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def _wait_for_port(host: str, port: int, timeout: float = 5.0) -> bool:
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            with socket.create_connection((host, port), timeout=1):
                return True
        except OSError:
            time.sleep(0.2)
    return False


def egress_ip(proxy_url: Optional[str] = None) -> dict:
    proxies = {"http": proxy_url, "https": proxy_url} if proxy_url else None
    try:
        import requests
        r = requests.get("https://api.ipify.org?format=json", timeout=10, proxies=proxies)
        if r.status_code == 200:
            return {"ip": r.json().get("ip"), "via": proxy_url or "direct"}
    except Exception as exc:
        return {"error": str(exc), "via": proxy_url or "direct"}
    return {"error": "unknown", "via": proxy_url or "direct"}


def dns_leak_test(proxy_url: Optional[str] = None) -> dict:
    proxies = {"http": proxy_url, "https": proxy_url} if proxy_url else None
    try:
        import requests
        r = requests.get("https://dnsleaktest.com/results.csv", timeout=10, proxies=proxies)
        if r.status_code == 200:
            lines = [line for line in r.text.splitlines() if line.strip()][:5]
            return {"lines": lines, "via": proxy_url or "direct"}
    except Exception as exc:
        return {"error": str(exc), "via": proxy_url or "direct"}
    return {"error": "unknown", "via": proxy_url or "direct"}
