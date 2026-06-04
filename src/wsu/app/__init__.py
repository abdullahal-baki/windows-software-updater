"""Application entry points: the updater GUI and the background notifier."""

from __future__ import annotations

__all__ = ["run_updater", "run_notifier"]


def run_updater() -> None:
    """Launch the full updater GUI. See :func:`wsu.app.updater.main`."""
    from wsu.app.updater import main

    main()


def run_notifier() -> None:
    """Launch the background tray notifier. See :func:`wsu.app.notifier.main`."""
    from wsu.app.notifier import main

    main()
