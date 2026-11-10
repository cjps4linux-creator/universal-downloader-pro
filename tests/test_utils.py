"""Tests for Universal Downloader Pro  -  shared utility helpers.

Pure unit tests: no network, no filesystem writes outside tmp_path.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT / "src") not in sys.path:
    sys.path.insert(0, str(REPO_ROOT / "src"))

from udp.utils import (  # noqa: E402
    sanitize_filename,
    unique_path,
    derive_page_name,
    compute_backoff,
    is_private_ip,
)
from udp.utils.paths import task_dir, downloads_dir  # noqa: E402


# ---------------------------------------------------------------------------
# Filename sanitisation
# ---------------------------------------------------------------------------

@pytest.mark.parametrize(
    "raw",
    [
        'a/b\\c:d*e?f"g<h>i|j',
        "with\x00null",
        "trailing dot.",
        "   ",
        "",
    ],
)
def test_sanitize_filename_removes_unsafe_characters(raw):
    out = sanitize_filename(raw)
    assert out
    for ch in '<>:"/\\|?*':
        assert ch not in out
    assert "\x00" not in out


def test_sanitize_filename_collapses_whitespace_and_dots():
    out = sanitize_filename("a   b...c")
    assert " " not in out
    assert ".." not in out


def test_sanitize_filename_truncates():
    assert len(sanitize_filename("y" * 400)) == 180


# ---------------------------------------------------------------------------
# Unique paths
# ---------------------------------------------------------------------------

def test_unique_path_returns_input_when_absent(tmp_path):
    p = tmp_path / "file.bin"
    assert unique_path(p) == p


def test_unique_path_increments_counter(tmp_path):
    p = tmp_path / "file.bin"
    p.write_bytes(b"a")
    first = unique_path(p)
    first.write_bytes(b"b")
    second = unique_path(p)
    assert first.name == "file_1.bin"
    assert second.name == "file_2.bin"


# ---------------------------------------------------------------------------
# Page-name derivation
# ---------------------------------------------------------------------------

def test_derive_page_name_uses_title():
    name = derive_page_name("https://example.com/some/path", "My Page Title")
    assert name == "My_Page_Title"


def test_derive_page_name_falls_back_to_slug():
    name = derive_page_name("https://example.com/some/path", None)
    assert name == "path"


def test_derive_page_name_handles_root_url():
    name = derive_page_name("https://example.com/", None)
    assert name  # [lorem]-empty
    assert name == "page"


def test_derive_page_name_strips_special_characters():
    name = derive_page_name("https://example.com/x", "Price: $100 (USD)!")
    assert "$" not in name
    assert "(" not in name


def test_derive_page_name_truncates_to_80():
    name = derive_page_name("https://example.com/x", "a" * 300)
    assert len(name) <= 80


# ---------------------------------------------------------------------------
# Backoff
# ---------------------------------------------------------------------------

def test_compute_backoff_grows_exponentially():
    low = compute_backoff(0, base=1.0, cap=100.0)
    high = compute_backoff(5, base=1.0, cap=100.0)
    assert high > low


def test_compute_backoff_respects_cap():
    value = compute_backoff(20, base=1.0, cap=30.0)
    # cap + max jitter (<=1.0)
    assert value <= 31.0


def test_compute_backoff_is_non_negative():
    assert compute_backoff(0) >= 0.0


# ---------------------------------------------------------------------------
# Private IP detection
# ---------------------------------------------------------------------------

@pytest.mark.parametrize(
    "ip",
    ["127.0.0.1", "10.1.2.3", "192.168.0.1", "172.16.5.5", "::1"],
)
def test_is_private_ip_detects_private(ip):
    assert is_private_ip(ip) is True


def test_is_private_ip_detects_public():
    assert is_private_ip("8.8.8.8") is False


def test_is_private_ip_treats_invalid_as_private():
    # Fail closed: an unparsable address must not be considered public.
    assert is_private_ip("not-an-ip") is True


# ---------------------------------------------------------------------------
# Path helpers
# ---------------------------------------------------------------------------

def test_task_dir_is_under_downloads_dir():
    assert task_dir("abc").parent == downloads_dir()
    assert task_dir("abc").name == "abc"
