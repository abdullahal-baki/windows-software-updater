"""Worker that resolves human-readable names for excluded packages."""

from __future__ import annotations

from typing import List, Tuple

from PyQt6.QtCore import QObject, pyqtSignal

from wsu.services.winget import WingetService


class ExclusionsWorker(QObject):
    """Resolves display names for the set of excluded package identifiers.

    Name resolution shells out to winget per package, so it runs off the GUI
    thread to keep the exclusions view responsive.

    Signals:
        result(list): a list of ``(package_id, display_name)`` tuples.
        finished(): emitted once when resolution completes.
    """

    result = pyqtSignal(list)
    finished = pyqtSignal()

    def __init__(self, excluded_ids: List[str]) -> None:
        super().__init__()
        self.excluded_ids = list(excluded_ids)

    def run(self) -> None:
        """Entry point connected to the thread's ``started`` signal."""
        entries: List[Tuple[str, str]] = [
            (pid, WingetService.resolve_package_name(pid)) for pid in self.excluded_ids
        ]
        self.result.emit(entries)
        self.finished.emit()
