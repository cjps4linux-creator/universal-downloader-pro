"""Universal Downloader Pro — API routes: system, settings, health, export, tunnel."""

from __future__ import annotations

import os
from pathlib import Path

from flask import Blueprint, jsonify, request, send_file

from udp.models.db import Setting, Job, session
from udp.utils.paths import downloads_dir
from udp.security.tunnel import set_proxy_url, egress_ip, dns_leak_test, tunnel_port, tunnel_proxy_url
from udp.security.firewall import allow_loopback, block_egress_except_tunnel
from udp.security.ssrf import validate_url, resolve_and_validate

bp = Blueprint("system", __name__)


@bp.get("/api/settings")
def get_settings():
    with session() as db:
        rows = db.query(Setting).all()
        return jsonify({r.key: r.value for r in rows})


@bp.put("/api/settings")
def put_settings():
    body = request.get_json(silent=True) or {}
    if not isinstance(body, dict):
        return jsonify({"error": "settings must be a JSON object"}), 400
    with session() as db:
        for key, value in body.items():
            row = db.get(Setting, key)
            if row:
                row.value = str(value)
            else:
                db.add(Setting(key=str(key), value=str(value)))
        db.commit()
    return jsonify({"updated": list(body.keys())})


@bp.get("/api/history")
def get_history():
    status = (request.args.get("status") or "").strip().lower()
    mode = (request.args.get("mode") or "").strip().lower()
    q = (request.args.get("q") or "").strip().lower()
    with session() as db:
        query = db.query(Job)
        if status:
            query = query.filter(Job.status == status)
        if mode:
            query = query.filter(Job.mode == mode)
        if q:
            query = query.filter(Job.url.ilike(f"%{q}%"))
        rows = query.order_by(Job.created_at.desc()).limit(200).all()
        return jsonify([
            {
                "task_id": r.id,
                "url": r.url,
                "mode": r.mode,
                "status": r.status,
                "created_at": r.created_at.isoformat() if r.created_at else None,
                "finished_at": r.finished_at.isoformat() if r.finished_at else None,
            }
            for r in rows
        ])


@bp.post("/api/playbook/regenerate")
def regenerate_playbook():
    from udp.knowledge.pipeline import build_playbook
    path = build_playbook(force=True)
    return jsonify({"playbook": str(path)})


@bp.post("/api/export")
def export_manifest():
    body = request.get_json(silent=True) or {}
    fmt = (body.get("format") or "json").lower()
    task_id = (body.get("task_id") or "").strip()
    if fmt not in {"json", "csv", "md"}:
        return jsonify({"error": "unsupported format"}), 400
    with session() as db:
        job = db.get(Job, task_id) if task_id else None
        if not job:
            return jsonify({"error": "task_id required and must exist"}), 400
        payload = {
            "task_id": job.id,
            "url": job.url,
            "mode": job.mode,
            "status": job.status,
            "dest_path": job.dest_path,
        }
    if fmt == "json":
        return jsonify(payload)
    if fmt == "md":
        text = "\n".join(f"**{k}**: {v}" for k, v in payload.items())
        return jsonify({"markdown": text})
    csv_text = ",".join(payload.keys()) + "\n" + ",".join(str(v) for v in payload.values())
    return jsonify({"csv": csv_text})


@bp.get("/api/playbook")
def get_playbook():
    from udp.knowledge.pipeline import build_playbook
    path = build_playbook()
    return send_file(str(path), mimetype="text/markdown")


@bp.get("/api/training/export")
def training_export():
    from udp.knowledge.pipeline import export_training
    path = export_training(from_history=True)
    return send_file(str(path), mimetype="application/jsonl")


@bp.get("/api/tunnel/status")
def tunnel_status():
    proxy_url = tunnel_proxy_url()
    return jsonify({
        "running": proxy_url is not None,
        "proxy_url": proxy_url,
        "mode": "manual" if proxy_url else "unavailable",
    })


@bp.post("/api/tunnel/start")
def tunnel_start():
    body = request.get_json(silent=True) or {}
    upstream = (body.get("upstream") or "").strip()
    if not upstream:
        return jsonify({"error": "upstream is required"}), 400
    return jsonify({"error": "App-sidecar tunnel is unavailable in this build. Use /api/tunnel/proxy to set a manual proxy URL."}), 501


@bp.post("/api/tunnel/stop")
def tunnel_stop():
    set_proxy_url(None)
    return jsonify({"stopped": True, "mode": "manual proxy cleared"})


