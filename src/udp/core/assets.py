"""Universal Downloader Pro — content-addressed asset store and resume helpers."""

from __future__ import annotations

import hashlib
import os
from pathlib import Path
from typing import Optional

from udp.utils.paths import downloads_dir, ensure_dirs

ensure_dirs()


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        while True:
            chunk = f.read(1024 * 1024)
            if not chunk:
                break
            h.update(chunk)
    return h.hexdigest()


def content_addressed_path(content_hash: str, suffix: str) -> Path:
    ab = content_hash[:2]
    cd = content_hash[2:4]
    p = downloads_dir() / "assets" / ab / cd / content_hash
    p.parent.mkdir(parents=True, exist_ok=True)
    return p.with_suffix(suffix)


def unique_dest_path(base: Path) -> Path:
    if not base.exists():
        return base
    stem = base.stem
    suffix = base.suffix
    parent = base.parent
    idx = 1
    while True:
        candidate = parent / f"{stem}_{idx}{suffix}"
        if not candidate.exists():
            return candidate
        idx += 1


def part_path(dest: Path) -> Path:
    return dest.with_suffix(dest.suffix + ".part")


def resume_bytes(part: Path) -> int:
    if part.exists():
        try:
            return part.stat().st_size
        except OSError:
            pass
    return 0


def move_part_to_final(part: Path, dest: Path) -> None:
    if part.exists():
        part.replace(dest)
    elif dest.exists():
        pass
    else:
        raise FileNotFoundError(f"missing completed file: {dest}")


def store_asset(source: Path, content_hash: Optional[str] = None) -> Path:
    if not source.exists():
        raise FileNotFoundError(f"source missing: {source}")
    if content_hash is None:
        content_hash = sha256_file(source)
    suffix = source.suffix or ".bin"
    dest = content_addressed_path(content_hash, suffix)
    if not dest.exists():
        temp = dest.with_suffix(dest.suffix + ".part")
        temp.parent.mkdir(parents=True, exist_ok=True)
        os.replace(source, temp)
        temp.replace(dest)
    return dest
