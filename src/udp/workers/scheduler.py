"""Universal Downloader Pro — durable job scheduler and worker pool."""

from __future__ import annotations

import subprocess
import threading
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Optional

from udp.models.db import Session, Job
from udp.utils.paths import ensure_dirs

ensure_dirs()

_executor = ThreadPoolExecutor(max_workers=2, thread_name_prefix="udp-worker")
_running: set[str] = set()
_lock = threading.Lock()


def submit(func, *args, **kwargs):
    future = _executor.submit(func, *args, **kwargs)
    return future


def cancel_job(job_id: str) -> bool:
    with _lock:
        return job_id in _running


def worker_count() -> int:
    with _lock:
        return len(_running)


def run_archive_job(url: str, task_id: str) -> None:
    run_archive_job_anti_block(url, task_id)


def run_archive_job_anti_block(url: str, task_id: str, *, proxy: Optional[str] = None, cookies: Optional[dict] = None) -> None:
    with _lock:
        _running.add(task_id)
    try:
        from udp.core.archiver_anti_block import archive_web_page_anti_block
        result = archive_web_page_anti_block(url, task_id, proxy=proxy, cookies=cookies)
    except Exception as exc:
        _finalize(task_id, "failed", "", error_message=str(exc))
    finally:
        with _lock:
            _running.discard(task_id)


def run_stream_job(url: str, dest: Path, job_id: str) -> None:
    run_stream_job_with_cookies(url, dest, job_id)


def run_stream_job_with_cookies(url: str, dest: Path, job_id: str, *, cookies: Optional[str] = None, browser: Optional[str] = None, audio_only: bool = False, playlist: bool = False, audio_format: str = "mp3") -> None:
    with _lock:
        _running.add(job_id)
    try:
        from udp.workers.ytdlp import stream_with_ytdlp
        result = stream_with_ytdlp(url, dest, job_id, cookies=cookies, cookies_from_browser=browser, audio_only=audio_only, playlist=playlist, audio_format=audio_format)
        try:
            path, err = result
        except Exception as exc:
            import traceback; traceback.print_exc(); print("[debug] stream_with_ytdlp returned:", type(result), result); raise
        if err:
            # stream_with_ytdlp already called _finalize on failure
            pass
        else:
            # stream_with_ytdlp already called _finalize on success
            pass
    except Exception as exc:
        _finalize(job_id, "failed", str(dest), error_message=str(exc))
    finally:
        with _lock:
            _running.discard(job_id)


def _finalize(job_id: str, status: str, dest: str, error_message: Optional[str] = None) -> None:
    try:
        with Session() as session:
            job = session.get(Job, job_id)
            if job:
                job.status = status
                job.dest_path = dest
                job.error_message = error_message
                job.finished_at = __import__("datetime").datetime.now(__import__("datetime").timezone.utc)
                session.commit()
    except Exception:
        pass
