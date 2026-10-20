"""Universal Downloader Pro — application factory and core app module."""

from __future__ import annotations

import os
from urllib.parse import urlparse
from flask import Flask, jsonify, request, send_from_directory
from werkzeug.exceptions import HTTPException

from udp.api.routes.downloads import bp as downloads_bp
from udp.api.routes.knowledge import bp as knowledge_bp
from udp.api.routes.system import bp as system_bp
from udp.api.routes.archive import bp as archive_bp
from udp.security.middleware import register_security
from udp.models.db import init_db, session
from pathlib import Path


def create_app() -> Flask:
    app = Flask(
        __name__,
        static_folder=None,
    )
    app.config["SECRET_KEY"] = os.environ.get("UDP_SECRET_KEY", "change-me-in-production")
    app.config["MAX_CONTENT_LENGTH"] = 256 * 1024 * 1024
    app.config["JSON_SORT_KEYS"] = False

    register_security(app)

    app.register_blueprint(downloads_bp)
    app.register_blueprint(knowledge_bp)
    app.register_blueprint(system_bp)
    app.register_blueprint(archive_bp)

    frontend_dir = Path(__file__).resolve().parent.parent.parent / "frontend"
    app.add_url_rule("/frontend/<path:filename>", endpoint="frontend", view_func=lambda filename: send_from_directory(frontend_dir, filename))
    app.add_url_rule("/", endpoint="index", view_func=lambda: send_from_directory(frontend_dir, "index.html"))

    @app.get("/api/analyze")
    def analyze_get():
        url = request.args.get("url", "").strip()
        if not url:
            return jsonify({"error": "url is required"}), 400
        mode = _guess_category(url)
        filename = _guess_filename(url, mode)
        return jsonify({"url": url, "mode": mode, "filename": filename})

    def _guess_category(url: str) -> str:
        lowered = url.lower()
        streaming_hosts = ["youtube.com", "youtu.be", "vimeo.com", "dailymotion.com", "twitch.tv", "twitter.com", "x.com", "facebook.com", "instagram.com", "tiktok.com", "soundcloud.com", "bandcamp.com"]
        if any(host in lowered for host in streaming_hosts):
            return "stream"
        if lowered.endswith((".pdf", ".doc", ".docx", ".xls", ".xlsx", ".ppt", ".pptx")):
            return "doc"
        if lowered.endswith((".jpg", ".jpeg", ".png", ".gif", ".webp", ".svg", ".bmp", ".ico", ".mp4", ".webm", ".mkv", ".avi", ".mov", ".mp3", ".wav", ".flac", ".aac")):
            return "media"
        if lowered.endswith((".zip", ".rar", ".7z", ".tar", ".gz", ".bz2")):
            return "archive"
        if lowered.endswith((".html", ".htm")):
            return "web"
        from urllib.parse import urlparse
        parsed = urlparse(url)
        path = parsed.path or ""
        if path and not path.endswith("/") and "." not in Path(path).name:
            return "web"
        return "web"


    def _guess_filename(url: str, category: str):
        parsed = urlparse(url)
        name = Path(parsed.path).name
        if name and "." in name:
            return name
        return None

    init_db()

    @app.get("/health")
    def health():
        return jsonify({"status": "ok", "service": "universal-downloader-pro", "version": "1.0.0"})

    @app.get("/api/token")
    def token_info():
        return jsonify({"token": (os.environ.get("UDP_API_TOKEN", "") or "").strip()})

    @app.errorhandler(HTTPException)
    def on_http_error(exc: HTTPException):
        return jsonify({"error": exc.name, "detail": exc.description}), exc.code

    @app.errorhandler(Exception)
    def on_unhandled(exc: Exception):
        return jsonify({"error": "Internal Server Error", "detail": str(exc)}), 500

    return app


app = create_app()

if __name__ == "__main__":
    port = int(os.environ.get("UDP_PORT", "8765"))
    app.run(host="127.0.0.1", port=port, debug=False)
