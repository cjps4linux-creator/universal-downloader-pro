"""Universal Downloader Pro — anti-blocking web archive worker."""

from __future__ import annotations

import json
import re
import secrets
from pathlib import Path
from typing import Optional

from bs4 import BeautifulSoup

from udp.core.anti_block import fetch_with_anti_block, BlockedError, BlockClass
from udp.core.downloader import download_file, sha256_file
from udp.models.db import Job, session
from udp.utils.paths import task_dir, ensure_dirs
from udp.security.tunnel import tunnel_proxy_url

ensure_dirs()


def archive_web_page_anti_block(url: str, task_id: str, *, max_assets: int = 200, proxy: Optional[str] = None, cookies: Optional[dict] = None) -> dict:
    base_dir = task_dir(task_id)
    assets_dir = base_dir / "assets"
    assets_dir.mkdir(parents=True, exist_ok=True)

    html_path = base_dir / "index.html"
    report_path = base_dir / "report.txt"
    failed_path = base_dir / "failed_assets.json"

    # Tier 0/1: direct fetch with curl_cffi impersonation
    try:
        status_code, html_text, block = fetch_with_anti_block(url, cookies=cookies, proxy=proxy)
    except BlockedError as exc:
        return _blocked_result(task_id, exc)

    if block != BlockClass.OK:
        return _blocked_result(task_id, BlockedError(block, f"HTTP {status_code}", retryable=block in (BlockClass.TRANSIENT_NET, BlockClass.RATE_LIMIT), recovery_hint="Try Tier 2 cookies or Tier 3 headless browser"))

    soup = BeautifulSoup(html_text, "html.parser")
    assets = _extract_assets(soup, url)[:max_assets]

    results: list[dict] = []
    failed: list[dict] = []
    total = len(assets)
    done = 0

    for asset in assets:
        done += 1
        _update_progress(task_id, int((done / max(total, 1)) * 100), total)
        asset_url = asset["url"]
        kind = asset["kind"]
        try:
            local_name = _asset_filename(asset_url, kind)
            local_path = assets_dir / local_name
            if not local_path.exists():
                _, err = download_file(asset_url, local_path, task_id, proxy_url=tunnel_proxy_url())
                if err:
                    failed.append({"url": asset_url, "kind": kind, "error": err})
                    results.append({"url": asset_url, "kind": kind, "status": "failed"})
                    continue
            content_hash = sha256_file(local_path) if local_path.exists() else None
            results.append({"url": asset_url, "kind": kind, "status": "ok", "hash": content_hash})
        except Exception as exc:
            failed.append({"url": asset_url, "kind": kind, "error": str(exc)})
            results.append({"url": asset_url, "kind": kind, "status": "failed"})

    _rewrite_links(soup, url, assets_dir.name)
    html_path.write_text(str(soup), encoding="utf-8")

    report = _build_report(url, results, failed)
    report_path.write_text(report, encoding="utf-8")
    failed_path.write_text(json.dumps(failed, ensure_ascii=False, indent=2), encoding="utf-8")

    status = "partial" if failed else "succeeded"
    _finalize_job(task_id, status, str(html_path), results, failed)
    return {"status": status, "html": str(html_path), "report": str(report_path), "failed": len(failed), "total": total}


def _blocked_result(task_id: str, exc: BlockedError) -> dict:
    _finalize_job(task_id, "blocked", "", [], [])
    return {"status": "blocked", "error": str(exc), "block_class": exc.cls.value, "retryable": exc.retryable, "recovery_hint": exc.recovery_hint}


def _update_progress(task_id: str, percent: int, total: Optional[int] = None) -> None:
    try:
        with session() as db:
            job = db.get(Job, task_id)
            if job:
                job.status = "running"
                job.error_message = json.dumps({"percent": percent, "assets_total": total})
                job.updated_at = __import__("datetime").datetime.now(__import__("datetime").timezone.utc)
                db.commit()
    except Exception:
        pass


def _finalize_job(task_id: str, status: str, dest: str, results: list[dict], failed: list[dict]) -> None:
    try:
        with session() as db:
            job = db.get(Job, task_id)
            if job:
                job.status = status
                job.dest_path = dest
                job.finished_at = __import__("datetime").datetime.now(__import__("datetime").timezone.utc)
                job.error_message = json.dumps({"assets_ok": sum(1 for r in results if r["status"] == "ok"), "assets_failed": len(failed)})
                db.commit()
    except Exception:
        pass


def _extract_assets(soup: BeautifulSoup, base_url: str) -> list[dict]:
    from urllib.parse import urljoin

    assets: list[dict] = []
    for tag in soup.find_all(["img", "script", "link", "audio", "video", "source"]):
        kind = None
        url_attr = None
        if tag.name == "img":
            kind = "image"
            url_attr = "src"
        elif tag.name == "script":
            kind = "script"
            url_attr = "src"
        elif tag.name == "link":
            rel = (tag.get("rel") or [""])[0]
            if rel in {"stylesheet", "icon", "preload", "modulepreload"}:
                kind = rel
                url_attr = "href"
        elif tag.name == "audio":
            kind = "audio"
            url_attr = "src"
        elif tag.name == "video":
            kind = "video"
            url_attr = "src"
        elif tag.name == "source":
            kind = "source"
            url_attr = "src"
        if kind and url_attr:
            raw = tag.get(url_attr)
            if raw and not raw.startswith("data:"):
                abs_url = urljoin(base_url, raw)
                assets.append({"kind": kind, "url": abs_url})
    return assets


def _asset_filename(url: str, kind: str) -> str:
    from urllib.parse import urlparse

    parsed = urlparse(url)
    name = Path(parsed.path).name
    if not name or "." not in name:
        ext = {"image": ".img", "script": ".js", "stylesheet": ".css", "icon": ".ico", "audio": ".mp3", "video": ".mp4", "source": ".bin"}.get(kind, ".bin")
        name = f"asset_{secrets.token_hex(4)}{ext}"
    return re.sub(r"[^A-Za-z0-9._-]", "_", name)


def _rewrite_links(soup: BeautifulSoup, base_url: str, assets_dir_name: str) -> None:
    from urllib.parse import urljoin

    for tag in soup.find_all(["a"]):
        href = tag.get("href")
        if href and not href.startswith(("#", "javascript:", "mailto:", "data:")) and not href.startswith("http"):
            tag["href"] = urljoin(base_url, href)
    for tag in soup.find_all(["img", "script", "link", "audio", "video", "source"]):
        attr = "src" if tag.name != "link" else "href"
        raw = tag.get(attr)
        if raw and not raw.startswith(("data:", "http:", "https:")):
            tag[attr] = f"{assets_dir_name}/{raw}"


def _build_report(url: str, results: list[dict], failed: list[dict]) -> str:
    ok = sum(1 for r in results if r["status"] == "ok")
    lines = [
        f"URL: {url}",
        f"Status: {'partial' if failed else 'succeeded'}",
        f"Assets: {ok}/{len(results)} ok, {len(failed)} failed",
        "",
        "## Asset Inventory",
    ]
    for r in results:
        h = f" hash={r['hash'][:12]}" if r.get("hash") else ""
        lines.append(f"- [{r['status']}] {r['url']}{h}")
    if failed:
        lines += ["", "## Failed Assets"]
        for f in failed:
            lines.append(f"- {f['url']} :: {f['error']}")
    return "\n".join(lines)
