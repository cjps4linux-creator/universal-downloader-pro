"""Contract tests for the Universal Downloader Pro frontend.

The knowledge base panel is a real feature with a real backend, so the
HTML that renders it is part of the product surface. These tests assert
that the panel, its filters and its API wiring are present, and that the
API contract the frontend depends on is served.

Pure: no network, no browser, no writes outside tmp_path.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT / "src") not in sys.path:
    sys.path.insert(0, str(REPO_ROOT / "src"))

FRONTEND = REPO_ROOT / "frontend" / "index.html"


@pytest.fixture(scope="module")
def html() -> str:
    assert FRONTEND.exists(), "frontend/index.html is missing"
    return FRONTEND.read_text(encoding="utf-8", errors="replace")


def test_frontend_exists():
    assert FRONTEND.exists()
    assert FRONTEND.stat().st_size > 10_000


def test_knowledge_button_is_present(html: str):
    assert 'id="kbBtn"' in html
    assert "Knowledge" in html


def test_knowledge_panel_structure(html: str):
    for element_id in ["kbPanel", "kbSearch", "kbCms", "kbType", "kbStats", "kbBody"]:
        assert f'id="{element_id}"' in html, f"missing element: {element_id}"


def test_knowledge_panel_calls_the_api(html: str):
    assert "/api/knowledge" in html
    # the delete call must be namespaced to a single domain
    assert re.search(r"/api/knowledge/\'?\s*\+\s*encodeURIComponent", html)


def test_knowledge_panel_has_filter_logic(html: str):
    assert "kbQuery" in html
    assert "renderKnowledge" in html
    assert "loadKnowledge" in html


def test_knowledge_panel_escapes_untrusted_values(html: str):
    """Domain names come from the archive target and are attacker-influenced."""
    for snippet in ["escapeHtml(d.domain)", "escapeHtml(b)"]:
        assert snippet in html, f"untrusted value is not escaped: {snippet}"


def test_knowledge_api_route_is_registered():
    from udp.app import create_app

    app = create_app()
    rules = {r.rule for r in app.url_map.iter_rules()}
    assert "/api/knowledge" in rules
    assert any(r.startswith("/api/knowledge/") for r in rules)


def test_knowledge_api_returns_domains():
    from udp.app import create_app

    app = create_app()
    client = app.test_client()
    resp = client.get("/api/knowledge")
    assert resp.status_code == 200
    body = resp.get_json()
    assert "domains" in body
    assert "count" in body
    assert isinstance(body["domains"], list)


def test_knowledge_api_accepts_filters():
    from udp.app import create_app

    app = create_app()
    client = app.test_client()
    for query in ["?q=example", "?cms=WordPress", "?site_type=blog"]:
        resp = client.get(f"/api/knowledge{query}")
        assert resp.status_code == 200, f"filter {query} failed"
        assert isinstance(resp.get_json()["domains"], list)
