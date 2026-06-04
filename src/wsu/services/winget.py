"""High-level winget facade used by the rest of the application."""

from __future__ import annotations

import os
import re
from typing import Callable, List, Optional, Tuple

import requests

from wsu.core.config import (
    ENABLE_EXECUTABLE_SCAN,
    ENABLE_FILESIZE_SCAN,
    HTTP_PROBE_TIMEOUT_SECONDS,
    WINGET_OPTIONAL_FLAGS,
    WINGET_REQUIRED_FLAGS,
    WINGET_SHOW_TIMEOUT_SECONDS,
    WINGET_UNKNOWN_ARG_TOKENS,
)
from wsu.core.logging_config import get_logger
from wsu.services.parser import UpgradeEntry, parse_upgrade_output
from wsu.services.process import run_command, stream_command

_log = get_logger("winget")

_INSTALLER_URL_RE = re.compile(r"Installer Url:\s*(https?://[^\s]+)", re.IGNORECASE)
_INSTALL_LOCATION_RE = re.compile(r"Install Location:\s*(.*?)\n", re.IGNORECASE)
_SHOW_NAME_RE = re.compile(r"^Name:\s*(.+)$", re.IGNORECASE | re.MULTILINE)


class WingetService:
    """Stateless facade over the ``winget`` CLI.

    Methods are static because winget itself holds all state; instances would
    add nothing. The class grouping keeps the winget surface discoverable.
    """

    # -- command execution --------------------------------------------------

    @staticmethod
    def run_winget(args: List[str]) -> "object":
        """Run a winget command with the configured flags.

        If winget rejects an optional flag (older builds), the command is
        retried with only the required flags.

        Returns:
            The ``subprocess.CompletedProcess`` from the (final) invocation.
        """
        full_args = list(args) + WINGET_REQUIRED_FLAGS + WINGET_OPTIONAL_FLAGS
        result = run_command(full_args)
        if result.returncode != 0:
            combined = f"{result.stdout} {result.stderr}".lower()
            if any(token in combined for token in WINGET_UNKNOWN_ARG_TOKENS):
                result = run_command(list(args) + WINGET_REQUIRED_FLAGS)
        return result

    @staticmethod
    def upgrade_package(
        package_id: str, on_progress: Optional[Callable[[int], None]] = None
    ) -> Tuple[int, str]:
        """Upgrade a single package, streaming download/install percent.

        Args:
            package_id: The winget package identifier to upgrade.
            on_progress: Optional callback receiving integer percentages
                (0-100) parsed live from winget's progress line.

        Returns:
            ``(returncode, combined_output_lowercased)`` from the invocation
            that actually ran (after any flag-rejection retry).
        """
        pct_re = re.compile(r"(\d{1,3})\s*%")
        last_pct = [-1]

        def _handle_line(line: str) -> None:
            if on_progress is None:
                return
            match = pct_re.search(line)
            if match:
                pct = max(0, min(100, int(match.group(1))))
                if pct != last_pct[0]:
                    last_pct[0] = pct
                    on_progress(pct)

        base = ["winget", "upgrade", package_id]
        returncode, combined = stream_command(
            base + WINGET_REQUIRED_FLAGS + WINGET_OPTIONAL_FLAGS, _handle_line
        )
        if returncode != 0 and any(t in combined for t in WINGET_UNKNOWN_ARG_TOKENS):
            returncode, combined = stream_command(
                base + WINGET_REQUIRED_FLAGS, _handle_line
            )
        return returncode, combined

    # -- queries ------------------------------------------------------------

    @staticmethod
    def list_upgrades() -> List[UpgradeEntry]:
        """Return all upgradable packages reported by ``winget upgrade``."""
        result = WingetService.run_winget(["winget", "upgrade"])
        return parse_upgrade_output(getattr(result, "stdout", "") or "")

    @staticmethod
    def get_file_size(package_id: str) -> Optional[float]:
        """Return the installer download size in MB, or ``None`` if unknown.

        Resolves the installer URL via ``winget show`` and probes it with an
        HTTP HEAD (falling back to a streamed GET). Disabled entirely when
        :data:`ENABLE_FILESIZE_SCAN` is false.
        """
        if not ENABLE_FILESIZE_SCAN:
            return None
        try:
            result = run_command(
                ["winget", "show", package_id], timeout=WINGET_SHOW_TIMEOUT_SECONDS
            )
            match = _INSTALLER_URL_RE.search(result.stdout or "")
            if not match:
                return None
            link = match.group(1)
            try:
                response = requests.head(
                    link, allow_redirects=True, timeout=HTTP_PROBE_TIMEOUT_SECONDS
                )
                if "Content-Length" not in response.headers:
                    response = requests.get(
                        link, stream=True, timeout=HTTP_PROBE_TIMEOUT_SECONDS
                    )
                size_bytes = int(response.headers.get("Content-Length", 0))
                if size_bytes <= 0:
                    return None
                return round(size_bytes / (1024 * 1024), 2)
            except Exception:
                return None
        except Exception:
            _log.debug("file size lookup failed for %s", package_id, exc_info=True)
            return None

    @staticmethod
    def get_executable_path(package_id: str, package_name: str) -> Optional[str]:
        """Best-effort resolution of a package's main executable path.

        Disabled unless :data:`ENABLE_EXECUTABLE_SCAN` is true.
        """
        if not ENABLE_EXECUTABLE_SCAN:
            return None
        try:
            result = run_command(
                ["winget", "show", "--id", package_id, "--exact"],
                timeout=WINGET_SHOW_TIMEOUT_SECONDS,
            )
            match = _INSTALL_LOCATION_RE.search(result.stdout or "")
            if not match:
                return None
            install_path = match.group(1).strip()
            if not install_path or not os.path.exists(install_path):
                return None
            for root_dir, _, files in os.walk(install_path):
                for file in files:
                    if file.lower().endswith(".exe") and (
                        package_name.lower() in file.lower()
                        or package_id.lower() in file.lower()
                    ):
                        return os.path.join(root_dir, file)
        except Exception:
            _log.debug("executable lookup failed for %s", package_id, exc_info=True)
            return None
        return None

    @staticmethod
    def resolve_package_name(package_id: str) -> str:
        """Resolve a human-readable name for ``package_id``.

        Tries ``winget search`` first, then ``winget show``; falls back to the
        identifier itself when neither yields a name.
        """
        try:
            search_result = run_command(
                ["winget", "search", "--id", package_id, "--exact"]
            )
            for line in (search_result.stdout or "").splitlines():
                if package_id in line and not line.strip().startswith(("Name", "--")):
                    match = re.match(
                        rf"^(.*?)\s{{2,}}{re.escape(package_id)}(\s|$)", line
                    )
                    if match:
                        candidate = match.group(1).strip()
                        if candidate:
                            return candidate
            show_result = run_command(
                ["winget", "show", "--id", package_id, "--exact"]
            )
            match = _SHOW_NAME_RE.search(show_result.stdout or "")
            if match:
                return match.group(1).strip()
        except Exception:
            _log.debug("name resolution failed for %s", package_id, exc_info=True)
        return package_id
