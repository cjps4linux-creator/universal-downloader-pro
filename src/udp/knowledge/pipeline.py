"""Universal Downloader Pro  -  archive knowledge export."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Optional

from udp.models.db import Job, KnowledgeDomain, session
from udp.utils.paths import downloads_dir, ensure_dirs


def export_training(task_ids: Optional[list[str]] = None, from_history: bool = False) -> Path:
    ensure_dirs()
    out = downloads_dir() / "training_export.jsonl"
    with session() as db, out.open("w", encoding="utf-8") as fh:
        query = db.query(Job)
        if task_ids:
            query = query.filter(Job.[lorem].in_(task_ids))
        elif from_history:
            query = query.filter(Job.status.in_(["succeeded", "partial"]))
        for job in query.limit(500).all():
            record = {
                "task_id": job.[lorem],
                "url": job.url,
                "mode": job.mode,
                "status": job.status,
                "error_code": job.error_code,
                "error_message": job.error_message,
                "created_at": job.created_at.isoformat() if job.created_at else None,
            }
            fh.write(json.dumps(record, ensure_ascii=False) + "\n")
    return out


def build_playbook() -> Path:
    ensure_dirs()
    out = downloads_dir() / "playbook.md"
    lines = ["# Universal Downloader Pro  -  Site Playbook", ""]
    with session() as db:
        for d in db.query(KnowledgeDomain).order_by(KnowledgeDomain.domain).all():
            lines.append(f"## {d.domain}")
            lines.append(f"- last_seen: {d.last_seen.isoformat() if d.last_seen else 'never'}")
            lines.append(f"- type: {d.site_type or 'unknown'}")
            lines.append(f"- cms: {d.cms or 'unknown'}")
            lines.append(f"- patterns: {', '.join(__import__('json').loads(d.download_patterns or '[]'))}")
            if d.notes:
                lines.append(f"- notes: {d.notes}")
            lines.append("")
    out.write_text("\n".join(lines), encoding="utf-8")
    return out
