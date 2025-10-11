"""
Update notifier that uses Windows toast notifications to alert the user
when software updates are available via winget.

This script wraps ``winget upgrade`` in a lightweight class which
parses the output, honours both "fake" and "excluded" updates, and
displays a clickable toast.  Fake updates are updates reported by
winget that cannot actually be applied (perhaps because the package
isn't installed); these are persisted in a JSON file and ignored on
subsequent runs.  Excluded updates are packages that the user has
chosen to permanently ignore; these are also persisted in a JSON file
and never counted towards the notification.

To configure the file locations and icons, adjust the class
attributes ``fake_updates_file`` and ``excluded_updates_file`` or pass
your own paths when constructing ``UpdateNotifier``.
"""

import json
import os
import re
import subprocess
import sys
from typing import Dict, List

from win10toast_click import ToastNotifier


class UpdateNotifier:
    """Checks for pending software updates and shows a toast notification."""

    def __init__(self) -> None:
        # Initialise variables
        self.updates: List[Dict[str, str]] = []
        # Path to JSON file recording fake updates
        self.fake_updates_file = (
            r"C:\Users\Alamin\OneDrive\github\windows-software-updater\dist\fake_updates.json"
        )
        # Path to JSON file recording excluded updates
        self.excluded_updates_file = (
            r"C:\Users\Alamin\OneDrive\github\windows-software-updater\dist\excluded_updates.json"
        )
        self.fake_updates: Dict[str, str] = self._load_json(self.fake_updates_file)
        self.excluded_updates: Dict[str, bool] = self._load_json(
            self.excluded_updates_file
        )

        # Resolve icon and updater paths relative to the bundle when frozen
        base_path = getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__)))
        self.icon_path = os.path.join(base_path, "icon.ico")
        self.updater_path = (
            r"C:\Users\Alamin\OneDrive\github\windows-software-updater\dist\Updater.exe"
        )

        self.toaster = ToastNotifier()

        # Check for updates on startup
        self.check_for_updates()

    # ------------------------------------------------------------------
    # JSON helpers
    # ------------------------------------------------------------------
    @staticmethod
    def _load_json(path: str) -> Dict:
        """Load a JSON file from disk and return an empty dict on error."""
        if os.path.exists(path):
            try:
                with open(path, "r", encoding="utf-8") as f:
                    return json.load(f)
            except (json.JSONDecodeError, IOError):
                return {}
        return {}

    # ------------------------------------------------------------------
    # Updater launcher
    # ------------------------------------------------------------------
    def _launch_updater(self) -> None:
        """Launch the GUI updater application when the toast is clicked."""
        if os.path.exists(self.updater_path):
            os.startfile(self.updater_path)

    def show_notification(self, count: int) -> None:
        """Show a toast informing the user about pending updates."""
        plural = "s" if count != 1 else ""
        self.toaster.show_toast(
            f"{count} Software Update{plural} Available!",
            "Open Software Updater app to install new versions.",
            icon_path=self.icon_path,
            duration=5,
            threaded=True,
            callback_on_click=self._launch_updater,
        )

    # ------------------------------------------------------------------
    # Core functionality
    # ------------------------------------------------------------------
    def check_for_updates(self) -> None:
        """Check for available software updates via winget."""

        def run_command_silently(command: List[str]) -> subprocess.CompletedProcess:
            startupinfo = subprocess.STARTUPINFO()
            startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
            return subprocess.run(
                command,
                startupinfo=startupinfo,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            )

        try:
            result = run_command_silently(["winget", "upgrade", "--accept-source-agreements"])
            lines = result.stdout.split("\n")
            start_index = 0
            for i, line in enumerate(lines):
                if line.startswith("Name") and "Id" in line:
                    start_index = i + 1
                    break
            lines = lines[start_index:]
            self.updates = []
            count = 0
            for line in lines:
                # Skip empty and header lines
                if line.strip() and not line.startswith("-"):
                    # Remove stray 'winget' tokens from the line
                    line = line.replace("winget", "")
                    pattern = r"^(.*?)\s+([^\s]+)\s+([^\s]+\s*(?:\([^\)]+\))?)\s+([^\s]+\s*(?:\([^\)]+\))?)$"
                    match = re.match(pattern, line.strip())
                    parts: List[str] = []
                    if match:
                        parts = [
                            match.group(1).strip(),
                            match.group(2).strip(),
                            match.group(3).strip(),
                            match.group(4).strip(),
                        ]
                    if len(parts) >= 4:
                        name, package_id, installed_version, available_version = parts
                        # Skip fake or excluded packages entirely
                        if (
                            package_id in self.fake_updates
                            and self.fake_updates[package_id] == available_version
                        ) or (package_id in self.excluded_updates):
                            continue
                        # Otherwise include in updates list
                        self.updates.append(
                            {
                                "name": name,
                                "id": package_id,
                                "installed_version": installed_version,
                                "available_version": available_version,
                            }
                        )
                        count += 1
            # Only show notification if there are pending updates
            if count:
                self.show_notification(count)
        except subprocess.CalledProcessError:
            # Winget not found or another non‑zero return; silently ignore
            pass


if __name__ == "__main__":
    app = UpdateNotifier()