@bp.get("/api/tunnel/egress")
def tunnel_egress():
    proxy = tunnel_proxy_url()
    direct = egress_ip(None)
    via_tunnel = egress_ip(proxy) if proxy else {"error": "no manual proxy configured"}
    return jsonify({"direct": direct, "tunnel": via_tunnel, "proxy_url": proxy})


@bp.get("/api/tunnel/dns-leak")
def tunnel_dns_leak():
    proxy = tunnel_proxy_url()
    direct = dns_leak_test(None)
    via_tunnel = dns_leak_test(proxy) if proxy else {"error": "no manual proxy configured"}
    return jsonify({"direct": direct, "tunnel": via_tunnel, "proxy_url": proxy})


@bp.get("/api/tunnel/proxy")
def get_proxy():
    return jsonify({"proxy_url": tunnel_proxy_url()})


@bp.put("/api/tunnel/proxy")
def put_proxy():
    body = request.get_json(silent=True) or {}
    proxy_url = (body.get("proxy_url") or "").strip() or None
    if proxy_url and not proxy_url.startswith(("http://", "https://", "socks4://", "socks5://", "socks5h://")):
        return jsonify({"error": "proxy_url must start with http(s):// or socks4/5://"}), 400
    set_proxy_url(proxy_url)
    return jsonify({"proxy_url": tunnel_proxy_url(), "mode": "manual"})


@bp.post("/api/firewall/lockdown")
def firewall_lockdown():
    body = request.get_json(silent=True) or {}
    port = int(body.get("port") or tunnel_port() or 0)
    if not port:
        return jsonify({"error": "tunnel port required"}), 400
    try:
        allow_loopback()
        block_egress_except_tunnel(port)
        return jsonify({"locked": True, "tunnel_port": port})
    except Exception as exc:
        return jsonify({"error": str(exc)}), 500


@bp.get("/api/files/actions")
def file_actions():
    task_id = (request.args.get("task_id") or "").strip()
    if not task_id:
        return jsonify({"error": "task_id required"}), 400
    with session() as db:
        job = db.get(Job, task_id)
        if not job:
            return jsonify({"error": "not found"}), 404
        dest = Path(job.dest_path) if job.dest_path else None
        if not dest or not dest.exists():
            candidates = sorted(downloads_dir().glob(f"{task_id}_download*"))
            if candidates:
                dest = candidates[-1]
            else:
                return jsonify({"error": "file not found"}), 404
        folder = str(dest.parent)
        filename = dest.name
        return jsonify({
            "task_id": task_id,
            "dest_path": str(dest),
            "folder": folder,
            "filename": filename,
            "exists": dest.exists(),
            "size": dest.stat().st_size if dest.exists() else None,
        })


@bp.post("/api/files/open-folder")
def open_folder():
    body = request.get_json(silent=True) or {}
    task_id = (body.get("task_id") or "").strip()
    if not task_id:
        return jsonify({"error": "task_id required"}), 400
    with session() as db:
        job = db.get(Job, task_id)
        if not job or not job.dest_path:
            return jsonify({"error": "not found"}), 404
        dest = Path(job.dest_path)
        if not dest.exists():
            candidates = sorted(downloads_dir().glob(f"{task_id}_download*"))
            if candidates:
                dest = candidates[-1]
            else:
                return jsonify({"error": "file not found"}), 404
        folder = dest.parent
        try:
            os.startfile(str(folder))
            return jsonify({"opened": str(folder)})
        except Exception as exc:
            return jsonify({"error": str(exc)}), 500


@bp.post("/api/files/reveal")
def reveal_file():
    body = request.get_json(silent=True) or {}
    task_id = (body.get("task_id") or "").strip()
    if not task_id:
        return jsonify({"error": "task_id required"}), 400
    with session() as db:
        job = db.get(Job, task_id)
        if not job or not job.dest_path:
            return jsonify({"error": "not found"}), 404
        dest = Path(job.dest_path)
        if not dest.exists():
            candidates = sorted(downloads_dir().glob(f"{task_id}_download*"))
            if candidates:
                dest = candidates[-1]
            else:
                return jsonify({"error": "file not found"}), 404
        try:
            import subprocess
            subprocess.run(["explorer.exe", "/select,", str(dest)], check=False)
            return jsonify({"revealed": str(dest)})
        except Exception as exc:
            return jsonify({"error": str(exc)}), 500


@bp.post("/api/validate/url")
def validate_url_route():
    body = request.get_json(silent=True) or {}
    url = (body.get("url") or "").strip()
    if not url:
        return jsonify({"error": "url is required"}), 400
    try:
        validate_url(url)
        ip = resolve_and_validate(url)
        return jsonify({"valid": True, "resolved_ip": ip})
    except Exception as exc:
        return jsonify({"valid": False, "error": str(exc)}), 400
