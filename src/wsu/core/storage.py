"""JSON-backed persistence for the application's small state stores."""

from __future__ import annotations

import json
import os
from typing import Dict


def load_json(path: str) -> Dict:
    """Load a JSON object from ``path``.

    Returns an empty dict when the file is missing, unreadable, or contains
    malformed JSON — the stores are caches, so a corrupt file is recoverable
    by simply starting over rather than crashing the app.
    """
    if os.path.exists(path):
        try:
            with open(path, "r", encoding="utf-8") as handle:
                return json.load(handle)
        except (json.JSONDecodeError, IOError):
            return {}
    return {}


def save_json(path: str, data: Dict) -> None:
    """Persist ``data`` as pretty-printed JSON to ``path``.

    Raises:
        IOError: if the file cannot be written. Callers that must not fail
            (e.g. the background notifier) should catch this.
    """
    try:
        with open(path, "w", encoding="utf-8") as handle:
            json.dump(data, handle, indent=4)
    except IOError as exc:
        raise IOError(f"Error saving JSON file '{path}': {exc}") from exc


def save_json_quiet(path: str, data: Dict) -> bool:
    """Persist ``data`` to ``path``, swallowing any error.

    Returns ``True`` on success and ``False`` on failure. Intended for
    fire-and-forget writes where surfacing an error is worse than skipping it.
    """
    try:
        save_json(path, data)
        return True
    except Exception:
        return False
