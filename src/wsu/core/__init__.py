"""Framework-agnostic domain code for Windows Software Updater.

Nothing in this package imports PyQt6 — it can be unit-tested and reused
without a running GUI.
"""

from __future__ import annotations

from wsu.core.models import UpdateItem

__all__ = ["UpdateItem"]
