from pathlib import Path
p = Path('src/udp/api/routes/archive.py')
text = p.read_text(encoding='utf-8')

old = '''from udp.utils.paths import downloads_dir, task_dir, ensure_dirs
from udp.core.assets import unique_dest_path
from udp.workers.scheduler import submit, _finalize'''

new = '''from udp.utils.paths import downloads_dir, task_dir, ensure_dirs
from udp.core.assets import unique_dest_path
from udp.core.downloader import circuit
from udp.workers.scheduler import submit, _finalize'''

if old not in text:
    raise SystemExit('import block not found')
text = text.replace(old, new)

old2 = '''def _salvage_worker(task_id: str) -> None:
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
    _finalize(task_id, status, "", error_message=error_payload)'''

new2 = '''def _salvage_worker(task_id: str) -> None:
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
    _finalize(task_id, status, "", error_message=error_payload)'''

if old2 not in text:
    raise SystemExit('salvage worker block not found')
text = text.replace(old2, new2)
p.write_text(text, encoding='utf-8')
print('patched')
