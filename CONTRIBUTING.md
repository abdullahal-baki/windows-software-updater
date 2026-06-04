# Contributing

Thanks for your interest in improving Windows Software Updater!

## Development setup

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -e ".[dev]"
```

Run the app from source:

```powershell
python -m wsu                 # GUI
python -m wsu.app.notifier    # notifier
```

## Before opening a PR

```powershell
ruff check .        # lint
ruff format .       # format
mypy src            # type-check
pytest              # tests
```

## Code conventions

- **Respect the layering** described in [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md):
  `core` and `services` must not import PyQt6; widgets must not shell out to
  winget directly — go through `WingetService`.
- **Workers emit signals only.** Never touch widgets from a worker thread.
- **One concern per module.** Prefer adding a focused module over growing an
  existing file past a few hundred lines.
- **Type hints** on public functions; module/class/function docstrings explain
  *why*, not just *what*.
- **No new runtime dependencies** without discussion — the appeal of this app
  is a small, self-contained footprint.

## Adding a setting

1. Add it to `src/wsu/core/config.py` (read from a `WSU_*` env var).
2. Document it in the README's configuration table.

## Releasing

See the release checklist in [docs/BUILD.md](docs/BUILD.md). Remember to bump
the version in `pyproject.toml`, `src/wsu/__init__.py`, and
`packaging/installer.iss` together.
