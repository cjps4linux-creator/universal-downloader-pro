"""Network helpers for Universal Downloader Pro."""

from __future__ import annotations

import ipaddress
import socket


def resolve_host(url: str) -> str:
    host = __import__("urllib.parse").parse.urlparse(url).hostname
    if not host:
        raise ValueError("missing host")
    return socket.gethostbyname(host)


def is_private_ip(ip: str) -> bool:
    try:
        return ipaddress.ip_address(ip).is_private
    except ValueError:
        return True
