"""Universal Downloader Pro — API routes: downloads, media, and archives."""

from __future__ import annotations

import json
import uuid
import re
from pathlib import Path
from typing import Optional

from flask import Flask, Blueprint, jsonify, request, send_file, send_from_directory

from udp.core.downloader import download_file
from udp.core.archiver import archive_web_page
from udp.core.archiver_anti_block import archive_web_page_anti_block
from udp.core.anti_block import BlockClass, classify_response, fetch_with_anti_block
from udp.core.browser_cookies import load_browser_cookies_for_url
from udp.core.assets import part_path, resume_bytes, move_part_to_final, unique_dest_path
from udp.workers.scheduler import submit, run_stream_job, run_archive_job, run_archive_job_anti_block, run_stream_job_with_cookies, cancel_job, worker_count
from udp.workers.ytdlp import extract_info
from udp.models.db import Session, Job, KnowledgeDomain
from udp.utils.paths import downloads_dir, task_dir, ensure_dirs

bp = Blueprint("downloads", __name__)


@bp.post("/api/analyze")
def analyze():
    body = request.get_json(silent=True) or {}
    url = (body.get("url") or "").strip()
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
    # Fallback: treat extensionless page paths as web when auto mode needs a safe default.
    from urllib.parse import urlparse
    parsed = urlparse(url)
    path = parsed.path or ""
    if path and not path.endswith("/") and "." not in Path(path).name:
        return "web"
    return "unknown"


def _guess_filename(url: str, category: str) -> Optional[str]:
    from urllib.parse import urlparse
    parsed = urlparse(url)
    name = Path(parsed.path).name
    if name and "." in name:
        return name
    return None


