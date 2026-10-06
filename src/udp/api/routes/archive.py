"""Universal Downloader Pro — API routes: archive origin isolation and sanitization."""

from __future__ import annotations

import json
import os
import socket
import threading
import time
from pathlib import Path
from typing import Optional

from flask import Blueprint, Response, jsonify, request, send_from_directory

from udp.models.db import Session, Job
from udp.security.sanitizer import (
    ALLOWED_PROTOCOLS,
    ALLOWED_TAGS,
    archive_origin_port,
    archive_safe_headers,
    is_archive_origin_request,
    sanitize_filename,
    sanitize_html,
    validate_archive_path,
)
from udp.utils.paths import downloads_dir, task_dir, ensure_dirs
from udp.core.assets import unique_dest_path
from udp.core.downloader import circuit, download_file
from udp.workers.scheduler import submit, _finalize

bp = Blueprint("archive", __name__)
ensure_dirs()


@bp.get("/api/archives/<task_id>")
def get_archive(task_id: str):
    with Session() as session:
        job = session.get(Job, task_id)
        if not job or not job.dest_path:
            return jsonify({"error": "not found"}), 404
        root = task_dir(task_id)
        html_path = root / "index.html"
        if not html_path.exists():
            return jsonify({"error": "archive not ready"}), 404
        raw = html_path.read_text(encoding="utf-8", errors="ignore")
        cleaned = sanitize_html(raw, base_url=job.url)
        safe_path = root / "index.sanitized.html"
        safe_path.write_text(cleaned, encoding="utf-8")
        return Response(
            cleaned,
            mimetype="text/html; charset=utf-8",
            headers=archive_safe_headers(),
        )


@bp.get("/api/archives/<task_id>/assets/<path:filename>")
def get_archive_asset(task_id: str, filename: str):
    root = task_dir(task_id)
    assets_root = root / "assets"
    target = validate_archive_path(assets_root / filename, assets_root)
    if not target or not target.exists():
        return jsonify({"error": "not found"}), 404
    return send_from_directory(str(assets_root), filename)


@bp.get("/api/archives/<task_id>/preview")
def archive_preview(task_id: str):
    root = task_dir(task_id)
    html_path = root / "index.html"
    report_path = root / "report.txt"
    assets_root = root / "assets"
    assets = []
    if assets_root.exists():
        for p in sorted(assets_root.iterdir()):
            if p.is_file():
                assets.append({"name": p.name, "size": p.stat().st_size, "url": f"/api/archives/{task_id}/assets/{p.name}"})
    report_text = ""
    if report_path.exists():
        report_text = report_path.read_text(encoding="utf-8", errors="ignore")[:4000]
    html_exists = html_path.exists()
    return jsonify({
        "task_id": task_id,
        "html_exists": html_exists,
        "html_url": f"/api/archives/{task_id}" if html_exists else None,
        "assets_count": len(assets),
        "assets": assets[:50],
        "report_preview": report_text,
    })


@bp.get("/api/firewall/commands")
def firewall_commands():
    from udp.security.firewall import allow_loopback, block_egress_except_tunnel
    port_raw = request.args.get("port")
    port = None
    if port_raw and port_raw.isdigit():
        port = int(port_raw)
    if not port:
        return jsonify({"commands": [
            'netsh advfirewall firewall add rule name="UDP Allow Loopback" dir=out action=allow protocol=any localip=127.0.0.1 profile=private',
            'netsh advfirewall firewall add rule name="UDP Block Egress" dir=out action=block remoteip=any localip!=127.0.0.1 profile=private',
        ], "note": "Provide a tunnel port to generate an allow rule for that proxy port."})
    cmds = [
        f'netsh advfirewall firewall add rule name="UDP Allow Loopback" dir=out action=allow protocol=any localip=127.0.0.1 profile=private',
        f'netsh advfirewall firewall add rule name="UDP Allow Proxy" dir=out action=allow protocol=TCP,UDP localport={port} profile=private',
        f'netsh advfirewall firewall add rule name="UDP Block Egress" dir=out action=block remoteip=any localip!=127.0.0.1 profile=private',
    ]
    return jsonify({"commands": cmds, "port": port})

