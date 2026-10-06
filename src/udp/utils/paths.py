"""Path and filesystem helpers for Universal Downloader Pro."""

from __future__ import annotations

from pathlib import Path


def data_dir() -> Path:
    base = Path(__import__("os").environ.get("LOCALAPPDATA", str(Path.home() / "AppData/Local")))
    return base / "UniversalDownloaderPro"


def downloads_dir() -> Path:
    return data_dir() / "downloads"


def task_dir(task_id: str) -> Path:
    return downloads_dir() / task_id


def ensure_dirs() -> None:
    downloads_dir().mkdir(parents=True, exist_ok=True)