@bp.post("/api/download")
def download():
    body = request.get_json(silent=True) or {}
    url = (body.get("url") or "").strip()
    mode = (body.get("mode") or "direct").strip().lower()
    print(f"[DEBUG] download() called: mode={repr(mode)}, url={url[:60]}...")
    if not url:
        return jsonify({"error": "url is required"}), 400

    ensure_dirs()
    task_id = uuid.uuid4().hex[:12]
    dest_dir = downloads_dir()

    with Session() as session:
        job = Job(
            id=task_id,
            url=url,
            mode=mode,
            status="queued",
            dest_path="",
        )
        session.add(job)
        session.commit()

    if mode == "archive" or mode == "web":
        tier = int((body.get("tier") or 0))
        proxy = (body.get("proxy") or "").strip() or None
        cookies = body.get("cookies")
        if not cookies:
            browser = (body.get("cookies_from_browser") or "").strip() or None
            if browser:
                cookies = load_browser_cookies_for_url(url, browser)
        submit(run_archive_job_anti_block, url, task_id, proxy=proxy, cookies=cookies)

    elif mode == "stream":
        cookies = body.get("cookies")
        browser = (body.get("cookies_from_browser") or "").strip() or None
        audio_only = bool(body.get("audio_only"))
        dual_mode = bool(body.get("dual"))
        audio_format = (body.get("audio_format") or "mp3").strip().lower()
        playlist = bool(body.get("playlist"))

        print(f"[DEBUG] Stream mode: dual_mode={dual_mode}, dual_raw={body.get('dual')}, body_keys={list(body.keys())}")

        # If dual mode requested, create two jobs: video + audio
        if dual_mode:
            print(f"[DEBUG] Stream dual mode requested")
            # Job 1: Video (best quality)
            video_task_id = uuid.uuid4().hex[:12]
            with Session() as session:
                job = Job(
                    id=video_task_id,
                    url=url,
                    mode="stream",
                    status="queued",
                    dest_path="",
                )
                session.add(job)
                session.commit()
            submit(run_stream_job_with_cookies, url, dest_dir, video_task_id, cookies=cookies, browser=browser, audio_only=False, playlist=False)
            with Session() as session:
                job = session.get(Job, video_task_id)
                if job:
                    job.status = "running"
                    session.commit()

            # Job 2: Audio (FLAC or selected format)
            audio_task_id = uuid.uuid4().hex[:12]
            with Session() as session:
                job = Job(
                    id=audio_task_id,
                    url=url,
                    mode="stream",
                    status="queued",
                    dest_path="",
                )
                session.add(job)
                session.commit()
            submit(run_stream_job_with_cookies, url, dest_dir, audio_task_id, cookies=cookies, browser=browser, audio_only=True, playlist=False, audio_format=audio_format)
            with Session() as session:
                job = session.get(Job, audio_task_id)
                if job:
                    job.status = "running"
                    session.commit()

            # Return both task IDs
            return jsonify({
                "task_id": task_id,
                "status": "queued",
                "mode": mode,
                "url": url,
                "dest": str(dest_dir),
                "dual_tasks": {
                    "video": video_task_id,
                    "audio": audio_task_id
                }
            }), 202

        # Regular single stream job
        submit(run_stream_job_with_cookies, url, dest_dir, task_id, cookies=cookies, browser=browser, audio_only=audio_only, playlist=playlist, audio_format=audio_format)
        with Session() as session:
            job = session.get(Job, task_id)
            if job:
                job.status = "running"
                session.commit()

    elif mode == "dual":
            print(f"[DEBUG] Entered dual mode branch")
            # Download both video and audio (FLAC)
            cookies = body.get("cookies")
            browser = (body.get("cookies_from_browser") or "").strip() or None
            audio_format = (body.get("audio_format") or "flac").strip().lower()

            # Job 1: Video (best quality)
            video_task_id = uuid.uuid4().hex[:12]
            with Session() as session:
                job = Job(
                    id=video_task_id,
                    url=url,
                    mode="stream",
                    status="queued",
                    dest_path="",
                )
                session.add(job)
                session.commit()
            submit(run_stream_job_with_cookies, url, dest_dir, video_task_id, cookies=cookies, browser=browser, audio_only=False, playlist=False)
            with Session() as session:
                job = session.get(Job, video_task_id)
                if job:
                    job.status = "running"
                    session.commit()

            # Job 2: Audio (FLAC)
            audio_task_id = uuid.uuid4().hex[:12]
            with Session() as session:
                job = Job(
                    id=audio_task_id,
                    url=url,
                    mode="stream",
                    status="queued",
                    dest_path="",
                )
                session.add(job)
                session.commit()
            submit(run_stream_job_with_cookies, url, dest_dir, audio_task_id, cookies=cookies, browser=browser, audio_only=True, playlist=False, audio_format=audio_format)
            with Session() as session:
                job = session.get(Job, audio_task_id)
                if job:
                    job.status = "running"
                    session.commit()

            # Return both task IDs
            return jsonify({
                "task_id": task_id,
                "status": "queued",
                "mode": mode,
                "url": url,
                "dest": str(dest_dir),
                "dual_tasks": {
                    "video": video_task_id,
                    "audio": audio_task_id
                }
            }), 202

    else:
        dest = unique_dest_path(dest_dir / f"{task_id}_download")
        dest.parent.mkdir(parents=True, exist_ok=True)
        try:
            _, err = download_file(url, dest, task_id)
            status = "failed" if err else "succeeded"
            with Session() as session:
                job = session.get(Job, task_id)
                if job:
                    job.status = status
                    job.error_message = err
                    job.finished_at = __import__("datetime").datetime.now(__import__("datetime").timezone.utc)
                    session.commit()
        except Exception as exc:
            with Session() as session:
                job = session.get(Job, task_id)
                if job:
                    job.status = "failed"
                    job.error_message = str(exc)
                    job.finished_at = __import__("datetime").datetime.now(__import__("datetime").timezone.utc)
                    session.commit()

    return jsonify({
        "task_id": task_id,
        "status": "queued",
        "mode": mode,
        "url": url,
        "dest": str(dest_dir),
    }), 202


