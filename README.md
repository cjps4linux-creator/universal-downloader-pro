<h1 align="center">Universal Downloader Pro</h1>

<p align="center"><b>Production-grade offline archiver and media downloader with a privacy-first tunnel, knowledge pipeline and batch queue.</b></p>

<p align="center">
  <img src="https://img.shields.io/badge/license-MIT-0a7563" alt="License: MIT">
  <img src="https://img.shields.io/badge/python-3.11%2B-3776ab" alt="Python 3.11+">
  <img src="https://img.shields.io/badge/platform-Windows-8a5800" alt="Platform: Windows">
  <img src="https://img.shields.io/badge/no_account-no_telemetry-0a7563" alt="No account, no telemetry">
</p>

---

## What it does

A local-first download and archive tool. Everything runs on your machine — no
account, no telemetry, no cloud dependency.

- **Media downloads** — yt-dlp powered, with browser-cookie retry for
  YouTube's bot check
- **Offline archiving** — captures a page with its assets and writes a
  semantic, design, dependency, accessibility, security and topology report
- **Knowledge pipeline** — extracts what a site *is* (CMS, framework, patterns)
  into a reusable site playbook
- **Batch queue** — a scheduler with a job queue and export in JSON / CSV /
  Markdown / manifest
- **Optional tunnel** — an app-scoped proxy sidecar for egress control

## Requirements

- Python 3.11+
- [yt-dlp](https://github.com/yt-dlp/yt-dlp) (installed via `pyproject.toml`)

## Install

```bash
git clone https://github.com/cjps4linux-creator/universal-downloader-pro.git
cd universal-downloader-pro

python -m venv .venv
.venv\Scripts\activate          # Windows
pip install -e .
```

### Optional: the tunnel sidecar

The tunnel uses [wireproxy](https://github.com/windtf/wireproxy), a third-party
project that is **not vendored here**. Fetch it with:

```bash
python scripts/setup_wireproxy.py
```

The script downloads a pinned release, verifies its SHA-256 checksum against
the published `checksums.txt`, and installs it to `scripts/wireproxy.exe`.
That path is gitignored and never committed.

If you prefer not to use the sidecar at all, the tunnel module reports itself
as unavailable and the rest of the application works normally.

## Run

```bash
launcher\universal-downloader-pro.bat
```

The Flask backend listens on **port 8765** and the SPA frontend is served from
`frontend/index.html`.

### Launchers

| File | Purpose |
|------|---------|
| `launcher/universal-downloader-pro.bat` | One-click start |
| `launcher/start-udp-venv.vbs` | Silent start (no console window) |
| `launcher/start-server-venv.vbs` | Backend only |
| `scripts/wait_for_health.py` | Poll `/health` until the server is ready |

## Layout

```
backend/      legacy Flask service
frontend/     single-page frontend
src/udp/      the current application package
  api/routes/ HTTP endpoints
  core/       archiver, assets, anti-block, browser cookies
  security/   tunnel sidecar control plane
  workers/    download and scheduler workers
scripts/      launcher, bootstrap and maintenance scripts
launcher/     Windows launchers
docs/         phase brief and session snapshot
```

## Notes

- Personal and non-commercial use. Respect the terms of service and copyright
  of every site and platform you point it at.
- `downloads/` is gitignored — it is output, not source.
- Archives are written next to the captured page as
  `<page_name>.html/` with an accompanying `<page_name>_report.txt`.

## Licence

MIT — see [LICENSE](LICENSE).

Third-party components are not covered by this licence; see each project's own
terms.

---

## Credits

Built by **Conrad CJ Wilson** — [GitHub](https://github.com/cjps4linux-creator) · [LinkedIn](https://linkedin.com/in/conradcjwilson)

`conradcjwilson0@gmail.com`
