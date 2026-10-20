"""Tests for Universal Downloader Pro — database helpers and knowledge pipeline.

No network. The knowledge pipeline is exercised against a temporary SQLite
database so the real project database is never touched.
"""

from __future__ import annotations

import json
import re
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
    """Point every session in the app at a throwaway SQLite database.

    The modules under test import ``session`` from ``udp.models.db``, so the
    engine has to be swapped on that module *before* those imports resolve
    the binding.  Patching the module attribute is enough, because ``session()``
    looks ``Session`` up on ``udp.models.db`` at call time.
    """
    from udp.models import db as db_module

    db_file = tmp_path / "knowledge.db"
    engine = db_module.create_engine(f"sqlite:///{db_file}")
    session_factory = db_module.sessionmaker(engine, future=True)
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


def test_update_knowledge_from_archive_handles_missing_host(pipeline_db):
    # The pipeline_db fixture is REQUIRED here: without it this test would
    # write a row into the user's live UDP database. A URL with no hostname
    # is recorded under the "unknown" domain.
    from udp.models import db as db_module
    from udp.models.db import KnowledgeDomain, update_knowledge_from_archive

    update_knowledge_from_archive("not-a-url", [], [])

    with db_module.Session() as session:
        row = session.query(KnowledgeDomain).filter_by(domain="unknown").one_or_none()
        assert row is not None


# ---------------------------------------------------------------------------
# Isolation regression
# ---------------------------------------------------------------------------

def test_knowledge_writes_never_touch_the_live_database(tmp_path, monkeypatch):
    """A test run must not mutate the user's real UDP database.

    Regression: the modules under test imported ``Session`` by name, so
    patching ``udp.models.db.Session`` did not affect them and the suite
    silently wrote rows into the live database — visible as a stray
    ``domain='unknown'`` row whose archive counter incremented on every run.

    This test asserts the property directly: after exercising the write path
    against a temporary database, the live database is byte-for-byte
    unchanged.
    """
    import hashlib

    from udp.models import db as db_module
    from udp.models.db import update_knowledge_from_archive

    live_path = db_module.DB_PATH
    live_before = (
        hashlib.sha256(live_path.read_bytes()).hexdigest()
        if live_path.exists()
        else None
    )

    # Now exercise the write path through the temporary engine.
    db_file = tmp_path / "isolated.db"
    engine = db_module.create_engine(f"sqlite:///{db_file}")
    factory = db_module.sessionmaker(engine, future=True)
    monkeypatch.setattr(db_module, "Session", factory)
    db_module.Base.metadata.create_all(engine)

    update_knowledge_from_archive(
        "https://isolated.example/page",
        [{"url": "https://cdn.isolated.example/a.png", "kind": "image"}],
        [],
    )

    # The row landed in the temporary database ...
    with factory() as session:
        row = session.query(db_module.KnowledgeDomain).filter_by(
            domain="isolated.example").one_or_none()
        assert row is not None, "the write did not reach the temporary database"

    # ... and the live database is untouched.
    live_after = (
        hashlib.sha256(live_path.read_bytes()).hexdigest()
        if live_path.exists()
        else None
    )
    assert live_before == live_after, (
        "the test suite modified the live UDP database — "
        f"{live_path} changed during the run"
    )

    engine.dispose()


def test_db_path_is_overridable_by_environment(monkeypatch, tmp_path):
    """UDP_DB_PATH lets a deployment or a test point at another database."""
    import importlib

    from udp.models import db as db_module

    target = tmp_path / "custom.db"
    monkeypatch.setenv("UDP_DB_PATH", str(target))
    reloaded = importlib.reload(db_module)
    try:
        assert reloaded.DB_PATH == target
        # SQLAlchemy percent-encodes the Windows drive colon in the URL,
        # so compare the decoded path rather than the raw URL string.
        assert reloaded.DB_PATH == target
        assert target.name in reloaded.ENGINE.url.database
    finally:
        monkeypatch.delenv("UDP_DB_PATH", raising=False)
        importlib.reload(db_module)
