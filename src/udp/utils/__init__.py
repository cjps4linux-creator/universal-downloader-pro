"""Utility modules for Universal Downloader Pro."""

from __future__ import annotations

import ipaddress
import os
import re
import secrets
import socket
from pathlib import Path, PurePosixPath, PureWindowsPath
from typing import Optional, Tuple
from urllib.parse import urlparse


def data_dir() -> Path:
    base = Path(os.environ.get("LOCALAPPDATA", str(Path.home() / "AppData/Local")))
    return base / "UniversalDownloaderPro"


def downloads_dir() -> Path:
    return data_dir() / "downloads"


def assets_dir(task_id: str) -> Path:
    return downloads_dir() / task_id / "assets"


def ensure_dirs() -> None:
    downloads_dir().mkdir(parents=True, exist_ok=True)


def sanitize_filename(name: str) -> str:
    name = re.sub(r'[<>:"/\\|?*\x00-\x1F]', "_", name)
    name = re.sub(r"[\s\.]+", "_", name).strip("_")
    if not name:
        name = "download"
    return name[:180]


def unique_path(path: Path) -> Path:
    if not path.exists():
        return path
    stem = path.stem
    suffix = path.suffix
    parent = path.parent
    idx = 1
    while True:
        candidate = parent / f"{stem}_{idx}{suffix}"
        if not candidate.exists():
            return candidate
        idx += 1


def derive_page_name(url: str, title: Optional[str]) -> str:
    parsed = urlparse(url)
    slug = parsed.path.strip("/").split("/")[-1]
    if not slug or slug == "":
        slug = "page"
    text = title.strip() if title else slug
    text = re.sub(r"[^a-zA-Z0-9\-_ ]+", "", text)
    text = re.sub(r"\s+", "_", text).strip("_")
    if not text:
        text = slug
    return sanitize_filename(text)[:80]


def compute_backoff(attempt: int, base: float = 1.0, cap: float = 60.0) -> float:
    jitter = secrets.randbelow(1000) / 1000.0
    return min(cap, base * (2 ** attempt)) + jitter


def resolve_host(url: str) -> str:
    host = urlparse(url).hostname
    if not host:
        raise ValueError("missing host")
    return socket.gethostbyname(host)


def is_private_ip(ip: str) -> bool:
    try:
        return ipaddress.ip_address(ip).is_private
    except ValueError:
        return True
