"""Worker that scans winget for available updates."""

from __future__ import annotations

import subprocess
from typing import Dict, List

from PyQt6.QtCore import QObject, pyqtSignal

from wsu.core.config import ENABLE_FILESIZE_SCAN
from wsu.core.models import UpdateItem
from wsu.services.winget import WingetService


class ScanWorker(QObject):
    """Scans for updates, honouring fake/excluded/skipped filters.

    The scan runs in two phases so the UI stays responsive:

    * **Phase 1** parses ``winget upgrade`` and emits :attr:`result` with the
      filtered update list immediately.
    * **Phase 2** fetches installer download sizes in the background and
      streams each one in via :attr:`size_ready`.

    Signals:
        result(list, dict, bool): updates, the (possibly pruned) skipped map,
            and whether that map changed and should be persisted.
        size_ready(str, float): ``(package_id, size_mb)`` as sizes resolve.
        error(str): a user-facing error message.
        finished(): emitted exactly once when the worker is done.
    """

    result = pyqtSignal(list, dict, bool)
    size_ready = pyqtSignal(str, float)
    error = pyqtSignal(str)
    finished = pyqtSignal()

    def __init__(
        self,
        fake_updates: Dict[str, str],
        excluded_updates: Dict[str, bool],
        skipped_updates: Dict[str, str],
    ) -> None:
        super().__init__()
        self.fake_updates = dict(fake_updates)
        self.excluded_updates = dict(excluded_updates)
        self.skipped_updates = dict(skipped_updates)

    def run(self) -> None:
        """Entry point connected to the thread's ``started`` signal."""
        skipped_changed = False
        updates: List[UpdateItem] = []
        try:
            entries = WingetService.list_upgrades()
            for name, package_id, installed_version, available_version in entries:
                if self._is_filtered(package_id, available_version):
                    continue
                skip_version = self.skipped_updates.get(package_id)
                if skip_version is not None and skip_version != available_version:
                    # A newer version superseded the skipped one; un-skip it.
                    self.skipped_updates.pop(package_id, None)
                    skipped_changed = True
                updates.append(
                    UpdateItem(
                        name=name,
                        package_id=package_id,
                        installed_version=installed_version,
                        available_version=available_version,
                    )
                )

            # Phase 1: emit immediately so the UI can render.
            self.result.emit(updates, self.skipped_updates, skipped_changed)

            # Phase 2: stream download sizes in the background.
            if ENABLE_FILESIZE_SCAN:
                for item in updates:
                    size = WingetService.get_file_size(item.package_id)
                    if size is not None:
                        self.size_ready.emit(item.package_id, size)
        except FileNotFoundError:
            self.error.emit(
                "winget not found. Please install Windows Package Manager."
            )
        except TimeoutError as exc:
            self.error.emit(str(exc))
        except subprocess.CalledProcessError as exc:
            self.error.emit(f"Error checking for updates: {exc.stderr}")
        finally:
            self.finished.emit()

    def _is_filtered(self, package_id: str, available_version: str) -> bool:
        """Return ``True`` if the package should be hidden from results."""
        if package_id in self.excluded_updates:
            return True
        if (
            package_id in self.fake_updates
            and self.fake_updates[package_id] == available_version
        ):
            return True
        if self.skipped_updates.get(package_id) == available_version:
            return True
        return False