@bp.get("/api/jobs/<task_id>/detail")
def job_detail(task_id: str):
    with Session() as session:
        job = session.get(Job, task_id)
        if not job:
            return jsonify({"error": "not found"}), 404
        progress = None
        try:
            progress = __import__("json").loads(job.error_message or "{}").get("percent") if job.error_message else None
        except Exception:
            pass
        payload = {
            "job": {
                "task_id": job.id,
                "status": job.status,
                "url": job.url,
                "mode": job.mode,
                "bytes_done": job.bytes_done,
                "bytes_total": job.bytes_total,
                "progress": progress,
                "dest_path": job.dest_path,
                "error_code": job.error_code,
                "error_message": job.error_message,
                "attempts": job.attempts,
                "created_at": job.created_at.isoformat() if job.created_at else None,
                "updated_at": job.updated_at.isoformat() if job.updated_at else None,
                "finished_at": job.finished_at.isoformat() if job.finished_at else None,
                "artifact_path": job.artifact_path,
                "report_path": job.report_path,
                "stream": {
                    "title": job.stream_title,
                    "filename": job.stream_filename,
                    "filesize": job.stream_filesize,
                    "extractor": job.stream_extractor,
                    "duration": job.stream_duration,
                    "thumbnail": job.stream_thumbnail,
                } if job.mode == "stream" else None,
                "file": {
                    "path": job.dest_path,
                    "exists": Path(job.dest_path).exists() if job.dest_path else False,
                    "size": Path(job.dest_path).stat().st_size if job.dest_path and Path(job.dest_path).exists() else None,
                } if job.dest_path else None,
            },
            "assets": [],
            "report": "",
            "failed_assets": [],
        }
        root = task_dir(task_id)
        html_path = root / "index.html"
        report_path = root / "report.txt"
        assets_root = root / "assets"
        failed_path = root / "failed_assets.json"
        has_archive_contents = html_path.exists() or assets_root.exists() or report_path.exists()
        if job.mode == "archive" or has_archive_contents:
            assets = []
            if assets_root.exists():
                for p in sorted(assets_root.iterdir()):
                    if p.is_file() and not p.name.endswith('.part'):
                        meta = {
                            "name": p.name,
                            "size": p.stat().st_size,
                            "url": f"/api/archives/{task_id}/assets/{p.name}",
                            "kind": _guess_asset_kind(p.name),
                        }
                        if p.suffix.lower() == '.css':
                            meta['css'] = _analyze_css(p)
                        assets.append(meta)
            report_text = ""
            if report_path.exists():
                report_text = report_path.read_text(encoding="utf-8", errors="ignore")[:8000]
            failed_assets = []
            if failed_path.exists():
                try:
                    failed_assets = json.loads(failed_path.read_text(encoding="utf-8"))
                    if isinstance(failed_assets, dict):
                        failed_assets = failed_assets.get("failed") or []
                except Exception:
                    failed_assets = []
            payload["assets"] = assets[:100]
            payload["report"] = report_text
            payload["failed_assets"] = failed_assets[:100]
            if html_path.exists():
                payload["archive_url"] = f"/api/archives/{task_id}"
        return jsonify(payload)


def _analyze_css(path: Path):
    try:
        text = path.read_text(encoding="utf-8", errors="ignore")
    except Exception:
        return None
    lower = text.lower()
    framework = None
    if 'bootstrap' in lower or 'grid(' in lower or 'container-fluid' in lower:
        framework = 'Bootstrap'
    elif 'tailwind' in lower or '@tailwind' in lower:
        framework = 'Tailwind'
    elif 'foundation' in lower:
        framework = 'Foundation'
    elif 'bulma' in lower:
        framework = 'Bulma'
    elif 'materialize' in lower or 'material ' in lower:
        framework = 'Materialize'
    elif 'wordpress' in lower or 'wp-' in lower or 'admin-bar' in lower:
        framework = 'WordPress'
    colors = sorted(set(re.findall(r'#(?:[0-9a-f]{3}){1,2}\b', lower)))[:8]
    fonts = sorted(set(re.findall(r'font-family:\s*([^;}\n]+)', lower)))[:5]
    media_queries = re.findall(r'@media\s+([^{]+)\{', text, re.IGNORECASE)
    media_queries = [m.strip() for m in media_queries][:5]
    return {
        'framework': framework,
        'colors': colors,
        'fonts': fonts,
        'media_queries': media_queries,
        'charset': 'utf-8' if '@charset' in lower else None,
        'size_bytes': path.stat().st_size if path.exists() else None,
    }

