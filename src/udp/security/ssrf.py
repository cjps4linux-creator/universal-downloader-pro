"""Universal Downloader Pro — SSRF guard and URL validation."""

from __future__ import annotations

import ipaddress
import socket
from typing import Optional
from urllib.parse import urlparse

_BLOCKED = {"localhost", "127.0.0.1", "0.0.0.0", "169.254.169.254", "[::1]"}


def validate_url(url: str) -> None:
    parsed = urlparse(url)
    if not parsed.scheme.startswith("http"):
        raise ValueError("url scheme must be http or https")
    host = (parsed.hostname or "").lower()
    if host in _BLOCKED:
        raise ValueError(f"url targets a blocked host: {host}")
    if _is_private_host(host):
        raise ValueError(f"url targets a private-range host: {host}")


def _is_private_host(host: str) -> bool:
    if host.startswith("[") and host.endswith("]"):
        host = host[1:-1]
    try:
        ip = ipaddress.ip_address(host)
        return ip.is_private or ip.is_loopback or ip.is_link_local
    except ValueError:
        return False


def resolve_and_validate(url: str) -> str:
    host = urlparse(url).hostname
    if not host:
        raise ValueError("missing host")
    ip = socket.gethostbyname(host)
    addr = ipaddress.ip_address(ip)
    if addr.is_private or addr.is_loopback or addr.is_link_local:
        raise ValueError(f"resolved to blocked ip: {ip}")
    return ip
