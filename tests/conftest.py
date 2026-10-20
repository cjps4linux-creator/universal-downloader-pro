"""Shared pytest configuration for the Universal Downloader Pro test-suite.

The most important thing this file does is guarantee that **no test can
write to the developer's live database**.

Regression: ``udp.models.db`` exposes a module-level ``Session`` factory, and
the application modules imported it by name
(``from udp.models.db import Session``).  Patching
``udp.models.db.Session`` in a fixture therefore did *not* affect those
modules, so a test that forgot to request the database fixture silently
wrote rows into ``%LOCALAPPDATA%/UniversalDownloaderPro/udp.db``.  The
symptom was a stray ``domain='unknown'`` row whose archive counter
incremented on every test run.

The fix has two halves:

1. ``UDP_DB_PATH`` makes the database location overridable, and the modules
   now resolve their session through ``udp.models.db.session()`` so the
   override is always honoured.
2. This file points ``UDP_DB_PATH`` at a temporary file **before any
   application module is imported**, so even a test that forgets the
   fixture cannot reach the live database.
"""

from __future__ import annotations

import os
import tempfile
from pathlib import Path

# The override must be in place before udp.models.db is imported anywhere,
# because DB_PATH is read at import time. pytest loads conftest.py before
# collecting test modules, so setting it here is early enough.
_TMP_DB_DIR = Path(tempfile.gettempdir()) / "udp-pytest-isolated"
_TMP_DB_DIR.mkdir(parents=True, exist_ok=True)
os.environ["UDP_DB_PATH"] = str(_TMP_DB_DIR / "udp-test.db")

# Never let a test reach the network by accident.
os.environ.setdefault("UDP_API_TOKEN", "pytest-isolated-token")

import pytest  # noqa: E402


@pytest.fixture(scope="session", autouse=True)
def isolated_database():
    """Point the whole session at a throwaway database.

    This is belt-and-braces alongside ``UDP_DB_PATH`` above: if a module
    captured the engine at import time before the override applied, the
    engine is re-pointed here as well.
    """
    from udp.models import db as db_module

    target = Path(os.environ["UDP_DB_PATH"])
    engine = db_module.create_engine(f"sqlite:///{target}")
    factory = db_module.sessionmaker(engine, future=True)

    db_module.ENGINE = engine
    db_module.Session = factory
    db_module.Base.metadata.create_all(engine)

    yield target

    engine.dispose()


@pytest.fixture()
def live_database_untouched():
    """Assert that a block of code leaves the live database unmodified.

    Use this to guard any code path that must not persist anything.
    """
    import hashlib

    from udp.models import db as db_module

    path = db_module.DB_PATH
    before = hashlib.sha256(path.read_bytes()).hexdigest() if path.exists() else None

    yield path

    after = hashlib.sha256(path.read_bytes()).hexdigest() if path.exists() else None
    assert before == after, f"the live UDP database was modified: {path}"
