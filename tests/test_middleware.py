"""Tests for Universal Downloader Pro — request security middleware.

Covers the token gate, the Host/Origin allow-list, and the SSRF pre-check
that runs before a download body reaches the engine.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT / "src") not in sys.path:
    sys.path.insert(0, str(REPO_ROOT / "src"))

from udp.security import middleware  # noqa: E402


# ---------------------------------------------------------------------------
# Token handling
# ---------------------------------------------------------------------------

def test_get_api_token_uses_environment_token(monkeypatch):
    monkeypatch.setenv("UDP_API_TOKEN", "s3cret-token")
    assert middleware._get_api_token() == "s3cret-token"


def test_get_api_token_generates_when_missing(monkeypatch):
    monkeypatch.delenv("UDP_API_TOKEN", raising=False)
    token = middleware._get_api_token()
    assert token
    assert len(token) >= 32
    # The generated token is cached in the environment for the process.
    import os

    assert os.environ["UDP_API_TOKEN"] == token


def test_get_api_token_strips_whitespace(monkeypatch):
    monkeypatch.setenv("UDP_API_TOKEN", "  padded  ")
    assert middleware._get_api_token() == "padded"


def test_require_token_rejects_missing_header():
    from flask import Flask

    app = Flask(__name__)
    with app.test_request_context("/api/download", method="POST"):
        result = middleware._require_token()
    assert result is not None
    assert result[1] == 401


def test_require_token_rejects_wrong_token(monkeypatch):
    from flask import Flask

    monkeypatch.setenv("UDP_API_TOKEN", "correct-token")
    app = Flask(__name__)
    with app.test_request_context(
        "/api/download", method="POST", headers={"X-API-Token": "wrong-token"}
    ):
        result = middleware._require_token()
    assert result is not None
    assert result[1] == 401


def test_require_token_accepts_correct_token(monkeypatch):
    from flask import Flask

    monkeypatch.setenv("UDP_API_TOKEN", "correct-token")
    app = Flask(__name__)
    with app.test_request_context(
        "/api/download", method="POST", headers={"X-API-Token": "correct-token"}
    ):
        assert middleware._require_token() is None


# ---------------------------------------------------------------------------
# Host allow-list
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("host", ["127.0.0.1", "localhost"])
def test_check_host_allows_loopback(host):
    from flask import Flask

    app = Flask(__name__)
    with app.test_request_context("/health", headers={"Host": host}):
        assert middleware._check_host() is None


def test_check_host_blocks_external_host():
    from flask import Flask

    app = Flask(__name__)
    with app.test_request_context("/health", headers={"Host": "evil.example.com"}):
        result = middleware._check_host()
    assert result is not None
    assert result[1] == 403


# ---------------------------------------------------------------------------
# Origin allow-list
# ---------------------------------------------------------------------------

def test_check_origin_allows_missing_origin():
    from flask import Flask

    app = Flask(__name__)
    with app.test_request_context("/health"):
        assert middleware._check_origin() is None


@pytest.mark.parametrize("origin", ["http://127.0.0.1:8765", "http://localhost:3000"])
def test_check_origin_allows_loopback_origins(origin):
    from flask import Flask

    app = Flask(__name__)
    with app.test_request_context("/health", headers={"Origin": origin}):
        assert middleware._check_origin() is None


def test_check_origin_blocks_external_origin():
    from flask import Flask

    app = Flask(__name__)
    with app.test_request_context("/health", headers={"Origin": "http://evil.example.com"}):
        result = middleware._check_origin()
    assert result is not None
    assert result[1] == 403


# ---------------------------------------------------------------------------
# SSRF pre-check
# ---------------------------------------------------------------------------

def test_check_ssrf_blocks_private_address(monkeypatch):
    from flask import Flask

    monkeypatch.setattr(middleware, "resolve_host", lambda url: "127.0.0.1")
    app = Flask(__name__)
    with app.test_request_context("/api/download", method="POST"):
        result = middleware._check_ssrf("http://internal.example/")
    assert result is not None
    assert result[1] == 403


def test_check_ssrf_allows_public_address(monkeypatch):
    from flask import Flask

    monkeypatch.setattr(middleware, "resolve_host", lambda url: "93.184.216.34")
    app = Flask(__name__)
    with app.test_request_context("/api/download", method="POST"):
        assert middleware._check_ssrf("https://example.com/") is None


def test_check_ssrf_rejects_unresolvable_host(monkeypatch):
    from flask import Flask

    def boom(url):
        raise OSError("dns failure")

    monkeypatch.setattr(middleware, "resolve_host", boom)
    app = Flask(__name__)
    with app.test_request_context("/api/download", method="POST"):
        result = middleware._check_ssrf("https://example.com/")
    assert result is not None
    assert result[1] == 400


# ---------------------------------------------------------------------------
# Body inspection
# ---------------------------------------------------------------------------

def test_wrap_ssrf_extracts_url_from_body():
    assert middleware._wrap_ssrf({"url": "https://example.com/"}) is None


def test_wrap_ssrf_ignores_body_without_url():
    assert middleware._wrap_ssrf({"mode": "web"}) is None


def test_wrap_ssrf_ignores_non_dict_body():
    assert middleware._wrap_ssrf("not a dict") is None


def test_wrap_ssrf_uses_first_url_in_list(monkeypatch):
    from flask import Flask

    monkeypatch.setattr(middleware, "resolve_host", lambda url: "127.0.0.1")
    app = Flask(__name__)
    # _wrap_ssrf calls jsonify(), which needs an application context.
    with app.test_request_context("/api/download", method="POST"):
        result = middleware._wrap_ssrf({"urls": ["http://internal.example/"]})
    assert result is not None
    assert result["error"] == "Forbidden"


def test_wrap_ssrf_ignores_empty_url_list():
    assert middleware._wrap_ssrf({"urls": []}) is None
