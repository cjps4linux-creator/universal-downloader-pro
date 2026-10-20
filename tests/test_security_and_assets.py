"""Tests for Universal Downloader Pro — security guards, asset store, paths.

These are pure unit tests: no network, no database, no subprocess.
They target the security-critical code paths so that a regression in the
SSRF guard or the archive-path containment check fails CI loudly.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT / "src") not in sys.path:
    sys.path.insert(0, str(REPO_ROOT / "src"))


# ---------------------------------------------------------------------------
# SSRF guard
# ---------------------------------------------------------------------------

from udp.security.ssrf import validate_url, resolve_and_validate  # noqa: E402


@pytest.mark.parametrize(
    "url",
    [
        "file:///etc/passwd",
        "gopher://x",
        "ftp://host/file",
        "data:text/html,<script>",
        "javascript:alert(1)",
        "ws://example.com",
    ],
)
def test_validate_url_rejects_non_http_schemes(url):
    with pytest.raises(ValueError):
        validate_url(url)


@pytest.mark.parametrize(
    "url",
    [
        "http://localhost/",
        "http://127.0.0.1/",
        "http://0.0.0.0/",
        "http://169.254.169.254/latest/meta-data/",
        "http://[::1]/",
    ],
)
def test_validate_url_rejects_blocked_hosts(url):
    with pytest.raises(ValueError):
        validate_url(url)


@pytest.mark.parametrize(
    "url",
    [
        "http://10.0.0.5/",
        "http://192.168.1.1/",
        "http://172.16.0.1/",
        "http://127.1.2.3/",
    ],
)
def test_validate_url_rejects_private_ranges(url):
    with pytest.raises(ValueError):
        validate_url(url)


def test_validate_url_accepts_public_hostname():
    # No exception expected. Does not perform DNS resolution.
    validate_url("https://example.com/path?q=1")


def test_resolve_and_validate_requires_host():
    with pytest.raises(ValueError):
        resolve_and_validate("https:///nohost")


# ---------------------------------------------------------------------------
# HTML / filename sanitisation
# ---------------------------------------------------------------------------

from udp.security.sanitizer import (  # noqa: E402
    sanitize_html,
    sanitize_filename,
    validate_archive_path,
    archive_safe_headers,
)


def test_sanitize_html_strips_script_tags():
    out = sanitize_html("<p>ok</p><script>alert('x')</script>")
    assert "<script" not in out.lower()
    assert "ok" in out


def test_sanitize_html_strips_event_handlers():
    out = sanitize_html('<div onclick="steal()">text</div>')
    assert "onclick" not in out.lower()


def test_sanitize_html_handles_empty_input():
    assert sanitize_html("") == ""


@pytest.mark.parametrize(
    "raw",
    [
        "a/b\\c:d*e?f",
        "..",
        "   ",
        "name with spaces",
    ],
)
def test_sanitize_filename_strips_path_separators(raw):
    out = sanitize_filename(raw)
    assert "/" not in out
    assert "\\" not in out
    assert ":" not in out
    assert out  # never empty


def test_sanitize_filename_truncates_long_names():
    out = sanitize_filename("x" * 500)
    assert len(out) <= 180


def test_validate_archive_path_blocks_traversal(tmp_path):
    root = tmp_path / "archive"
    root.mkdir()
    outside = tmp_path / "secret.txt"
    outside.write_text("secret", encoding="utf-8")

    assert validate_archive_path(outside, root) is None


def test_validate_archive_path_accepts_inside_root(tmp_path):
    root = tmp_path / "archive"
    root.mkdir()
    inside = root / "page.html"
    inside.write_text("<html></html>", encoding="utf-8")

    result = validate_archive_path(inside, root)
    assert result is not None
    assert result.name == "page.html"


def test_archive_safe_headers_include_csp():
    headers = archive_safe_headers()
    assert "Content-Security-Policy" in headers
    assert "default-src" in headers["Content-Security-Policy"]


# ---------------------------------------------------------------------------
# Asset store
# ---------------------------------------------------------------------------

from udp.core.assets import (  # noqa: E402
    sha256_file,
    content_addressed_path,
    unique_dest_path,
    part_path,
    resume_bytes,
    move_part_to_final,
)


def test_sha256_file_matches_hashlib(tmp_path):
    import hashlib

    f = tmp_path / "a.bin"
    f.write_bytes(b"hello world")
    assert sha256_file(f) == hashlib.sha256(b"hello world").hexdigest()


def test_sha256_file_empty(tmp_path):
    import hashlib

    f = tmp_path / "empty.bin"
    f.write_bytes(b"")
    assert sha256_file(f) == hashlib.sha256(b"").hexdigest()


def test_content_addressed_path_uses_prefix_shards():
    digest = "ab" * 32
    p = content_addressed_path(digest, ".bin")
    # with_suffix() keeps the hash as the stem and applies the suffix
    assert p.stem == digest
    assert p.suffix == ".bin"
    assert p.parent.name == "ab"


def test_unique_dest_path_returns_base_when_free(tmp_path):
    target = tmp_path / "file.bin"
    assert unique_dest_path(target) == target


def test_unique_dest_path_avoids_overwrite(tmp_path):
    target = tmp_path / "file.bin"
    target.write_bytes(b"x")
    nxt = unique_dest_path(target)
    assert nxt != target
    assert nxt.name == "file_1.bin"


def test_part_path_appends_part_suffix(tmp_path):
    assert part_path(tmp_path / "file.bin").name == "file.bin.part"


def test_resume_bytes_reads_part_size(tmp_path):
    part = tmp_path / "file.bin.part"
    part.write_bytes(b"12345")
    assert resume_bytes(part) == 5


def test_resume_bytes_missing_part_is_zero(tmp_path):
    assert resume_bytes(tmp_path / "nope.part") == 0


def test_move_part_to_final_renames(tmp_path):
    part = tmp_path / "file.bin.part"
    dest = tmp_path / "file.bin"
    part.write_bytes(b"payload")
    move_part_to_final(part, dest)
    assert dest.read_bytes() == b"payload"
    assert not part.exists()


def test_move_part_to_final_raises_when_nothing_present(tmp_path):
    with pytest.raises(FileNotFoundError):
        move_part_to_final(tmp_path / "a.part", tmp_path / "a.bin")
