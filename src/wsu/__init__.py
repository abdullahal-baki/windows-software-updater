"""Windows Software Updater (WSU).

A PyQt6 desktop application that wraps the Windows Package Manager (winget)
to scan for, apply, and manage software updates with a custom dark UI and
system-tray notifications.

The package is organised into layers:

* :mod:`wsu.core`     – framework-agnostic domain code (config, models,
  storage, paths, logging).
* :mod:`wsu.services` – the winget integration layer.
* :mod:`wsu.workers`  – Qt ``QObject`` workers that run blocking work off the
  GUI thread.
* :mod:`wsu.ui`       – all PyQt6 presentation code (theme, widgets, windows).
* :mod:`wsu.app`      – application entry points (the updater GUI and the
  background notifier).
"""

from __future__ import annotations

__all__ = ["__version__"]

__version__ = "1.0.0"
