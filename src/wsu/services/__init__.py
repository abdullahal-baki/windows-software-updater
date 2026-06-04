"""Integration with the Windows Package Manager (winget).

The service layer is the only place that shells out to ``winget``. It exposes
a small, typed surface so the rest of the app never deals with subprocess
plumbing or output parsing directly.
"""

from __future__ import annotations

from wsu.services.winget import WingetService

__all__ = ["WingetService"]
