"""Tests for the Universal Downloader Pro Flask application factory.

Uses Flask's test client — no real HTTP server, no network.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT / "src") not in sys.path:
    sys.path.insert(0, str(REPO_ROOT / "src"))


@pytest.fixture(scope="module")
def client():
    from udp.app import create_app

    app = create_app()
    app.config.update(TESTING=True)
    with app.test_client() as c:
        yield c


def test_health_endpoint_reports_ok(client):
    resp = client.get("/health")
    assert resp.status_code == 200
    payload = resp.get_json()
    assert payload["status"] == "ok"
    assert payload["service"] == "universal-downloader-pro"


def test_analyze_requires_url(client):
    resp = client.get("/api/analyze")
    assert resp.status_code == 400
    assert "error" in resp.get_json()


def test_analyze_detects_stream_category(client):
    resp = client.get("/api/analyze?url=https://www.youtube.com/watch?v=abc")
    assert resp.status_code == 200
    assert resp.get_json()["mode"] == "stream"


def test_analyze_detects_doc_category(client):
    resp = client.get("/api/analyze?url=https://example.com/report.pdf")
    assert resp.status_code == 200
    assert resp.get_json()["mode"] == "doc"


def test_analyze_detects_media_category(client):
    resp = client.get("/api/analyze?url=https://example.com/clip.mp4")
    assert resp.status_code == 200
    assert resp.get_json()["mode"] == "media"


def test_analyze_detects_archive_category(client):
    resp = client.get("/api/analyze?url=https://example.com/bundle.zip")
    assert resp.status_code == 200
    assert resp.get_json()["mode"] == "archive"


def test_analyze_derives_filename_from_path(client):
    resp = client.get("/api/analyze?url=https://example.com/docs/report.pdf")
    assert resp.status_code == 200
    assert resp.get_json()["filename"] == "report.pdf"


def test_app_registers_core_routes():
    from udp.app import create_app

    app = create_app()
    rules = {r.rule for r in app.url_map.iter_rules()}
    for expected in (
        "/health",
        "/api/analyze",
        "/api/knowledge",
        "/api/queue",
        "/api/playbook",
        "/api/download",
    ):
        assert expected in rules, f"missing route: {expected}"


def test_token_endpoint_returns_json(client):
    resp = client.get("/api/token")
    assert resp.status_code == 200
    assert "token" in resp.get_json()


def test_protected_route_requires_api_token(client):
    # A route outside the public allow-list must reject a missing token.
    resp = client.put("/api/settings")
    assert resp.status_code == 401
    body = resp.get_json()
    assert body["error"] == "Unauthorized"


def test_public_routes_do_not_require_token(client):
    for path in ("/health", "/api/analyze?url=https://example.com", "/api/knowledge", "/api/token"):
        resp = client.get(path)
        assert resp.status_code != 401, f"{path} unexpectedly required a token"
