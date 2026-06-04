"""Worker that applies updates to one or more packages."""

from __future__ import annotations

from typing import Dict, List

from PyQt6.QtCore import QObject, pyqtSignal

from wsu.core.models import UpdateItem
from wsu.services.winget import WingetService


class UpdateWorker(QObject):
    """Upgrades a list of packages sequentially, reporting live progress.

    Signals:
        progress(int, int, str): ``(index, total, package_id)`` after each
            package completes.
        package_progress(str, int): ``(package_id, percent)`` live download /
            install percent for the current package.
        item_complete(str, bool, bool, str): ``(package_id, success,
            is_phantom, message)``. ``is_phantom`` flags a package winget no
            longer finds installed, which is recorded as a "fake" update so it
            stops reappearing.
        error(str): a user-facing error message; the run stops after emitting.
        finished(bool): ``True`` if the whole batch succeeded.
    """

    progress = pyqtSignal(int, int, str)
    package_progress = pyqtSignal(str, int)
    item_complete = pyqtSignal(str, bool, bool, str)
    error = pyqtSignal(str)
    finished = pyqtSignal(bool)

    def __init__(
        self, package_ids: List[str], updates_by_id: Dict[str, UpdateItem]
    ) -> None:
        super().__init__()
        self.package_ids = list(package_ids)
        self.updates_by_id = dict(updates_by_id)

    def run(self) -> None:
        """Entry point connected to the thread's ``started`` signal."""
        total = len(self.package_ids)
        try:
            for index, package_id in enumerate(self.package_ids, start=1):
                self.package_progress.emit(package_id, 0)
                returncode, combined = WingetService.upgrade_package(
                    package_id,
                    on_progress=lambda pct, pid=package_id: self.package_progress.emit(
                        pid, pct
                    ),
                )
                if returncode == 0 or "successfully upgraded" in combined:
                    self.package_progress.emit(package_id, 100)
                    self.item_complete.emit(package_id, True, False, "")
                elif "no package found" in combined or "not installed" in combined:
                    self.item_complete.emit(package_id, False, True, "")
                else:
                    message = combined.strip() or "Unknown error occurred"
                    self.error.emit(f"Error updating {package_id}: {message}")
                    self.finished.emit(False)
                    return
                self.progress.emit(index, total, package_id)
            self.finished.emit(True)
        except FileNotFoundError:
            self.error.emit(
                "winget not found. Please install Windows Package Manager."
            )
            self.finished.emit(False)
        except TimeoutError as exc:
            self.error.emit(str(exc))
            self.finished.emit(False)
        except Exception as exc:  # noqa: BLE001 - surface any failure to the UI
            self.error.emit(f"Unexpected error: {exc}")
            self.finished.emit(False)
