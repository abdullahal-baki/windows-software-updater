"""Parsing of winget's human-oriented table output.

winget has no stable machine-readable output for ``winget upgrade``, so we
parse the fixed-width / multi-space columns defensively, with a regex first
and a column-split fallback.
"""

from __future__ import annotations

import re
from typing import List, Tuple

# (Name, Id, InstalledVersion, AvailableVersion)
UpgradeEntry = Tuple[str, str, str, str]

# Matches: name, id, installed version, available version. Versions may carry
# a trailing parenthetical note, e.g. "1.2.3 (preview)".
_ROW_PATTERN = re.compile(
    r"^(.*?)\s+([^\s]+)\s+([^\s]+\s*(?:\([^\)]+\))?)\s+([^\s]+\s*(?:\([^\)]+\))?)$"
)


def parse_upgrade_output(output: str) -> List[UpgradeEntry]:
    """Parse ``winget upgrade`` output into structured rows.

    The header row (``Name  Id  Version  Available ...``) and the dashed
    separator beneath it are skipped, along with winget's own self-update
    footer noise.

    Args:
        output: The raw stdout from ``winget upgrade``.

    Returns:
        A list of ``(name, package_id, installed_version, available_version)``
        tuples. Rows that cannot be parsed into four columns are dropped.
    """
    lines = output.splitlines()
    start_index = 0
    for i, line in enumerate(lines):
        if line.startswith("Name") and "Id" in line:
            start_index = i + 1
            break

    entries: List[UpgradeEntry] = []
    for line in lines[start_index:]:
        if not line.strip() or line.strip().startswith("-"):
            continue
        cleaned = line.replace("winget", "").strip()
        match = _ROW_PATTERN.match(cleaned)
        if match:
            entries.append(
                (
                    match.group(1).strip(),
                    match.group(2).strip(),
                    match.group(3).strip(),
                    match.group(4).strip(),
                )
            )
            continue
        parts = re.split(r"\s{2,}", cleaned)
        if len(parts) >= 4:
            entries.append(
                (parts[0].strip(), parts[1].strip(), parts[2].strip(), parts[3].strip())
            )
    return entries
