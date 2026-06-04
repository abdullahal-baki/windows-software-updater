"""Application configuration resolved from environment variables.

All tunables live here so that behaviour can be adjusted without touching
business logic. Every value is read once at import time; set the relevant
``WSU_*`` environment variable before launching to override a default.
"""

from __future__ import annotations

import os

# -- Application identity ---------------------------------------------------

APP_TITLE = "Windows Software Updater"
APP_SUBTITLE = "Powered by Windows Package Manager (winget)"

#: Folder name used under ``%LOCALAPPDATA%`` for persisted state.
APP_DATA_DIRNAME = "WindowsSoftwareUpdater"

#: Filename of the bundled application icon (looked up next to the executable).
ICON_FILENAME = "icon.ico"

#: Filename of the updater executable the notifier launches when clicked.
UPDATER_EXECUTABLE = "Updater.exe"


def _env_int(name: str, default: int) -> int:
    """Read an integer environment variable, falling back on parse errors."""
    try:
        return int(os.environ.get(name, str(default)))
    except (TypeError, ValueError):
        return default


def _env_flag(name: str, default: bool = False) -> bool:
    """Read a ``"1"``/``"0"`` style boolean environment variable."""
    return os.environ.get(name, "1" if default else "0") == "1"


# -- winget timeouts (seconds) ----------------------------------------------

WINGET_TIMEOUT_SECONDS = _env_int("WSU_WINGET_TIMEOUT", 120)
WINGET_SHOW_TIMEOUT_SECONDS = _env_int("WSU_WINGET_SHOW_TIMEOUT", 20)

# -- winget flags -----------------------------------------------------------

#: Flags always appended to winget invocations.
WINGET_REQUIRED_FLAGS = ["--accept-source-agreements"]

#: Optional flags appended only when ``WSU_WINGET_OPTIONAL_FLAGS=1``. Older
#: winget builds reject these; the service layer retries without them.
WINGET_OPTIONAL_FLAGS = (
    ["--accept-package-agreements", "--disable-interactivity"]
    if _env_flag("WSU_WINGET_OPTIONAL_FLAGS", False)
    else []
)

#: Substrings in winget output indicating it rejected an unknown argument,
#: which triggers a retry with only the required flags.
WINGET_UNKNOWN_ARG_TOKENS = (
    "unknown argument",
    "unrecognized option",
    "not recognized",
    "unknown option",
    "is not a valid option",
)

# -- Optional metadata scans ------------------------------------------------

#: When enabled, the scanner fetches installer download sizes (HTTP HEAD).
ENABLE_FILESIZE_SCAN = _env_flag("WSU_FILESIZE_SCAN", True)

#: When enabled, the scanner attempts to resolve each package's executable.
ENABLE_EXECUTABLE_SCAN = _env_flag("WSU_EXECUTABLE_SCAN", False)

#: HTTP timeout (seconds) for installer size HEAD/GET probes.
HTTP_PROBE_TIMEOUT_SECONDS = _env_int("WSU_HTTP_PROBE_TIMEOUT", 6)
