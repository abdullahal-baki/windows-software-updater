"""Compatibility entry point for the Windows Software Updater GUI.

The application has been refactored into the :mod:`wsu` package under ``src``.
This thin shim keeps the historical ``python main.py`` invocation and the
existing PyInstaller build command working. New code should import from
``wsu`` directly.
"""

from __future__ import annotations

import os
import sys

# Ensure the ``src`` layout is importable when run directly from a checkout.
_SRC = os.path.join(os.path.dirname(os.path.abspath(__file__)), "src")
if _SRC not in sys.path:
    sys.path.insert(0, _SRC)

from wsu.app.updater import main  # noqa: E402

if __name__ == "__main__":
    main()