@bp.get("/api/archives/<task_id>/css-preview")
def css_preview(task_id: str):
    filename = request.args.get("filename", "")
    if not filename:
        return jsonify({"error": "missing filename"}), 400
    root = task_dir(task_id)
    assets_root = root / "assets"
    target = validate_archive_path(assets_root / filename, assets_root)
    if not target or not target.exists():
        return jsonify({"error": "not found"}), 404
    css_text = target.read_text(encoding="utf-8", errors="ignore")
    safe_css = css_text.replace("</style>", "<\\/style>")
    html = f"""<!doctype html>
<html>
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{filename} preview</title>
<style>
  body {{ font-family: system-ui, sans-serif; margin: 0; padding: 24px; background: #f5f5f5; color: #222; }}
  .wrap {{ max-width: 960px; margin: 0 auto; }}
  .bar {{ display:flex; gap: 12px; align-items:center; justify-content:space-between; }}
  pre {{ background:#111; color:#f8f8f2; padding:12px; border-radius:8px; overflow:auto; font-size:12px; }}
  .sample {{ margin-top: 16px; padding: 16px; border: 1px solid #ddd; border-radius: 8px; background:#fff; }}
</style>
<style>
  /* BEGIN loaded stylesheet */
  {safe_css}
  /* END loaded stylesheet */
</style>
</head>
<body>
  <div class="wrap">
    <div class="bar">
      <h1 style="font-size:14px;margin:0">{filename}</h1>
      <a href="/api/archives/{task_id}/assets/{filename}" target="_blank">Raw</a>
    </div>
    <pre style="margin-top:12px">{_escape(css_text)}</pre>
    <div class="sample">
      <h2>Sample heading</h2>
      <p>This area is styled by the stylesheet above, if it applies to these elements.</p>
      <button>Button</button>
      <a href="#">Link</a>
      <table><tr><th>A</th><th>B</th></tr><tr><td>1</td><td>2</td></tr></table>
    </div>
  </div>
</body>
</html>"""
    return Response(html, mimetype="text/html; charset=utf-8")


def _escape(s: str) -> str:
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


@bp.get("/api/archives/<task_id>/failed_assets")
def get_failed_assets(task_id: str):
    root = task_dir(task_id)
    failed_path = root / "failed_assets.json"
    if not failed_path.exists():
        return jsonify({"error": "no failed assets record"}), 404
    try:
        data = json.loads(failed_path.read_text(encoding="utf-8"))
    except Exception:
        return jsonify({"error": "invalid failed assets record"}), 500
    return jsonify(data)


@bp.post("/api/archives/<task_id>/salvage")
def salvage_archive(task_id: str):
    with Session() as session:
        job = session.get(Job, task_id)
        if not job:
            return jsonify({"error": "not found"}), 404
        root = task_dir(task_id)
        has_archive_contents = (root / "index.html").exists() or (root / "assets").exists() or (root / "report.txt").exists()
        if job.mode != "archive" and not has_archive_contents:
            return jsonify({"error": "not an archive job"}), 400
        job.status = "salvaging"
        job.error_message = None
        session.commit()
    submit(_salvage_worker, task_id)
    return jsonify({"task_id": task_id, "status": "salvaging"}), 202


def _salvage_worker(task_id: str) -> None:
    root = task_dir(task_id)
    failed_path = root / "failed_assets.json"
    if not failed_path.exists():
        _finalize(task_id, "succeeded", "")
        return
    try:
        raw = failed_path.read_text(encoding="utf-8")
        payload = json.loads(raw)
    except Exception:
        payload = {"failed": []}
    if isinstance(payload, list):
        urls = payload
    else:
        urls = payload.get("failed") or []
    assets_dir = root / "assets"
    assets_dir.mkdir(parents=True, exist_ok=True)

    # Reset circuit breakers for domains in the failed list so retries can proceed.
    try:
        domains = {Path((item if isinstance(item, str) else item.get("url", ""))).hostname or "" for item in urls}
        for domain in domains:
            if domain:
                circuit.record_success(domain)
    except Exception:
        pass

    # Remove zero-byte .part files from earlier aborted attempts.
    for part in assets_dir.glob("*.part"):
        try:
            if part.exists() and part.stat().st_size == 0:
                part.unlink()
        except Exception:
            pass

    recovered = []
    still_failed = []
    for item in urls:
        url = item if isinstance(item, str) else item.get("url")
        if not url:
            continue
        try:
            from urllib.parse import urlparse
            parsed = urlparse(url)
            local_name = Path(parsed.path).name or f"asset_{len(recovered)}.bin"
            target = assets_dir / local_name
            target = unique_dest_path(target)
            _, err = download_file(url, target, task_id)
            if err:
                still_failed.append({"url": url, "error": err})
            else:
                recovered.append({"url": url, "path": str(target)})
        except Exception as exc:
            still_failed.append({"url": url, "error": str(exc)})
    failed_path.write_text(json.dumps({"failed": still_failed}, ensure_ascii=False), encoding="utf-8")
    status = "succeeded" if not still_failed else "partial"
    error_payload = json.dumps({"recovered": len(recovered), "failed": len(still_failed)})
    _finalize(task_id, status, "", error_message=error_payload)


@bp.post("/api/sanitize")
def sanitize_endpoint():
    body = request.get_json(silent=True) or {}
    html_text = body.get("html", "")
    base_url = body.get("base_url", "")
    cleaned = sanitize_html(html_text, base_url=base_url)
    return jsonify({"html": cleaned})