def _guess_asset_kind(name: str) -> str:
    lowered = name.lower()
    if lowered.endswith((".png", ".jpg", ".jpeg", ".webp", ".avif", ".svg", ".gif", ".ico")):
        return "image"
    if lowered.endswith((".mp4", ".webm", ".mov", ".avi", ".mkv")):
        return "video"
    if lowered.endswith((".mp3", ".wav", ".flac", ".aac", ".m4a")):
        return "audio"
    if lowered.endswith((".html", ".htm")):
        return "html"
    if lowered.endswith((".css", ".js", ".json", ".xml", ".txt")):
        return "code"
    return "file"


@bp.get("/api/jobs/<task_id>")
def job_status(task_id: str):
    with Session() as session:
        job = session.get(Job, task_id)
        if not job:
            return jsonify({"error": "not found"}), 404
        progress = None
        try:
            progress = __import__("json").loads(job.error_message or "{}").get("percent") if job.error_message else None
        except Exception:
            pass
        return jsonify({
            "task_id": job.id,
            "status": job.status,
            "url": job.url,
            "mode": job.mode,
            "bytes_done": job.bytes_done,
            "bytes_total": job.bytes_total,
            "progress": progress,
            "dest_path": job.dest_path,
            "error_code": job.error_code,
            "error_message": job.error_message,
            "attempts": job.attempts,
            "created_at": job.created_at.isoformat() if job.created_at else None,
            "updated_at": job.updated_at.isoformat() if job.updated_at else None,
            "finished_at": job.finished_at.isoformat() if job.finished_at else None,
            "stream": {
                "title": job.stream_title,
                "filename": job.stream_filename,
                "filesize": job.stream_filesize,
                "extractor": job.stream_extractor,
                "duration": job.stream_duration,
                "thumbnail": job.stream_thumbnail,
            } if job.mode == "stream" else None,
        })


@bp.get("/api/jobs/<task_id>/stream")
def stream_job(task_id: str):
    def generate():
        last_payload = None
        while True:
            with Session() as session:
                job = session.get(Job, task_id)
                if not job:
                    yield "event: error\ndata: not found\n\n"
                    break
                payload = {
                    "task_id": job.id,
                    "status": job.status,
                    "progress": job.progress,
                    "bytes_done": job.bytes_done,
                    "bytes_total": job.bytes_total,
                    "error_message": job.error_message,
                    "artifact_url": job.artifact_path and f"/files/{Path(job.artifact_path).relative_to(downloads_dir())}" or None,
                    "report_url": job.report_path and f"/files/{Path(job.report_path).relative_to(downloads_dir())}" or None,
                }
                progress_payload = dict(payload)
                try:
                    progress_payload["progress"] = __import__("json").loads(job.error_message or "{}").get("percent") if job.error_message else None
                except Exception:
                    pass
            status = payload["status"]
            # Emit update if status changed OR if this is a stream/archive job with progress
            if last_payload is None or status != last_payload:
                yield f"event: status\ndata: {__import__('json').dumps(payload)}\n\n"
                last_payload = status
            elif job.mode in {"stream", "archive"} and (payload.get("progress") is not None or progress_payload.get("progress") is not None):
                yield f"event: progress\ndata: {__import__('json').dumps(progress_payload)}\n\n"
            if status in ("succeeded", "failed", "blocked", "cancelled", "partial"):
                yield "event: done\ndata: done\n\n"
                break
            import time
            time.sleep(1)
    from flask import Response
    return Response(generate(), mimetype="text/event-stream")


