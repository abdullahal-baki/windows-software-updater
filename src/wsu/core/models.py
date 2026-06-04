"""Domain models shared across the application."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional


@dataclass
class UpdateItem:
    """A single upgradable package as reported by winget.

    Attributes:
        name: Human-readable application name (e.g. ``"Mozilla Firefox"``).
        package_id: winget package identifier (e.g. ``"Mozilla.Firefox"``).
        installed_version: Currently installed version string.
        available_version: Version winget reports as available.
        file_size: Installer download size in MB, or ``None`` if unknown or
            not yet fetched (size lookups happen asynchronously).
        executable_path: Resolved path to the package's main executable, when
            the optional executable scan is enabled.
    """

    name: str
    package_id: str
    installed_version: str
    available_version: str
    file_size: Optional[float] = None
    executable_path: Optional[str] = None
