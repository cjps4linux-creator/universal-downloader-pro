"""Universal Downloader Pro  -  anti-blocking HTTP client and blocked-state machine."""

from __future__ import annotations

from enum import Enum
from typing import Optional

from curl_cffi import requests


class BlockClass(str, Enum):
    TRANSIENT_NET = "TRANSIENT_NET"
    RATE_LIMIT = "RATE_LIMIT"
    BLOCKED = "BLOCKED"
    AUTH = "AUTH"
    NOT_FOUND = "NOT_FOUND"
    CONTENT_INTEGRITY = "CONTENT_INTEGRITY"
    EXTRACTOR_BROKEN = "EXTRACTOR_BROKEN"
    LOCAL_IO = "LOCAL_IO"
    POLICY = "POLICY"
    TUNNEL_DOWN = "TUNNEL_DOWN"
    OK = "OK"


class BlockedError(Exception):
    def __init__(self, cls: BlockClass, message: str, retryable: bool = True, recovery_hint: str = ""):
        super().__init__(message)
        self.cls = cls
        self.retryable = retryable
        self.recovery_hint = recovery_hint


def classify_response(status_code: int, text: str, retry_after: Optional[str] = None) -> BlockClass:
    if status_code in (429,):
        return BlockClass.RATE_LIMIT
    if status_code in (401, 403):
        if "captcha" in text.lower() or "cloudflare" in text.lower() or "verify you are human" in text.lower():
            return BlockClass.BLOCKED
        if "login" in text.lower() or "sign in" in text.lower():
            return BlockClass.AUTH
        return BlockClass.BLOCKED
    if status_code in (404, 410):
        return BlockClass.NOT_FOUND
    if status_code in (500, 502, 503, 504):
        return BlockClass.TRANSIENT_NET
    if status_code == 451:
        return BlockClass.BLOCKED
    if status_code == 200:
        if len(text) < 500 and any(k in text.lower() for k in ["captcha", "cloudflare", "verify you are human", "consent"]):
            return BlockClass.BLOCKED
        return BlockClass.OK
    return BlockClass.TRANSIENT_NET


def _supported_impersonate() -> str:
    try:
        candidates = ["chrome120", "chrome110", "chrome"]
        for candidate in candidates:
            try:
                requests.get("https://example.com", impersonate=candidate, timeout=(3, 5))
                return candidate
            except Exception:
                continue
    except Exception:
        pass
    return ""


def chrome_headers(url: str) -> dict:
    return {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9",
        "Accept-Encoding": "gzip, deflate, br",
        "Referer": __import__("urllib.parse").parse.urlparse(url).scheme + "://" + __import__("urllib.parse").parse.urlparse(url).netloc + "/",
        "Sec-Fetch-Dest": "document",
        "Sec-Fetch-Mode": "navigate",
        "Sec-Fetch-Site": "same-origin",
        "Sec-Ch-Ua": '"Chromium";v="131", "Not_A Brand";v="24"',
        "Sec-Ch-Ua-Mobile": "?0",
        "Sec-Ch-Ua-Platform": '"Windows"',
        "Upgrade-Insecure-Requests": "1",
    }


def fetch_with_anti_block(url: str, *, cookies: Optional[dict] = None, proxy: Optional[str] = None, timeout: int = 30) -> tuple[int, str, BlockClass]:
    try:
        kwargs = {
            "cookies": cookies,
            "proxies": {"https": proxy, "http": proxy} if proxy else None,
            "timeout": (10, timeout),
            "allow_redirects": True,
        }
        impersonate = _supported_impersonate()
        if impersonate:
            kwargs["impersonate"] = impersonate
        else:
            kwargs["headers"] = chrome_headers(url)

        r = requests.get(url, **kwargs)
        block = classify_response(r.status_code, r.text, r.headers.get("Retry-After"))
        return r.status_code, r.text, block
    except Exception as exc:
        if "timeout" in str(exc).lower():
            raise BlockedError(BlockClass.TRANSIENT_NET, str(exc), retryable=True, recovery_hint="Retry with longer timeout or different upstream")
        raise BlockedError(BlockClass.TRANSIENT_NET, str(exc), retryable=True, recovery_hint="Check network or tunnel state")