@bp.post("/api/jobs/<task_id>/cancel")
def cancel(task_id: str):
    if cancel_job(task_id):
        return jsonify({"cancelled": True})
    return jsonify({"cancelled": False, "reason": "not running or unknown"}), 404


@bp.get("/api/queue")
def queue_status():
    return jsonify({"workers": worker_count()})


@bp.post("/api/batch")
def batch_download():
    body = request.get_json(silent=True) or {}
    urls = [u.strip() for u in (body.get("urls") or []) if u and u.strip()]
    mode = (body.get("mode") or "auto").strip().lower()
    if not urls:
        return jsonify({"error": "urls is required"}), 400
    urls = urls[:20]
    results = []
    for url in urls:
        category = _guess_category(url)
        resolved_mode = mode if mode != "auto" else category
        if resolved_mode not in {"direct", "archive", "stream"}:
            resolved_mode = "direct"
        ensure_dirs()
        task_id = uuid.uuid4().hex[:12]
        dest = unique_dest_path(downloads_dir() / f"{task_id}_download")
        with Session() as session:
            job = Job(id=task_id, url=url, mode=resolved_mode, status="queued", dest_path=str(dest))
            session.add(job)
            session.commit()
        try:
            if resolved_mode in {"archive", "web"}:
                tier = int((body.get("tier") or 0))
                proxy = (body.get("proxy") or "").strip() or None
                cookies = body.get("cookies")
                submit(run_archive_job_anti_block, url, task_id, proxy=proxy, cookies=cookies)
            elif resolved_mode == "stream":
                            cookies = body.get("cookies")
                            browser = (body.get("cookies_from_browser") or "").strip() or None
                            audio_only = bool(body.get("audio_only"))
                            audio_format = (body.get("audio_format") or "mp3").strip().lower()
                            playlist = bool(body.get("playlist"))
                            submit(run_stream_job_with_cookies, url, dest, task_id, cookies=cookies, browser=browser, audio_only=audio_only, playlist=playlist, audio_format=audio_format)
                            with Session() as session:
                                job = session.get(Job, task_id)
                                if job:
                                    job.status = "running"
                                    session.commit()
            else:
                dest.parent.mkdir(parents=True, exist_ok=True)
                _, err = download_file(url, dest, task_id)
                status = "failed" if err else "succeeded"
                with Session() as session:
                    job = session.get(Job, task_id)
                    if job:
                        job.status = status
                        job.error_message = err
                        job.finished_at = __import__("datetime").datetime.now(__import__("datetime").timezone.utc)
                        session.commit()
                results.append({"url": url, "task_id": task_id, "status": status, "dest": str(dest), "error": err})
                continue
        except Exception as exc:
            with Session() as session:
                job = session.get(Job, task_id)
                if job:
                    job.status = "failed"
                    job.error_message = str(exc)
                    job.finished_at = __import__("datetime").datetime.now(__import__("datetime").timezone.utc)
                    session.commit()
            results.append({"url": url, "task_id": task_id, "status": "failed", "dest": str(dest), "error": str(exc)})
            continue
        results.append({"url": url, "task_id": task_id, "status": "queued", "mode": resolved_mode, "dest": str(dest)})
    return jsonify({"results": results}), 202


@bp.get("/files/<path:filename>")
def serve_file(filename: str):
    ensure_dirs()
    target = (downloads_dir() / filename).resolve()
    base = downloads_dir().resolve()
    if not str(target).startswith(str(base)):
        return jsonify({"error": "invalid path"}), 403
    if not target.exists():
        return jsonify({"error": "not found"}), 404
    ext = target.suffix.lower()
    mimetype = mime_map.get(ext, "application/octet-stream")
    return send_file(str(target), mimetype=mimetype, as_attachment=False, download_name=target.name)


