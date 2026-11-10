#!/usr/bin/env python3
"""
Fetch the wireproxy binary that Universal Downloader Pro uses for its
optional network tunnel.

wireproxy is a third-party project and is NOT vendored in this repository.
This script downloads a pinned release, verifies its SHA-256 checksum against
the published checksum file, and installs it to scripts/wireproxy.exe.

    python scripts/setup_wireproxy.py

Upstream: https://github.com/windtf/wireproxy  (ISC licence)
"""

from __future__ import annotations

import hashlib
import platform
import shutil
import sys
import tarfile
import tempfile
import urllib.request
from pathlib import Path

REPO = "windtf/wireproxy"
VERSION = "v1.1.3"
CHECKSUMS_URL = (
    f"https://github.com/{REPO}/releases/download/{VERSION}/checksums.txt"
)

TARGET_DIR = Path(__file__).resolve().parent
INSTALL_PATH = TARGET_DIR / "wireproxy.exe"

# Maps (os, arch) -> upstream asset name.
# Keys are lower-cased; platform.machine() is normalised before lookup.
ASSETS = {
    ("windows", "amd64"): "wireproxy_windows_amd64.tar.gz",
    ("windows", "x86"): "wireproxy_windows_386.tar.gz",
    ("windows", "x86_64"): "wireproxy_windows_amd64.tar.gz",
    ("linux", "x86_64"): "wireproxy_linux_amd64.tar.gz",
    ("linux", "amd64"): "wireproxy_linux_amd64.tar.gz",
    ("linux", "aarch64"): "wireproxy_linux_arm64.tar.gz",
    ("linux", "arm64"): "wireproxy_linux_arm64.tar.gz",
    ("linux", "i686"): "wireproxy_linux_386.tar.gz",
    ("linux", "x86"): "wireproxy_linux_386.tar.gz",
    ("linux", "armv7l"): "wireproxy_linux_arm.tar.gz",
    ("linux", "armv6l"): "wireproxy_linux_arm.tar.gz",
    ("darwin", "x86_64"): "wireproxy_darwin_amd64.tar.gz",
    ("darwin", "amd64"): "wireproxy_darwin_amd64.tar.gz",
    ("darwin", "arm64"): "wireproxy_darwin_arm64.tar.gz",
    ("darwin", "aarch64"): "wireproxy_darwin_arm64.tar.gz",
}


def asset_for_current_platform() -> str:
    system = platform.system().lower()
    machine = platform.machine().lower()
    key = (system, machine)
    if key not in ASSETS:
        raise SystemExit(
            f"No wireproxy build for {platform.system()}/{platform.machine()}.\n"
            f"Download it manually from "
            f"https://github.com/{REPO}/releases/tag/{VERSION} and place "
            f"the executable at {INSTALL_PATH}"
        )
    return ASSETS[key]


def download(url: str, dest: Path) -> None:
    print(f"  downloading {url}")
    with urllib.request.urlopen(url) as resp, open(dest, "wb") as out:
        shutil.copyfileobj(resp, out)


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def main() -> int:
    asset = asset_for_current_platform()
    url = f"https://github.com/{REPO}/releases/download/{VERSION}/{asset}"

    print(f"wireproxy setup  -  {REPO} {VERSION}")
    print(f"  asset: {asset}")

    with tempfile.TemporaryDirectory() as tmp:
        tmpdir = Path(tmp)
        archive = tmpdir / asset
        sums = tmpdir / "checksums.txt"

        print("  fetching published checksums...")
        download(CHECKSUMS_URL, sums)

        expected = None
        for line in sums.read_text(encoding="utf-8").splitlines():
            parts = line.split()
            if len(parts) == 2 and parts[1] == asset:
                expected = parts[0]
                break
        if not expected:
            raise SystemExit(f"No checksum published for {asset}  -  refusing to install.")

        print(f"  fetching {asset}...")
        download(url, archive)

        actual = sha256(archive)
        print(f"  expected sha256: {expected}")
        print(f"  actual   sha256: {actual}")
        if actual != expected:
            raise SystemExit("CHECKSUM MISMATCH  -  aborting. The download was not installed.")

        print("  checksum verified")
        print("  extracting...")
        with tarfile.open(archive, "r:gz") as tf:
            members = [m for m in tf.getmembers() if Path(m.name).name in ("wireproxy", "wireproxy.exe")]
            if not members:
                raise SystemExit("wireproxy executable not found inside the archive.")
            member = members[0]
            src = tf.extractfile(member)
            if src is None:
                raise SystemExit("Could not read the wireproxy executable from the archive.")
            with open(INSTALL_PATH, "wb") as out:
                shutil.copyfileobj(src, out)

    if platform.system() == "Windows":
        pass
    else:
        INSTALL_PATH.chmod(0o755)

    print(f"\n  installed -> {INSTALL_PATH}")
    print("  note: scripts/wireproxy.exe is gitignored and is never committed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
