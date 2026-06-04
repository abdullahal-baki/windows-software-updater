"""Reusable custom widgets used by the main window."""

from __future__ import annotations

from wsu.ui.widgets.empty_state import EmptyStateWidget
from wsu.ui.widgets.search_bar import SearchBar
from wsu.ui.widgets.status_chip import FooterProxy, StatusChip
from wsu.ui.widgets.title_bar import TitleBar
from wsu.ui.widgets.version_badge import VersionBadge
from wsu.ui.widgets.window_controls import WindowControlButton

__all__ = [
    "EmptyStateWidget",
    "SearchBar",
    "StatusChip",
    "FooterProxy",
    "TitleBar",
    "VersionBadge",
    "WindowControlButton",
]
