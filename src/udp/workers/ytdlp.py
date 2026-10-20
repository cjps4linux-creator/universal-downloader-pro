"""Universal Downloader Pro — yt-dlp streaming with cookie/tier support."""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path
from typing import Optional

from udp.models.db import Session, Job
from udp.utils.paths import downloads_dir, ensure_dirs

ensure_dirs()


def _venv_yt_dlp() -> str:
    return str(Path(__file__).resolve().parent.parent.parent.parent / ".venv" / "Scripts" / "yt-dlp.exe")


def stream_with_ytdlp(url: str, dest: Path, job_id: str, *, cookies: Optional[str] = None, cookies_from_browser: Optional[str] = None, audio_only: bool = False, playlist: bool = False, audio_format: str = "mp3") -> tuple[Path, Optional[str]]:
    yt_dlp = shutil.which("yt-dlp") or _venv_yt_dlp()
    if not yt_dlp or not Path(yt_dlp).exists():
        return dest, f"yt-dlp not found: tried PATH={shutil.which('yt-dlp')}, venv={_venv_yt_dlp()}"

    # Validate audio format
    valid_formats = {"mp3", "flac", "wav", "m4a", "opus", "vorbis", "aac", "alac"}
    if audio_format.lower() not in valid_formats:
        audio_format = "mp3"

    dest.mkdir(parents=True, exist_ok=True)

    # Use video title as filename (sanitized by yt-dlp)
    out_template = str(dest / "%(title)s.%(ext)s")
    cmd = [
        yt_dlp,
        "-f", "bestaudio/best" if audio_only else "bestvideo+bestaudio/best",
        "-o", out_template,
        "--no-playlist",
        "--retries", "6",
        "--fragment-retries", "6",
        "--concurrent-fragments", "1",
        "--no-warnings",
        "--force-overwrites",
        "--print", "after_move:filepath",
        "--print", "after_move:filesize",
        "--print", "after_move:extractor",
    ]
    if audio_only:
        cmd.extend(["--extract-audio", "--audio-format", audio_format.lower(), "--audio-quality", "0"])
    if playlist:
        cmd.remove("--no-playlist")
        cmd.extend(["--yes-playlist", "--merge-output-format", "mp4"])
    cmd.append(url)
    if cookies:
        cmd.extend(["--cookies", cookies])
    if cookies_from_browser:
        cmd.extend(["--cookies-from-browser", cookies_from_browser])

    try:
        proc = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=600,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
    except subprocess.TimeoutExpired:
        _finalize(job_id, "failed", str(dest), error_message="timeout after 600s")
        return dest, "timeout after 600s"
    except Exception as exc:
        _finalize(job_id, "failed", str(dest), error_message=str(exc))
        return dest, str(exc)

    if proc.returncode != 0:
        stderr = proc.stderr.strip()[-4000:] if proc.stderr else ""
        bot_hint = _maybe_retry_with_browser_cookies(url, dest, job_id, cookies, cookies_from_browser, audio_only, playlist, stderr, audio_format)
        if bot_hint:
            return dest, bot_hint
        _finalize(job_id, "failed", str(dest), error_message=stderr or f"exit {proc.returncode}")
        return dest, stderr or f"yt-dlp exit {proc.returncode}"

    meta = {}
    try:
        info = extract_info(url, cookies=cookies)
        if isinstance(info, dict) and "error" not in info:
            meta = {
                "title": info.get("title"),
                "extractor": info.get("extractor"),
                "duration": info.get("duration"),
                "thumbnail": info.get("thumbnail"),
            }
    except Exception:
        pass

    stdout_lines = [line.strip() for line in (proc.stdout or "").splitlines() if line.strip()]
    filename = None
    filesize = None
    extractor = None
    if len(stdout_lines) >= 3:
        filename = stdout_lines[0]
        try:
            filesize = int(stdout_lines[1])
        except Exception:
            pass
        extractor = stdout_lines[2]
    elif len(stdout_lines) == 2:
        filename = stdout_lines[0]
        try:
            filesize = int(stdout_lines[1])
        except Exception:
            pass
    elif len(stdout_lines) == 1:
        filename = stdout_lines[0]

    if not filename:
        try:
            dest_stem = Path(dest).stem
            candidates = sorted(downloads_dir().glob(f"*{dest_stem}*"))
            if not candidates:
                candidates = sorted(downloads_dir().glob(f"*{job_id}*"))
            if candidates:
                filename = str(candidates[-1])
        except Exception:
            pass

    if extractor:
        meta.setdefault("extractor", extractor)

    try:
        # DEBUG: Write to file to see what's happening
        with open("C:/tmp/ytdlp_debug.log", "a") as df:
            df.write(f"JOB {job_id}: entering session block, filename={filename}\n")
        with Session() as session:
            job = session.get(Job, job_id)
            if job:
                with open("C:/tmp/ytdlp_debug.log", "a") as df:
                    df.write(f"JOB {job_id}: got job object, meta title={meta.get('title')}\n")
                if meta.get("title"):
                    job.stream_title = meta["title"][:1024]
                if filename:
                    job.stream_filename = Path(filename).name[:1024]
                    job.dest_path = str(Path(filename))
                    print(f"[DEBUG] Set stream_filename={Path(filename).name}, dest_path={str(Path(filename))}")
                if not filesize and filename and Path(filename).exists():
                    try:
                        job.stream_filesize = Path(filename).stat().st_size
                        print(f"[DEBUG] Set stream_filesize={job.stream_filesize}")
                    except Exception:
                        pass
                if meta.get("extractor"):
                    job.stream_extractor = meta["extractor"][:128]
                if meta.get("duration"):
                    try:
                        job.stream_duration = int(meta["duration"])
                    except Exception:
                        pass
                if meta.get("thumbnail"):
                    job.stream_thumbnail = meta["thumbnail"][:2048]
                session.commit()
                print(f"[DEBUG] Session committed successfully for job {job_id}")
    except Exception as exc:
        print(f"[DEBUG] Exception in session block: {exc}")
        import traceback; traceback.print_exc()

    _finalize(job_id, "succeeded", str(dest) if not filename else filename)
    return Path(filename) if filename else dest, None


