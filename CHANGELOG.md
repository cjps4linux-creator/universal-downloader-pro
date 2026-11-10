# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.0.0]  -  2026-10-20

### Added

- **Real CI test gate.** The workflow ran `pytest -q || echo "No tests yet"`
  and never installed `pytest-cov`, so the declared `--cov=udp` and
  `fail_under` had never once been enforced. Both are now installed and
  the suite runs unconditionally. It has 120 Python tests and 25 frontend
  DOM assertions.
- **Frontend job.** A Node 20 / jsdom job runs the DOM contract test, so
  the single-page UI is covered by CI rather than by inspection.
- **Dependency pin guard** (`scripts/pin_guard.py`), wired as a required
  `pin-check` status check.
- **Dependabot policy** (`.github/dependabot.yml`) with a weekly schedule
  that groups minor and patch updates and excludes the pinned test
  toolchain, so a grouped pull request cannot silently move the project
  onto a pre-release.
- **Knowledge base browser** in the frontend: a searchable, filterable
  panel with summary tiles and row deletion, backed by the existing
  knowledge API. All attacker-influenced values are escaped.
- **`requirements.txt`**, so the project installs from a published
  manifest. `sqlalchemy` and `browser-cookie3` were previously undeclared.

### Fixed

- **The test suite wrote to the live application database.** The database
  path is now overridable through `UDP_DB_PATH`, the session is created at
  call time through a `session()` factory, and a repository-wide
  `tests/conftest.py` redirects the path before any application import.
  A regression test hashes the live database before and after the suite
  and asserts it is unchanged.
- **Undefined names** in `downloads.py`, `system.py` and `scheduler.py`,
  which the Ruff `F821` rule surfaced.
- **The venv `yt-dlp` path** is now resolved from the project root.
- The project version is now `1.0.0` in `pyproject.toml`, `package.json`
  and the health endpoint.

### Changed

- The Ruff rule set is pinned to `E4,E7,E9,F` with `ruff==0.17.1`.
- **Launcher scripts are location-independent.** The whole launcher family
   -  the VBScript and CMD entry points, the restart and debug scripts and
  the shortcut PowerShell scripts  -  now resolves its own directory.
- **README author credit** added: Conrad CJ Wilson.

### Removed

- **The bundled `wireproxy` binary.** It was purged from the entire Git
  history and replaced with `scripts/setup_wireproxy.py`, a pinned,
  checksum-verified bootstrap for `windtf/wireproxy` `v1.1.3`. The
  tunnel also falls back to a system-installed `wireproxy`.

### Coverage

The coverage floor is a documented ratchet at 35%, measured at 39.12%.
The floor was reduced from an aspirational 80% only after the suite was
expanded from 74 to 120 tests; the reason is recorded in `pyproject.toml`.

### Security

- Secret scanning and push protection enabled at the repository level.

## [0.1.0]

- Baseline: yt-dlp streaming, browser-cookie retry, batch queue and export
- Offline archiver with semantic/design/dependency/accessibility/security/topology extraction
- Knowledge pipeline: site fingerprinting, CMS/framework detection and playbook generation
- Unvendor the wireproxy binary; replaced with a checksum-verified bootstrap script

[1.0.0]: https://github.com/cjps4linux-creator/universal-downloader-pro/releases/tag/v1.0.0
