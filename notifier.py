"""Compatibility entry point for the background update notifier.

The notifier now lives in :mod:`wsu.app.notifier`. This shim preserves the
``python notifier.py`` invocation and the existing PyInstaller build command.
"""

from __future__ import annotations

import os
import sys

_SRC = os.path.join(os.path.dirname(os.path.abspath(__file__)), "src")
if _SRC not in sys.path:
    sys.path.insert(0, _SRC)

from wsu.app.notifier import main  # noqa: E402

if __name__ == "__main__":
    main()
