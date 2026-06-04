"""Background tray notifier.

Intended to run on a schedule (e.g. a Windows Task Scheduler job). It checks
winget for updates — honouring the same fake/excluded/skipped filters as the
GUI — and, if any are pending, shows a tray notification that launches the
updater when clicked. The process exits shortly afterwards.
"""

from __future__ import annotations

import os
import sys
from typing import Dict, List

from PyQt6.QtCore import QTimer
from PyQt6.QtGui import QIcon
from PyQt6.QtWidgets import QApplication, QSystemTrayIcon

from wsu.core.config import ICON_FILENAME, UPDATER_EXECUTABLE
from wsu.core.logging_config import configure_logging, get_logger
from wsu.core.paths import (
    EXCLUDED_UPDATES_FILE,
    FAKE_UPDATES_FILE,
    SKIPPED_UPDATES_FILE,
    resolve_data_path,
    resource_path,
)
from wsu.core.storage import load_json, save_json_quiet
from wsu.services.winget import WingetService

_log = get_logger("notifier")

# How long the process lingers (ms) so the toast can be seen / clicked.
_LINGER_WITH_UPDATES_MS = 8000
_LINGER_NO_UPDATES_MS = 1200


class UpdateNotifier:
    """Performs a single update check and shows a tray toast if needed."""

    def __init__(self) -> None:
        self.app = QApplication.instance() or QApplication(sys.argv)

        self.fake_updates_file = resolve_data_path(FAKE_UPDATES_FILE)
        self.excluded_updates_file = resolve_data_path(EXCLUDED_UPDATES_FILE)
        self.skipped_updates_file = resolve_data_path(SKIPPED_UPDATES_FILE)
        self.fake_updates: Dict[str, str] = load_json(self.fake_updates_file)
        self.excluded_updates: Dict[str, bool] = load_json(self.excluded_updates_file)
        self.skipped_updates: Dict[str, str] = load_json(self.skipped_updates_file)

        icon_path = resource_path(ICON_FILENAME)
        self.icon = QIcon(icon_path) if os.path.exists(icon_path) else QIcon()
        self.updater_path = resource_path(UPDATER_EXECUTABLE)

        if not QSystemTrayIcon.isSystemTrayAvailable():
            QTimer.singleShot(200, self.app.quit)
            return

        self.tray = QSystemTrayIcon(self.icon)
        self.tray.messageClicked.connect(self._launch_updater)
        self.tray.show()
        self.check_for_updates()

    def _launch_updater(self) -> None:
        if os.path.exists(self.updater_path):
            os.startfile(self.updater_path)  # noqa: S606 - launching our own exe

    def show_notification(self, count: int) -> None:
        """Show a tray toast announcing ``count`` available updates."""
        plural = "s" if count != 1 else ""
        self.tray.showMessage(
            f"{count} Software Update{plural} Available",
            "Open Software Updater to install new versions.",
            QSystemTrayIcon.MessageIcon.Information,
            7000,
        )

    def check_for_updates(self) -> None:
        """Check winget, notify if updates exist, then schedule a quit."""
        try:
            entries = WingetService.list_upgrades()
            updates: List[str] = []
            skipped_changed = False
            for name, package_id, installed_version, available_version in entries:
                if package_id in self.excluded_updates:
                    continue
                if (
                    package_id in self.fake_updates
                    and self.fake_updates[package_id] == available_version
                ):
                    continue
                skip_version = self.skipped_updates.get(package_id)
                if skip_version == available_version:
                    continue
                if skip_version is not None and skip_version != available_version:
                    self.skipped_updates.pop(package_id, None)
                    skipped_changed = True
                updates.append(package_id)

            if skipped_changed:
                save_json_quiet(self.skipped_updates_file, self.skipped_updates)

            if updates:
                self.show_notification(len(updates))
                QTimer.singleShot(_LINGER_WITH_UPDATES_MS, self.app.quit)
            else:
                QTimer.singleShot(_LINGER_NO_UPDATES_MS, self.app.quit)
        except (FileNotFoundError, TimeoutError) as exc:
            _log.warning("notifier update check failed: %s", exc)
            QTimer.singleShot(_LINGER_NO_UPDATES_MS, self.app.quit)
        except Exception:  # noqa: BLE001 - never let the notifier crash loudly
            _log.exception("unexpected notifier error")
            QTimer.singleShot(_LINGER_NO_UPDATES_MS, self.app.quit)


def main() -> None:
    """Run a single notification check and exit."""
    configure_logging()
    UpdateNotifier()
    instance = QApplication.instance()
    if instance is not None:
        sys.exit(instance.exec())


if __name__ == "__main__":
    main()
