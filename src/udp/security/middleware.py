"""Universal Downloader Pro  -  security middleware."""

from __future__ import annotations

import os
import secrets
from functools import wraps
from typing import Callable

from flask import Flask, Response, jsonify, request
from udp.utils.network import is_private_ip, resolve_host

_VENV_PYTHON = os.path.expandvars(r"%USERPROFILE%\\Projects\\universal-downloader-pro\\.venv\\Scripts\\python.exe")


def _get_api_token() -> str:
    token = os.environ.get("UDP_API_TOKEN", "")
    if not token:
        token = secrets.token_urlsafe(32)
        os.environ["UDP_API_TOKEN"] = token
    return token.strip()


def _require_token() -> tuple[Response, int] | None:
    token = _get_api_token()
    supplied = request.headers.get("X-API-Token", "")
    if not supplied or not secrets.compare_digest(supplied, token):
        return jsonify({"error": "Unauthorized", "detail": "Invalid or missing API token"}), 401
    return None


def _check_host() -> tuple[Response, int] | None:
    host = request.host.split(":")[0] if ":" in request.host else request.host
    if host not in {"127.0.0.1", "localhost"}:
        return jsonify({"error": "Forbidden", "detail": "Invalid Host header"}), 403
    return None


def _check_origin() -> tuple[Response, int] | None:
    origin = request.headers.get("Origin", "")
    if not origin:
        return None
    from urllib.parse import urlparse
    parsed = urlparse(origin)
    origin_host = parsed.hostname or ""
    if origin_host not in {"127.0.0.1", "localhost"}:
        return jsonify({"error": "Forbidden", "detail": "Origin not allowed"}), 403
    return None


def _check_ssrf(url: str) -> tuple[Response, int] | None:
    try:
        ip = resolve_host(url)
    except Exception:
        return jsonify({"error": "Bad Request", "detail": "Unable to resolve URL"}), 400
    if is_private_ip(ip):
        return jsonify({"error": "Forbidden", "detail": "Private or link-local IPs are blocked"}), 403
    return None


def _wrap_ssrf(body: dict) -> dict:
    url = None
    if isinstance(body, dict):
        if "url" in body and isinstance(body["url"], str):
            url = body["url"]
        elif "urls" in body and isinstance(body["urls"], list) and body["urls"]:
            url = body["urls"][0]
    if url:
        bad = _check_ssrf(url)
        if bad:
            return bad[0].get_json()
    return None


def register_security(app: Flask) -> None:
    PUBLIC_GET_PATHS = {
        "/health",
        "/api/analyze",
        "/api/knowledge",
        "/api/history",
        "/api/playbook",
        "/api/training/export",
        "/api/token",
        "/api/firewall/commands",
        "/api/tunnel/status",
        "/api/tunnel/proxy",
        "/api/tunnel/egress",
        "/api/tunnel/dns-leak",
        "/favicon.ico",
    }
    PUBLIC_GET_PREFIXES = (
        "/api/jobs/",
        "/api/archives/",
        "/api/archives/<task_id>/assets/",
        "/api/stream/",
        "/api/files/",
        "/files/",
        "/frontend/",
    )

    @app.before_request
    def before():
        path = request.path
        if path == "/" or path.startswith("/frontend/"):
            return
        if request.method == "GET" and (path in PUBLIC_GET_PATHS or any(path.startswith(p) for p in PUBLIC_GET_PREFIXES)):
            return
        if path in ("/health", "/api/analyze"):
            return
        deny = _require_token()
        if deny:
            return deny
        deny = _check_host()
        if deny:
            return deny
        deny = _check_origin()
        if deny:
            return deny


def require_token(fn: Callable) -> Callable:
    @wraps(fn)
    def wrapper(*args, **kwargs):
        deny = _require_token()
        return deny if deny else fn(*args, **kwargs)
    return wrapper


def check_ssrf(fn: Callable) -> Callable:
    @wraps(fn)
    def wrapper(*args, **kwargs):
        response = fn(*args, **kwargs)
        if isinstance(response, tuple):
            payload, status = response
            if isinstance(payload, dict) and status == 200:
                blocked = _wrap_ssrf(payload)
                if blocked:
                    return jsonify(blocked), 403
        return response
    return wrapper
