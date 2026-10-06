"""Universal Downloader Pro — HTML sanitization and archive origin isolation."""

from __future__ import annotations

import html
import os
import re
from pathlib import Path
from typing import Optional

try:
    import nh3
    HAS_NH3 = True
except Exception:
    HAS_NH3 = False

from udp.utils.paths import downloads_dir, task_dir, ensure_dirs

ensure_dirs()


ALLOWED_TAGS = {
    "a", "abbr", "acronym", "b", "blockquote", "code", "del", "dd", "dl", "dt",
    "em", "h1", "h2", "h3", "h4", "h5", "h6", "i", "img", "ins", "kbd", "li",
    "ol", "p", "pre", "q", "s", "samp", "small", "span", "strike", "strong",
    "sub", "sup", "table", "tbody", "td", "tfoot", "th", "thead", "tr", "tt", "u",
    "ul", "br", "hr", "picture", "source", "track", "video", "audio",
}
ALLOWED_ATTRS = {
    "a": {"href", "title"},
    "img": {"src", "alt", "title", "width", "height", "loading"},
    "video": {"src", "controls", "width", "height", "poster", "autoplay", "loop", "muted"},
    "audio": {"src", "controls", "autoplay", "loop", "muted", "preload"},
    "source": {"src", "type", "media", "sizes"},
    "track": {"kind", "src", "srclang", "label", "default"},
    "table": {"border", "cellspacing", "cellpadding"},
    "td": {"colspan", "rowspan", "headers"},
    "th": {"colspan", "rowspan", "headers", "scope"},
    "span": {"class", "style"},
    "div": {"class", "style"},
}
ALLOWED_PROTOCOLS = {"http", "https", "mailto", "data"}
FRAGMENT = "body"


def sanitize_html(html_text: str, *, base_url: str = "") -> str:
    if not html_text:
        return ""
    if HAS_NH3:
        cleaned = nh3.clean(
            html_text,
            tags=ALLOWED_TAGS,
            attributes=ALLOWED_ATTRS,
            url_schemes=ALLOWED_PROTOCOLS,
            link_rel="noopener noreferrer",
            strip_comments=True,
        )
        return cleaned
    return _fallback_sanitize(html_text)


def _fallback_sanitize(html_text: str) -> str:
    text = html_text
    text = re.sub(r"<\s*script[^>]*>.*?<\s*/\s*script\s*>", "", text, flags=re.I | re.S)
    text = re.sub(r"<\s*style[^>]*>.*?<\s*/\s*style\s*>", "", text, flags=re.I | re.S)
    text = re.sub(r"on\w+\s*=\s*(['\"])[^'\"]*\1", "", text, flags=re.I)
    text = re.sub(r"on\w+\s*=\s*[^\s>]+", "", text, flags=re.I)
    text = re.sub(r"javascript\s*:", "javascript_disabled:", text, flags=re.I)
    return text


def sanitize_filename(name: str) -> str:
    name = re.sub(r'[<>:"/\\|?*\x00-\x1F]', "_", name)
    name = re.sub(r"\s+", "_", name).strip("_")
    if not name:
        name = "archive"
    return name[:180]


def validate_archive_path(path: Path, root: Path) -> Optional[Path]:
    try:
        resolved = path.resolve()
        root_resolved = root.resolve()
        if not str(resolved).startswith(str(root_resolved)):
            return None
        return resolved
    except Exception:
        return None


def archive_safe_headers() -> dict:
    return {
        "Content-Security-Policy": "default-src 'none'; img-src 'self' data:; style-src 'self' 'unsafe-inline'; font-src 'self'; media-src 'self'; sandbox",
        "X-Content-Type-Options": "nosniff",
        "X-Frame-Options": "DENY",
        "Referrer-Policy": "no-referrer",
    }


def archive_origin_port() -> int:
    port_file = downloads_dir() / "archive_origin.port"
    if port_file.exists():
        try:
            return int(port_file.read_text(encoding="utf-8").strip())
        except ValueError:
            pass
    return None


def is_archive_origin_request(request) -> bool:
    from flask import request as flask_request
    host = flask_request.host.split(":")[0] if ":" in flask_request.host else flask_request.host
    return host == "archive.localhost"
