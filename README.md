# Windows Software Updater

A polished PyQt6 desktop application that wraps the **Windows Package Manager
(winget)** to scan for, install, and manage software updates — with a custom
frameless dark UI, live progress, system-tray notifications, and per-package
*exclude* / *skip* controls.

![Platform](https://img.shields.io/badge/platform-Windows-blue)
![Python](https://img.shields.io/badge/python-3.9%2B-blue)
![UI](https://img.shields.io/badge/UI-PyQt6-41cd52)
![License](https://img.shields.io/badge/license-MIT-green)

---

## Features

- **One-click scanning** of all upgradable packages via `winget upgrade`.
- **Update all, selected, or single** packages with **live download/install
  progress** streamed straight from winget.
- **Exclude** packages permanently or **skip** a specific version (and be
  reminded again when a newer one ships).
- **Background notifier** that runs automatically at every login (registered
  by the installer) and shows a tray toast when updates are available — click
  it to open the updater.
- **Responsive UI** — all winget/network calls run on background threads, so
  the window never freezes.
- **Self-contained artwork** — the logo and all icons are drawn procedurally;
  the only asset is `icon.ico`.

## Requirements

- Windows 10 / 11 (x64)
- [winget](https://learn.microsoft.com/windows/package-manager/winget/)
  (ships with modern Windows; otherwise install *App Installer* from the
  Microsoft Store)
- Python 3.9+ (for running from source or building)

## Quick start (from source)

```powershell
# Clone, then from the project root:
.\scripts\run-dev.ps1            # creates .venv, installs deps, launches the GUI
.\scripts\run-dev.ps1 -Notifier  # run the background notifier instead
```

Or manually:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -e ".[dev]"
python -m wsu                    # launch the GUI
python -m wsu.app.notifier       # launch the notifier
```

## Building the executables & installer

See **[docs/BUILD.md](docs/BUILD.md)** for the full guide, including how to
compile the installer with **Inno Setup**. The short version:

```powershell
.\scripts\build.ps1 -Clean -Installer
```

This produces `dist\Updater.exe`, `dist\Update Notifier.exe`, and
`dist\installer\WindowsSoftwareUpdater-Setup-<version>.exe`.

## Project layout

```
windows-software-updater/
├── main.py                      # compatibility shim → wsu.app.updater
├── notifier.py                  # compatibility shim → wsu.app.notifier
├── pyproject.toml               # packaging, dependencies, tooling config
├── icon.ico                     # the single bundled asset
├── src/wsu/                     # the application package
│   ├── core/                    # config, paths, storage, models, logging
│   ├── services/                # the winget integration layer
│   ├── workers/                 # background QThread workers
│   ├── ui/                      # theme, widgets, the main window
│   └── app/                     # entry points (updater, notifier)
├── packaging/                   # PyInstaller specs + Inno Setup script
├── scripts/                     # build.ps1, run-dev.ps1
├── tests/                       # pytest suite for the pure-logic layers
└── docs/                        # architecture & build documentation
```

A deeper explanation of each layer lives in
**[docs/ARCHITECTURE.md](docs/ARCHITECTURE.md)**.

## Configuration

Behaviour is tunable via environment variables (all read at startup):

| Variable                      | Default | Meaning                                            |
| ----------------------------- | ------- | -------------------------------------------------- |
| `WSU_WINGET_TIMEOUT`          | `120`   | Timeout (s) for `winget upgrade`.                  |
| `WSU_WINGET_SHOW_TIMEOUT`     | `20`    | Timeout (s) for `winget show` metadata lookups.    |
| `WSU_WINGET_OPTIONAL_FLAGS`   | `0`     | `1` adds `--accept-package-agreements` etc.        |
| `WSU_FILESIZE_SCAN`           | `1`     | `0` disables installer download-size lookups.      |
| `WSU_EXECUTABLE_SCAN`         | `0`     | `1` enables best-effort executable-path discovery. |
| `WSU_HTTP_PROBE_TIMEOUT`      | `6`     | Timeout (s) for installer size HTTP probes.        |

## State files

Three small JSON stores persist user choices under
`%LOCALAPPDATA%\WindowsSoftwareUpdater\`:

- `excluded_updates.json` — permanently excluded package ids.
- `skipped_updates.json` — `{package_id: skipped_version}`.
- `fake_updates.json` — packages winget reports but can no longer upgrade
  (recorded so they stop reappearing).

## Testing

```powershell
pip install -e ".[dev]"
pytest
ruff check .
mypy src
```

## License

MIT — see [LICENSE](LICENSE).
