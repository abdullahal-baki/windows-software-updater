"""
Update notifier using Qt system tray notifications.

Checks winget for updates, respects fake/excluded/skipped entries, and
shows a toast notification that can launch the updater app.
"""

import json
import os
import re
import subprocess
import sys
from typing import Dict, List, Optional

from PyQt6.QtCore import QTimer
from PyQt6.QtGui import QIcon
from PyQt6.QtWidgets import QApplication, QSystemTrayIcon

WINGET_TIMEOUT_SECONDS = int(os.environ.get("WSU_WINGET_TIMEOUT", "120"))
WINGET_REQUIRED_FLAGS = ["--accept-source-agreements"]
WINGET_OPTIONAL_FLAGS = []
if os.environ.get("WSU_WINGET_OPTIONAL_FLAGS", "0") == "1":
    WINGET_OPTIONAL_FLAGS = ["--accept-package-agreements", "--disable-interactivity"]


def resolve_data_path(filename: str) -> str:
    cwd_path = os.path.join(os.getcwd(), filename)
    local_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), filename)
    for candidate in (cwd_path, local_path):
        if os.path.exists(candidate):
            return candidate
    base = os.environ.get("LOCALAPPDATA") or os.environ.get("APPDATA")
    if not base:
        base = os.path.join(os.path.expanduser("~"), ".windows-software-updater")
    app_dir = os.path.join(base, "WindowsSoftwareUpdater")
    os.makedirs(app_dir, exist_ok=True)
    return os.path.join(app_dir, filename)


def load_json(path: str) -> Dict:
    if os.path.exists(path):
        try:
            with open(path, "r", encoding="utf-8") as handle:
                return json.load(handle)
        except (json.JSONDecodeError, IOError):
            return {}
    return {}


def save_json(path: str, data: Dict) -> None:
    try:
        with open(path, "w", encoding="utf-8") as handle:
            json.dump(data, handle, indent=4)
    except Exception:
        pass


def run_command_silently(command: List[str], timeout: Optional[int] = None) -> subprocess.CompletedProcess:
    startupinfo = subprocess.STARTUPINFO()
    startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
    if timeout is None:
        timeout = WINGET_TIMEOUT_SECONDS
    try:
        return subprocess.run(
            command,
            startupinfo=startupinfo,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=timeout,
        )
    except subprocess.TimeoutExpired as exc:
        raise TimeoutError(f"winget timed out after {timeout} seconds") from exc


def run_winget(args: List[str]) -> subprocess.CompletedProcess:
    full_args = args + WINGET_REQUIRED_FLAGS + WINGET_OPTIONAL_FLAGS
    result = run_command_silently(full_args)
    if result.returncode != 0:
        combined = f"{result.stdout} {result.stderr}".lower()
        unknown_tokens = (
            "unknown argument",
            "unrecognized option",
            "not recognized",
            "unknown option",
            "is not a valid option",
        )
        if any(token in combined for token in unknown_tokens):
            result = run_command_silently(args + WINGET_REQUIRED_FLAGS)
    return result


def parse_upgrade_output(output: str) -> List[List[str]]:
    lines = output.splitlines()
    start_index = 0
    for i, line in enumerate(lines):
        if line.startswith("Name") and "Id" in line:
            start_index = i + 1
            break
    entries: List[List[str]] = []
    for line in lines[start_index:]:
        if not line.strip() or line.strip().startswith("-"):
            continue
        cleaned = line.replace("winget", "").strip()
        pattern = r"^(.*?)\s+([^\s]+)\s+([^\s]+\s*(?:\([^\)]+\))?)\s+([^\s]+\s*(?:\([^\)]+\))?)$"
        match = re.match(pattern, cleaned)
        if match:
            entries.append([match.group(1), match.group(2), match.group(3), match.group(4)])
        else:
            parts = re.split(r"\s{2,}", cleaned)
            if len(parts) >= 4:
                entries.append(parts)
    return entries


class UpdateNotifier:
    def __init__(self) -> None:
        self.app = QApplication.instance() or QApplication(sys.argv)

        self.fake_updates_file = resolve_data_path("fake_updates.json")
        self.excluded_updates_file = resolve_data_path("excluded_updates.json")
        self.skipped_updates_file = resolve_data_path("skipped_updates.json")
        self.fake_updates: Dict[str, str] = load_json(self.fake_updates_file)
        self.excluded_updates: Dict[str, bool] = load_json(self.excluded_updates_file)
        self.skipped_updates: Dict[str, str] = load_json(self.skipped_updates_file)

        base_path = os.path.dirname(os.path.abspath(__file__))
        icon_path = os.path.join(base_path, "icon.ico")
        self.icon = QIcon(icon_path) if os.path.exists(icon_path) else QIcon()
        self.updater_path = os.path.join(base_path, "Updater.exe")

        if not QSystemTrayIcon.isSystemTrayAvailable():
            QTimer.singleShot(200, self.app.quit)
            return

        self.tray = QSystemTrayIcon(self.icon)
        self.tray.messageClicked.connect(self._launch_updater)
        self.tray.show()
        self.check_for_updates()

    def _launch_updater(self) -> None:
        if os.path.exists(self.updater_path):
            os.startfile(self.updater_path)

    def show_notification(self, count: int) -> None:
        plural = "s" if count != 1 else ""
        self.tray.showMessage(
            f"{count} Software Update{plural} Available",
            "Open Software Updater to install new versions.",
            QSystemTrayIcon.MessageIcon.Information,
            7000,
        )

    def check_for_updates(self) -> None:
        try:
            result = run_winget(["winget", "upgrade"])
            entries = parse_upgrade_output(result.stdout or "")
            updates = []
            skipped_changed = False
            for parts in entries:
                name, package_id, installed_version, available_version = parts[:4]
                if (package_id in self.fake_updates and self.fake_updates[package_id] == available_version) or (
                    package_id in self.excluded_updates
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
                save_json(self.skipped_updates_file, self.skipped_updates)
            if updates:
                self.show_notification(len(updates))
                QTimer.singleShot(8000, self.app.quit)
            else:
                QTimer.singleShot(1200, self.app.quit)
        except (subprocess.CalledProcessError, FileNotFoundError, TimeoutError):
            QTimer.singleShot(1200, self.app.quit)


def main() -> None:
    notifier = UpdateNotifier()
    if QApplication.instance():
        sys.exit(QApplication.instance().exec())


if __name__ == "__main__":
    main()
