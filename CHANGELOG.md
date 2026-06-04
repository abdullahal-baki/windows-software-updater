# Changelog

All notable changes to this project are documented here. The format is based
on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and this project
adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.0.0]

### Changed

- **Refactored the monolithic `main.py` / `notifier.py` into a layered `wsu`
  package** under `src/`, split into `core`, `services`, `workers`, `ui`, and
  `app` layers. No user-facing behaviour changed.
- Centralised configuration into `wsu.core.config` (driven by `WSU_*`
  environment variables).
- Centralised the theme/stylesheet into `wsu.ui.theme`.

### Added

- Proper Python packaging via `pyproject.toml` (editable install, console
  entry points, `ruff`/`mypy`/`pytest` configuration).
- PyInstaller spec files for both executables (`packaging/*.spec`).
- A single **Inno Setup** installer (`packaging/installer.iss`) that ships
  both executables and registers the notifier to run automatically at every
  login via the per-user autostart registry key.
- Build/dev PowerShell scripts (`scripts/build.ps1`, `scripts/run-dev.ps1`).
- Rotating file logging under the user data directory.
- A pytest suite for the parser and storage layers.
- Documentation: `README.md`, `docs/BUILD.md`, `docs/ARCHITECTURE.md`,
  `CONTRIBUTING.md`.

### Removed

- The throwaway `lab.py` scratch script.
