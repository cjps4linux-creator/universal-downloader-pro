"""Universal Downloader Pro — web archive worker with graceful degradation."""

from __future__ import annotations

import json
import os
import re
import secrets
from pathlib import Path
from typing import Optional

import requests
from bs4 import BeautifulSoup

from udp.core.downloader import download_file
from udp.core.assets import store_asset, sha256_file
from udp.models.db import Session, Job
from udp.models.db import update_knowledge_from_archive
from udp.security.sanitizer import sanitize_html
from udp.utils.paths import downloads_dir, task_dir, ensure_dirs
from udp.security.tunnel import tunnel_proxy_url

ensure_dirs()


def archive_web_page(url: str, task_id: str, *, max_assets: int = 200) -> dict:
    from urllib.parse import urljoin, urlparse

    base_dir = task_dir(task_id)
    assets_dir = base_dir / "assets"
    assets_dir.mkdir(parents=True, exist_ok=True)

    html_path = base_dir / "index.html"
    report_path = base_dir / "report.txt"
    failed_path = base_dir / "failed_assets.json"

    html_text, html_err = _fetch_html(url)
    if html_err or not html_text:
        return {"status": "failed", "error": html_err or "empty response"}

    soup = BeautifulSoup(html_text, "html.parser")
    assets = _extract_assets(soup, url)
    assets = assets[:max_assets]

    results: list[dict] = []
    failed: list[dict] = []
    total = len(assets)
    done = 0

    for asset in assets:
        done += 1
        _update_job_progress(task_id, int((done / max(total, 1)) * 100), total)
        asset_url = asset["url"]
        kind = asset["kind"]
        rel = asset.get("rel", "")
        try:
            local_name = _asset_filename(asset_url, kind)
            local_path = assets_dir / local_name
            if not local_path.exists():
                _, err = download_file(asset_url, local_path, task_id, proxy_url=tunnel_proxy_url())
                if err:
                    failed.append({"url": asset_url, "kind": kind, "error": err})
                    results.append({"url": asset_url, "kind": kind, "status": "failed"})
                    continue
            try:
                stored = store_asset(local_path)
                content_hash = sha256_file(stored)
            except Exception as exc:
                failed.append({"url": asset_url, "kind": kind, "error": f"asset_store:{exc}"})
                results.append({"url": asset_url, "kind": kind, "status": "failed"})
                continue
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
    try:
        update_knowledge_from_archive(url, results, failed)
    except Exception:
        pass
    return {"status": status, "html": str(html_path), "report": str(report_path), "failed": len(failed), "total": total}


def _update_job_progress(task_id: str, percent: int, total: Optional[int] = None) -> None:
    try:
        with Session() as session:
            job = session.get(Job, task_id)
            if job:
                extras = {}
                if total:
                    extras["bytes_total"] = total
                job.status = "running"
                job.error_message = json.dumps({"percent": percent})
                job.updated_at = __import__("datetime").datetime.now(__import__("datetime").timezone.utc)
                session.commit()
    except Exception:
        pass


def _finalize_job(task_id: str, status: str, dest: str, results: list[dict], failed: list[dict]) -> None:
    try:
        with Session() as session:
            job = session.get(Job, task_id)
            if job:
                job.status = status
                job.dest_path = dest
                job.finished_at = __import__("datetime").datetime.now(__import__("datetime").timezone.utc)
                job.error_message = json.dumps({"assets_ok": sum(1 for r in results if r["status"] == "ok"), "assets_failed": len(failed)})
                session.commit()
    except Exception:
        pass


def _fetch_html(url: str) -> tuple[Optional[str], Optional[str]]:
    try:
        r = requests.get(url, timeout=(10, 30), headers={"User-Agent": "Mozilla/5.0"})
        if r.status_code == 200:
            return r.text, None
        return None, f"http_{r.status_code}"
    except Exception as exc:
        return None, str(exc)


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
                assets.append({"kind": kind, "url": abs_url, "rel": tag.get("rel", [""])[0] if tag.get("rel") else ""})
    return assets


def _asset_filename(url: str, kind: str) -> str:
    from urllib.parse import urlparse

    parsed = urlparse(url)
    name = Path(parsed.path).name
    if not name or "." not in name:
        ext = _guess_ext(kind)
        name = f"asset_{secrets.token_hex(4)}{ext}"
    return re.sub(r"[^A-Za-z0-9._-]", "_", name)


def _guess_ext(kind: str) -> str:
    return { "image": ".img", "script": ".js", "stylesheet": ".css", "icon": ".ico", "audio": ".mp3", "video": ".mp4", "source": ".bin" }.get(kind, ".bin")


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
        status = r["status"]
        h = f" hash={r['hash'][:12]}" if r.get("hash") else ""
        lines.append(f"- [{status}] {r['url']}{h}")
    if failed:
        lines += ["", "## Failed Assets"]
        for f in failed:
            lines.append(f"- {f['url']} :: {f['error']}")
    return "\n".join(lines)
