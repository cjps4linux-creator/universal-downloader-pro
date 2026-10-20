"""Universal Downloader Pro — resilient download engine."""

from __future__ import annotations

import hashlib
import time
from pathlib import Path
from typing import Optional

from curl_cffi import requests as curl_requests

from udp.core.anti_block import _supported_impersonate
from udp.models.db import Job, session
from udp.utils.paths import downloads_dir, ensure_dirs

ensure_dirs()


class CircuitBreaker:
    def __init__(self, threshold: int = 5, cooldown: float = 60.0):
        self.threshold = threshold
        self.cooldown = cooldown
        self.failures: dict[str, int] = {}
        self.opened_until: dict[str, float] = {}

    def record_failure(self, domain: str) -> None:
        now = time.time()
        if self.opened_until.get(domain, 0) > now:
            return
        self.failures[domain] = self.failures.get(domain, 0) + 1
        if self.failures[domain] >= self.threshold:
            self.opened_until[domain] = now + self.cooldown
            self.failures[domain] = 0

    def record_success(self, domain: str) -> None:
        self.failures[domain] = 0
        self.opened_until.pop(domain, None)

    def is_open(self, domain: str) -> bool:
        return self.opened_until.get(domain, 0) > time.time()


circuit = CircuitBreaker()


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


def _request_with_retry(method: str, url: str, *, proxy_url: Optional[str] = None, stream: bool = False, impersonate: bool = True, **kwargs):
    kwargs.setdefault("timeout", (10, 30))
    if proxy_url:
        kwargs.setdefault("proxies", {"http": proxy_url, "https": proxy_url})
    kwargs.setdefault("allow_redirects", True)
    if impersonate:
        imp = _supported_impersonate()
        if imp:
            kwargs.setdefault("impersonate", imp)
    last_exc: Optional[Exception] = None
    for attempt in range(4):
        try:
            if stream:
                return curl_requests.request(method, url, **kwargs)
            return curl_requests.request(method, url, **kwargs)
        except Exception as exc:
            last_exc = exc
            if attempt < 3:
                time.sleep(min(2 ** attempt, 10))
    raise last_exc


def download_file(url: str, dest: Path, job_id: str, *, resume: bool = True, proxy_url: Optional[str] = None) -> tuple[Path, Optional[str]]:
    from urllib.parse import urlparse

    parsed = urlparse(url)
    domain = parsed.hostname or "unknown"

    if circuit.is_open(domain):
        raise RuntimeError(f"circuit_open:{domain}")

    dest.parent.mkdir(parents=True, exist_ok=True)
    part = dest.with_suffix(dest.suffix + ".part")

    headers = {}
    bytes_done = 0
    if resume and part.exists():
        bytes_done = part.stat().st_size
        headers["Range"] = f"bytes={bytes_done}-"

    try:
        r = _request_with_retry("GET", url, proxy_url=proxy_url, headers=headers)
        if r.status_code == 403:
            circuit.record_failure(domain)
            return dest, f"http_403:{r.status_code}"
        if r.status_code == 429:
            retry_after = r.headers.get("Retry-After")
            circuit.record_failure(domain)
            return dest, f"rate_limited:{retry_after}"
        if r.status_code not in (200, 206):
            circuit.record_failure(domain)
            return dest, f"http_{r.status_code}"

        mode = "ab" if bytes_done > 0 and r.status_code == 206 else "wb"
        data = r.content
        with part.open(mode) as f:
            f.write(data)
            bytes_done += len(data)
            _update_job_progress(job_id, bytes_done)

        try:
            r.close()
        except Exception:
            pass

        # Retry rename on Windows because antivirus/scanners can lock the .part briefly
        last_rename_err = None
        for attempt in range(20):
            try:
                part.replace(dest)
                last_rename_err = None
                break
            except PermissionError as exc:
                last_rename_err = exc
                if attempt < 19:
                    time.sleep(0.5)
                    continue
            except FileNotFoundError:
                last_rename_err = None
                break
            except OSError as exc:
                last_rename_err = exc
                if attempt < 19:
                    time.sleep(0.5)
                    continue
        if last_rename_err:
            return dest, f"file_locked:{part.name}:{last_rename_err}"

        circuit.record_success(domain)
        return dest, None
    except Exception as exc:
        circuit.record_failure(domain)
        raise


def _update_job_progress(job_id: str, bytes_done: int) -> None:
    try:
        with session() as db:
            job = db.get(Job, job_id)
            if job:
                job.bytes_done = bytes_done
                job.updated_at = __import__("datetime").datetime.now(__import__("datetime").timezone.utc)
                db.commit()
    except Exception:
        pass
