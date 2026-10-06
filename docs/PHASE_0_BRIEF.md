# Universal Downloader Pro — Phase 0 Engineering Brief

**Project:** Universal Downloader Pro  
**Base:** Universal Downloader v1  
**Target:** Production-grade Windows 11 desktop application  
**Status:** Phase 0 — Stabilization scaffold  

## Goals
- Modular backend package with security middleware
- SQLite persistence for jobs, settings, and knowledge
- API lockdown with per-launch token + Host/Origin + SSRF guard
- Test harness and CI-friendly layout
- Reproducible packaging via `pyproject.toml`

## Phase 0 Exit Criteria
- `uv sync` succeeds
- App starts via launcher and `/health` returns 200
- Token + Host checks reject bad requests
- `/api/download` creates a durable job row
- `/api/knowledge` returns the seeded domain list

## Directory Layout
```
universal-downloader-pro/
  src/udp/
    app.py
    api/routes/{downloads,knowledge,system}.py
    models/db.py
    security/middleware.py
    utils/{__init__,paths}.py
    knowledge/pipeline.py
    workers/  (Phase 1)
  frontend/index.html
  launcher/universal-downloader-pro.bat
  downloads/
  tests/{unit,integration,contract,ui}
  docs/
  pyproject.toml
```

## Constraints
- Windows 11, Python 3.13 (broad wheel availability)
- No Docker/WSL
- Personal/non-commercial use only
- No marketing, sale, or commercial distribution
