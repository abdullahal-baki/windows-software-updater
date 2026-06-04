"""Low-level subprocess helpers for invoking command-line tools on Windows.

These helpers always suppress the console window (so the GUI build never
flashes a black box) and normalise text decoding.
"""

from __future__ import annotations

import subprocess
from typing import Callable, List, Optional, Tuple

from wsu.core.config import WINGET_TIMEOUT_SECONDS


def _hidden_startupinfo() -> "subprocess.STARTUPINFO":
    """Build a STARTUPINFO that hides the spawned process's console window."""
    startupinfo = subprocess.STARTUPINFO()
    startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
    return startupinfo


def run_command(
    args: List[str], timeout: Optional[int] = None
) -> subprocess.CompletedProcess:
    """Run ``args`` to completion, capturing stdout/stderr as text.

    Args:
        args: The command and its arguments.
        timeout: Seconds to wait before giving up; defaults to the configured
            winget timeout.

    Returns:
        The completed process, with decoded ``stdout``/``stderr``.

    Raises:
        TimeoutError: if the process does not finish within ``timeout``.
        FileNotFoundError: if the executable cannot be found.
    """
    if timeout is None:
        timeout = WINGET_TIMEOUT_SECONDS
    try:
        return subprocess.run(
            args,
            startupinfo=_hidden_startupinfo(),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout,
        )
    except subprocess.TimeoutExpired as exc:
        raise TimeoutError(f"winget timed out after {timeout} seconds") from exc


def stream_command(
    args: List[str], on_line: Optional[Callable[[str], None]] = None
) -> Tuple[int, str]:
    """Run ``args`` while streaming output line by line.

    winget repaints progress on a single line using carriage returns, so this
    reads one character at a time and treats both ``\\r`` and ``\\n`` as line
    boundaries, invoking ``on_line`` for each completed segment.

    Args:
        args: The command and its arguments.
        on_line: Optional callback invoked with each non-empty output segment
            (already stripped of surrounding whitespace control characters).

    Returns:
        A tuple of ``(returncode, combined_output_lowercased)``.
    """
    proc = subprocess.Popen(
        args,
        startupinfo=_hidden_startupinfo(),
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    collected: List[str] = []
    token = ""
    assert proc.stdout is not None
    while True:
        ch = proc.stdout.read(1)
        if not ch:
            break
        if ch in ("\r", "\n"):
            if token.strip():
                collected.append(token)
                if on_line is not None:
                    on_line(token)
            token = ""
        else:
            token += ch
    if token.strip():
        collected.append(token)
        if on_line is not None:
            on_line(token)
    proc.wait()
    return proc.returncode, " ".join(collected).lower()
