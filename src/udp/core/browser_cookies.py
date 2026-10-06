"""Universal Downloader Pro — browser cookie extraction for archive jobs."""

from __future__ import annotations

from typing import Optional


def load_browser_cookies_for_url(url: str, browser: str) -> Optional[dict]:
    """Return cookies as a name->value dict for the given URL/browser."""
    try:
        import browser_cookie3
        from urllib.parse import urlparse
        hostname = urlparse(url).hostname or ""
        browser_lower = browser.lower()
        if browser_lower in {"chrome", "chromium", "chrome-beta"}:
            loader = browser_cookie3.chrome
        elif browser_lower in {"edge", "microsoft-edge"}:
            loader = browser_cookie3.edge
        elif browser_lower in {"firefox"}:
            loader = browser_cookie3.firefox
        elif browser_lower in {"opera"}:
            loader = browser_cookie3.opera
        elif browser_lower in {"brave"}:
            loader = browser_cookie3.brave
        else:
            loader = browser_cookie3.chrome
        cookies = loader(domain_name=hostname)
        out: dict[str, str] = {}
        for c in cookies:
            if c.name:
                out[c.name] = c.value
        return out or None
    except Exception:
        return None