def _update_stream_progress(job_id: str, percent: float) -> None:
    try:
        with Session() as session:
            job = session.get(Job, job_id)
            if job:
                job.progress = float(percent)
                job.updated_at = __import__("datetime").datetime.now(__import__("datetime").timezone.utc)
                session.commit()
    except Exception:
        pass


def _finalize(job_id: str, status: str, dest: str, error_message: Optional[str] = None) -> None:
    try:
        with Session() as session:
            job = session.get(Job, job_id)
            if job:
                job.status = status
                # Only update dest_path if it's a directory (not a file path already set)
                if job.dest_path and Path(job.dest_path).is_file():
                    # dest_path already set to actual file, don't overwrite
                    pass
                else:
                    job.dest_path = dest
                job.error_message = error_message
                job.finished_at = __import__("datetime").datetime.now(__import__("datetime").timezone.utc)
                session.commit()
    except Exception:
        pass


def _maybe_retry_with_browser_cookies(url: str, dest: Path, job_id: str, cookies: Optional[str], cookies_from_browser: Optional[str], audio_only: bool, playlist: bool, stderr: str, audio_format: str = "mp3") -> Optional[str]:
    lowered = (stderr or "").lower()
    if "sign in to confirm you" not in lowered or "bot" not in lowered:
        return None
    if cookies or not cookies_from_browser:
        return stderr or "youtube bot check failed"
    try:
        result = stream_with_ytdlp(url, dest, job_id, cookies=cookies, cookies_from_browser=cookies_from_browser, audio_only=audio_only, playlist=playlist, audio_format=audio_format)
        if isinstance(result, tuple) and len(result) == 2:
            path, err = result
            if not err and path and Path(path).exists():
                _finalize(job_id, "succeeded", str(path))
                return None
    except Exception:
        pass
    return stderr or "youtube bot check failed after cookie retry"


def extract_info(url: str, *, cookies: Optional[str] = None) -> dict:
    yt_dlp = shutil.which("yt-dlp") or _venv_yt_dlp()
    if not yt_dlp or not Path(yt_dlp).exists():
        return {"error": f"yt-dlp not found: tried PATH={shutil.which('yt-dlp')}, venv={_venv_yt_dlp()}"}
    cmd = [yt_dlp, "-j", "--no-playlist", "--no-warnings", url]
    if cookies:
        cmd.extend(["--cookies", cookies])
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        if proc.returncode == 0 and proc.stdout.strip():
            return json.loads(proc.stdout.splitlines()[0])
    except Exception as exc:
        return {"error": str(exc)}
    return {"error": proc.stderr.strip()[-1000:] or f"exit {proc.returncode}"}
