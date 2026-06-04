# Architecture

Windows Software Updater is organised as a layered Python package under
`src/wsu`. Each layer depends only on the layers beneath it, which keeps the
domain and integration code testable without a GUI and makes the UI easy to
retune in isolation.

```
        ┌──────────────────────────────────────────┐
        │  app/        entry points (updater, notifier)
        ├──────────────────────────────────────────┤
        │  ui/         theme, widgets, MainWindow     (PyQt6)
        ├──────────────────────────────────────────┤
        │  workers/    QThread workers (scan/update/exclusions)
        ├──────────────────────────────────────────┤
        │  services/   winget facade, process, parser
        ├──────────────────────────────────────────┤
        │  core/       config, paths, storage, models, logging
        └──────────────────────────────────────────┘
              (no PyQt6)            ↑ depends downward only
```

## Layers

### `core/` — domain & infrastructure (no Qt)

| Module              | Responsibility                                                        |
| ------------------- | --------------------------------------------------------------------- |
| `config.py`         | All tunables, resolved once from `WSU_*` environment variables.       |
| `models.py`         | `UpdateItem` dataclass — the single domain entity.                    |
| `paths.py`          | Resolves data/resource paths, with PyInstaller (`_MEIPASS`) awareness.|
| `storage.py`        | JSON load/save helpers (tolerant of missing/corrupt files).           |
| `logging_config.py` | Rotating file logger under the user data dir + console handler.       |

This layer imports no GUI code and is the target of the unit tests.

### `services/` — winget integration

| Module       | Responsibility                                                           |
| ------------ | ------------------------------------------------------------------------ |
| `process.py` | Low-level subprocess helpers: `run_command` and a char-streaming runner. |
| `parser.py`  | Parses winget's human-oriented `upgrade` table into typed tuples.        |
| `winget.py`  | `WingetService` facade: list upgrades, upgrade a package (with live progress), look up size/name/executable. |

This is the **only** layer that shells out to `winget`. Everything above it
deals in `UpdateItem`s and plain data.

### `workers/` — concurrency

Each worker is a `QObject` moved onto its own `QThread` so blocking
winget/network calls never freeze the GUI. Workers communicate purely through
Qt signals and never touch widgets.

- `ScanWorker` — two-phase scan: emit the parsed list immediately, then stream
  installer sizes in the background.
- `UpdateWorker` — upgrade packages sequentially, emitting live percent and
  per-item completion.
- `ExclusionsWorker` — resolve display names for excluded package ids.

### `ui/` — presentation

- `theme.py` — every colour token and the full Qt stylesheet in one place;
  `apply_dark_theme()` wires palette + font + QSS.
- `icons.py` — procedurally drawn logo (no image dependency).
- `widgets/` — small, reusable custom widgets (`TitleBar`, `SearchBar`,
  `VersionBadge`, `EmptyStateWidget`, `StatusChip`, `WindowControlButton`).
- `main_window.py` — `MainWindow`, which owns the state, builds the layout,
  and orchestrates workers. It is the one place where UI, workers, and the
  service layer meet.

### `app/` — entry points

- `updater.py` — `main()` builds the `QApplication`, applies the theme, shows
  `MainWindow`, runs the event loop.
- `notifier.py` — a one-shot tray notifier intended for scheduled execution.

Root-level `main.py` / `notifier.py` are thin compatibility shims that prepend
`src` to `sys.path` and delegate to `app/`, so the historical invocation and
the PyInstaller specs keep working.

## Key flows

### Scan

```
MainWindow.check_for_updates()
  → ScanWorker.run() on a QThread
      → WingetService.list_upgrades()           (winget upgrade + parse)
      → filter fake/excluded/skipped
      → emit result(updates, skipped, changed)  → MainWindow renders table
      → for each: WingetService.get_file_size() → emit size_ready → table cell
```

A `QTimer` watchdog guards against a hung winget call (`WINGET_TIMEOUT + 2s`).

### Update

```
MainWindow.start_update(ids)
  → UpdateWorker.run() on a QThread
      → for each id: WingetService.upgrade_package(on_progress=…)
            → stream_command parses live "NN%" → package_progress signal
      → item_complete / error / finished signals → MainWindow updates UI
```

Packages winget can no longer find are recorded in `fake_updates.json` so they
stop reappearing on subsequent scans.

## Design choices

- **Layer isolation.** `core` and `services` never import PyQt6, so the
  parsing/filtering logic is unit-tested headlessly.
- **Static `WingetService`.** winget owns all the state; instances would add
  nothing, so the methods are static and grouped for discoverability.
- **Signals over shared state.** Workers only emit signals; the main thread
  owns all widget mutation. This avoids cross-thread Qt access bugs.
- **One stylesheet.** Centralising QSS and colour tokens lets the visual
  identity change without touching widget logic.
