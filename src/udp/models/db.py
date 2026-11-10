"""Universal Downloader Pro  -  SQLAlchemy models and database initialization."""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from sqlalchemy import (
    DateTime,
    Float,
    Integer,
    String,
    Text,
    create_engine,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, sessionmaker

from udp.utils.paths import data_dir

# The database location is overridable so that tests (and any future
# multi-tenant or containerised deployment) can point at a throwaway file
# instead of the user's live database. Everything that needs a session must
# resolve it through session() below rather than importing Session directly,
# otherwise the override is bypassed.
DB_PATH = Path(os.environ.get("UDP_DB_PATH") or (data_dir() / "udp.db"))
ENGINE = create_engine(f"sqlite:///{DB_PATH}", echo=False, future=True)
Session = sessionmaker(ENGINE, future=True)


def session():
    """Return a new session bound to the *current* ENGINE.

    Modules must call this rather than importing Session, so that
    reconfiguring ENGINE (as the test-suite does) is always honoured.
    """
    return Session()


class Base(DeclarativeBase):
    pass


class Job(Base):
    __tablename__ = "jobs"

    [lorem]: Mapped[str] = mapped_column(String(36), primary_key=True)
    url: Mapped[str] = mapped_column(String(2048), nullable=False)
    mode: Mapped[str] = mapped_column(String(32), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="queued")
    bytes_done: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    bytes_total: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    dest_path: Mapped[Optional[str]] = mapped_column(String(4096), nullable=True)
    error_code: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))
    finished_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    progress: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    artifact_path: Mapped[Optional[str]] = mapped_column(String(4096), nullable=True)
    report_path: Mapped[Optional[str]] = mapped_column(String(4096), nullable=True)
    stream_title: Mapped[Optional[str]] = mapped_column(String(1024), nullable=True)
    stream_filename: Mapped[Optional[str]] = mapped_column(String(1024), nullable=True)
    stream_filesize: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    stream_extractor: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    stream_duration: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    stream_thumbnail: Mapped[Optional[str]] = mapped_column(String(2048), nullable=True)


class KnowledgeDomain(Base):
    __tablename__ = "knowledge_domains"

    domain: Mapped[str] = mapped_column(String(255), primary_key=True)
    last_seen: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    archives: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    category: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    cms: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    frameworks: Mapped[str] = mapped_column(Text, nullable=False, default="[]")
    cdn_providers: Mapped[str] = mapped_column(Text, nullable=False, default="[]")
    trackers: Mapped[str] = mapped_column(Text, nullable=False, default="[]")
    fonts: Mapped[str] = mapped_column(Text, nullable=False, default="[]")
    colors: Mapped[str] = mapped_column(Text, nullable=False, default="[]")
    security_issues: Mapped[str] = mapped_column(Text, nullable=False, default="[]")
    accessibility_issues: Mapped[str] = mapped_column(Text, nullable=False, default="[]")
    link_internal: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    link_external: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    link_nofollow: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    link_sponsored: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    media_counts: Mapped[str] = mapped_column(Text, nullable=False, default="{}")
    site_type: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    download_patterns: Mapped[str] = mapped_column(Text, nullable=False, default="[]")
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    asset_counts: Mapped[str] = mapped_column(Text, nullable=False, default="{}")
    schema_version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)


def update_knowledge_from_archive(url: str, results: list[dict], failed: list[dict]) -> None:
    from urllib.parse import urlparse
    parsed = urlparse(url)
    domain = parsed.hostname or "unknown"
    if not domain:
        domain = "unknown"
    media_counts: dict[str, int] = {}
    cdn_providers: list[str] = []
    trackers: list[str] = []
    for item in results + failed:
        asset_url = item.get("url", "")
        try:
            a_parsed = urlparse(asset_url)
            host = (a_parsed.hostname or "").lower()
        except Exception:
            host = ""
        kind = item.get("kind") or ""
        media_counts[kind] = media_counts.get(kind, 0) + 1
        if host and host != domain:
            cdn_providers.append(host)
        if any(t in host for t in ["google-analytics", "googletagmanager", "facebook.net", "twitter.com", "double-click"]):
            trackers.append(host)
    with Session() as session:
        row = session.get(KnowledgeDomain, domain)
        if not row:
            row = KnowledgeDomain(domain=domain)
            session.add(row)
        row.archives = (row.archives or 0) + 1
        row.last_seen = __import__("datetime").datetime.now(__import__("datetime").timezone.utc)
        row.asset_counts = json.dumps(media_counts, ensure_ascii=False)
        row.cdn_providers = json.dumps(list(dict.fromkeys(cdn_providers)), ensure_ascii=False)
        row.trackers = json.dumps(list(dict.fromkeys(trackers)), ensure_ascii=False)
        row.frameworks = row.frameworks or "[]"
        row.notes = row.notes or ""
        session.commit()


class Setting(Base):
    __tablename__ = "settings"

    key: Mapped[str] = mapped_column(String(128), primary_key=True)
    value: Mapped[str] = mapped_column(Text, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))


def init_db() -> None:
    data_dir().mkdir(parents=True, exist_ok=True)
    Base.metadata.create_all(ENGINE)
    with ENGINE.begin() as conn:
        for stmt in [
            "ALTER TABLE jobs ADD COLUMN progress FLOAT",
            "ALTER TABLE jobs ADD COLUMN artifact_path VARCHAR(4096)",
            "ALTER TABLE jobs ADD COLUMN report_path VARCHAR(4096)",
            "ALTER TABLE jobs ADD COLUMN stream_title VARCHAR(1024)",
            "ALTER TABLE jobs ADD COLUMN stream_filename VARCHAR(1024)",
            "ALTER TABLE jobs ADD COLUMN stream_filesize INTEGER",
            "ALTER TABLE jobs ADD COLUMN stream_extractor VARCHAR(128)",
            "ALTER TABLE jobs ADD COLUMN stream_duration INTEGER",
            "ALTER TABLE jobs ADD COLUMN stream_thumbnail VARCHAR(2048)",
        ]:
            try:
                conn.exec_driver_sql(stmt)
            except Exception:
                pass
    # Recover orphaned jobs from previous sessions
    # Only mark truly stale jobs as interrupted so users can retry them
    try:
        from datetime import datetime, timezone, timedelta
        cutoff = datetime.now(timezone.utc) - timedelta(hours=24)
        with Session() as session:
            orphaned = session.query(Job).filter(Job.status.in_(["queued", "running"]), Job.created_at < cutoff).all()
            if orphaned:
                now = datetime.now(timezone.utc)
                for job in orphaned:
                    job.status = "interrupted"
                    job.error_message = "Interrupted by server restart"
                    job.finished_at = now
                session.commit()
    except Exception:
        pass


def json_field(value) -> str:
    if value is None:
        return "[]"
    if isinstance(value, str):
        return value
    return json.dumps(value, ensure_ascii=False)


def parse_json_field(value: Optional[str], default):
    if not value:
        return default
    try:
        return json.loads(value)
    except json.JSONDecodeError:
        return default
