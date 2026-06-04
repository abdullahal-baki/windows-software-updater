"""Resolution of on-disk paths for persisted application data.

The resolver keeps backward compatibility with earlier versions that wrote
state files next to the executable or in the working directory, while
preferring a stable per-user location under ``%LOCALAPPDATA%``.
"""

from __future__ import annotations

import os
import sys

from wsu.core.config import APP_DATA_DIRNAME

# Filenames for the three persisted state stores.
FAKE_UPDATES_FILE = "fake_updates.json"
EXCLUDED_UPDATES_FILE = "excluded_updates.json"
SKIPPED_UPDATES_FILE = "skipped_updates.json"


def bundle_dir() -> str:
    """Return the directory of the running app.

    Works both from source and from a PyInstaller one-file build, where
    bundled resources are unpacked under ``sys._MEIPASS``.
    """
    meipass = getattr(sys, "_MEIPASS", None)
    if meipass:
        return meipass
    if getattr(sys, "frozen", False):
        return os.path.dirname(sys.executable)
    # Source layout: this file lives at src/wsu/core/paths.py; the project
    # root (where icon.ico and the executables live) is three levels up.
    return os.path.dirname(os.path.abspath(__file__))


def user_data_dir() -> str:
    """Return (creating if needed) the per-user data directory."""
    base = os.environ.get("LOCALAPPDATA") or os.environ.get("APPDATA")
    if not base:
        base = os.path.join(os.path.expanduser("~"), ".windows-software-updater")
    app_dir = os.path.join(base, APP_DATA_DIRNAME)
    os.makedirs(app_dir, exist_ok=True)
    return app_dir


def resolve_data_path(filename: str) -> str:
    """Resolve a stable data path with backward-compatible fallbacks.

    Preference order:

    1. ``<cwd>/<filename>`` if it already exists (legacy behaviour).
    2. ``<bundle_dir>/<filename>`` if it already exists (legacy behaviour).
    3. ``<user_data_dir>/<filename>`` (the canonical location for new files).
    """
    cwd_path = os.path.join(os.getcwd(), filename)
    local_path = os.path.join(bundle_dir(), filename)
    for candidate in (cwd_path, local_path):
        if os.path.exists(candidate):
            return candidate
    return os.path.join(user_data_dir(), filename)


def resource_path(filename: str) -> str:
    """Resolve a bundled, read-only resource (e.g. the application icon)."""
    return os.path.join(bundle_dir(), filename)