mime_map = {
    ".mp4": "video/mp4",
    ".webm": "video/webm",
    ".mkv": "video/x-matroska",
    ".mp3": "audio/mpeg",
    ".wav": "audio/wav",
    ".flac": "audio/flac",
    ".m4a": "audio/mp4",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".png": "image/png",
    ".gif": "image/gif",
    ".webp": "image/webp",
    ".svg": "image/svg+xml",
    ".pdf": "application/pdf",
    ".html": "text/html",
    ".htm": "text/html",
    ".txt": "text/plain",
    ".css": "text/css",
    ".js": "application/javascript",
    ".json": "application/json",
}


@bp.get("/api/stream/<task_id>/play")
def play_stream(task_id: str):
    with Session() as session:
        job = session.get(Job, task_id)
        if not job:
            return jsonify({"error": "not found"}), 404
        if job.mode != "stream":
            return jsonify({"error": "not a stream job"}), 400
        dest = Path(job.dest_path) if job.dest_path else None
        if not dest or not dest.exists():
            # fallback to expected pattern
            candidates = sorted(downloads_dir().glob(f"{task_id}_download*"))
            if not candidates:
                return jsonify({"error": "file not found"}), 404
            dest = candidates[-1]
        ext = dest.suffix.lower()
        mimetype = mime_map.get(ext, "application/octet-stream")
        return send_file(str(dest), mimetype=mimetype, as_attachment=False, download_name=dest.name)


@bp.get("/api/stream/<task_id>/download")
def download_stream(task_id: str):
    with Session() as session:
        job = session.get(Job, task_id)
        if not job:
            return jsonify({"error": "not found"}), 404
        if job.mode != "stream":
            return jsonify({"error": "not a stream job"}), 400
        dest = Path(job.dest_path) if job.dest_path else None
        if not dest or not dest.exists():
            candidates = sorted(downloads_dir().glob(f"{task_id}_download*"))
            if not candidates:
                return jsonify({"error": "file not found"}), 404
            dest = candidates[-1]
        return send_file(str(dest), as_attachment=True, download_name=dest.name)


@bp.get("/api/jobs/<task_id>/resume")
def resume_status(task_id: str):
    with Session() as session:
        job = session.get(Job, task_id)
        if not job:
            return jsonify({"error": "not found"}), 404
        dest = Path(job.dest_path) if job.dest_path else None
        part = part_path(dest) if dest else None
        resume = resume_bytes(part) if part else 0
        return jsonify({
            "task_id": job.id,
            "status": job.status,
            "dest_path": job.dest_path,
            "resume_bytes": resume,
            "can_resume": bool(dest and part and resume > 0),
        })


@bp.post("/api/jobs/<task_id>/retry")
def retry_job(task_id: str):
    with Session() as session:
        job = session.get(Job, task_id)
        if not job:
            return jsonify({"error": "not found"}), 404
        dest = Path(job.dest_path) if job.dest_path else downloads_dir() / f"{task_id}_download"
        job.status = "queued"
        job.error_message = None
        job.error_code = None
        job.bytes_done = resume_bytes(part_path(dest))
        job.finished_at = None
        session.commit()
        if job.mode == "archive":
            submit(run_archive_job, job.url, task_id)
        elif job.mode == "stream":
            submit(run_stream_job, job.url, dest)
        else:
            dest.parent.mkdir(parents=True, exist_ok=True)
            submit(_retry_direct, job.url, dest, task_id)
        return jsonify({"task_id": task_id, "status": "queued", "resume_bytes": job.bytes_done})


def _retry_direct(url: str, dest: Path, job_id: str) -> None:
    try:
        _, err = download_file(url, dest, job_id)
        status = "failed" if err else "succeeded"
        with Session() as session:
            job = session.get(Job, job_id)
            if job:
                job.status = status
                job.error_message = err
                job.finished_at = __import__("datetime").datetime.now(__import__("datetime").timezone.utc)
                session.commit()
    except Exception as exc:
        with Session() as session:
            job = session.get(Job, job_id)
            if job:
                job.status = "failed"
                job.error_message = str(exc)
                job.finished_at = __import__("datetime").datetime.now(__import__("datetime").timezone.utc)
                session.commit()
