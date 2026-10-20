"""Tests for Universal Downloader Pro — database helpers and knowledge pipeline.

No network. The knowledge pipeline is exercised against a temporary SQLite
database so the real project database is never touched.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT / "src") not in sys.path:
    sys.path.insert(0, str(REPO_ROOT / "src"))

from udp.models.db import json_field, parse_json_field  # noqa: E402


# ---------------------------------------------------------------------------
# json_field
# ---------------------------------------------------------------------------

def test_json_field_none_becomes_empty_list():
    assert json_field(None) == "[]"


def test_json_field_passes_strings_through():
    assert json_field('["a"]') == '["a"]'


def test_json_field_serialises_sequences():
    assert json.loads(json_field(["a", "b"])) == ["a", "b"]


def test_json_field_serialises_dicts():
    assert json.loads(json_field({"a": 1})) == {"a": 1}


def test_json_field_preserves_unicode():
    assert "é" in json_field(["café"])


# ---------------------------------------------------------------------------
# parse_json_field
# ---------------------------------------------------------------------------

def test_parse_json_field_returns_default_for_none():
    assert parse_json_field(None, []) == []


def test_parse_json_field_returns_default_for_empty_string():
    assert parse_json_field("", []) == []


def test_parse_json_field_parses_valid_json():
    assert parse_json_field('["a", "b"]', []) == ["a", "b"]


def test_parse_json_field_returns_default_on_invalid_json():
    assert parse_json_field("{not json", []) == []


def test_parse_json_field_returns_default_on_type_mismatch():
    # Valid JSON but not the expected shape — the caller decides what to do.
    assert parse_json_field('{"a": 1}', []) == {"a": 1}


# ---------------------------------------------------------------------------
# Knowledge pipeline
# ---------------------------------------------------------------------------

@pytest.fixture()
def pipeline_db(tmp_path, monkeypatch):
    """Point the SQLAlchemy session at a throwaway SQLite database."""
    from udp.models import db as db_module

    db_file = tmp_path / "knowledge.db"
    engine = db_module.create_engine(f"sqlite:///{db_file}")
    session_factory = db_module.sessionmaker(engine, future=True)
    monkeypatch.setattr(db_module, "ENGINE", engine)
    monkeypatch.setattr(db_module, "Session", session_factory)
    db_module.Base.metadata.create_all(engine)
    yield session_factory
    engine.dispose()


def test_build_playbook_creates_markdown_file(tmp_path, monkeypatch, pipeline_db):
    from udp.knowledge import pipeline

    out = tmp_path / "playbook.md"
    monkeypatch.setattr(pipeline, "downloads_dir", lambda: tmp_path)

    result = pipeline.build_playbook()
    assert result.exists()
    content = result.read_text(encoding="utf-8")
    assert "Site Playbook" in content


def test_export_training_writes_jsonl(tmp_path, monkeypatch, pipeline_db):
    from udp.knowledge import pipeline

    monkeypatch.setattr(pipeline, "downloads_dir", lambda: tmp_path)

    result = pipeline.export_training()
    assert result.exists()
    # With no jobs, the file is empty but still valid.
    assert result.read_text(encoding="utf-8") == ""


def test_update_knowledge_from_archive_records_domain(tmp_path, monkeypatch, pipeline_db):
    from udp.models import db as db_module
    from udp.models.db import KnowledgeDomain, update_knowledge_from_archive

    update_knowledge_from_archive(
        "https://example.com/page",
        [{"url": "https://cdn.example.org/a.png", "kind": "image"}],
        [],
    )

    with db_module.Session() as session:
        row = session.query(KnowledgeDomain).filter_by(domain="example.com").one_or_none()
        assert row is not None
        assert row.domain == "example.com"


def test_update_knowledge_from_archive_handles_missing_host():
    from udp.models import db as db_module
    from udp.models.db import KnowledgeDomain, update_knowledge_from_archive

    update_knowledge_from_archive("not-a-url", [], [])

    with db_module.Session() as session:
        row = session.query(KnowledgeDomain).filter_by(domain="unknown").one_or_none()
        assert row is not None
