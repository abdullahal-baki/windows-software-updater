"""Tests for the JSON storage helpers."""

from __future__ import annotations

import os

from wsu.core.storage import load_json, save_json, save_json_quiet


def test_round_trip(tmp_path) -> None:
    path = os.path.join(tmp_path, "data.json")
    data = {"Pkg.Id": "1.2.3", "Other.Id": "4.5.6"}
    save_json(path, data)
    assert load_json(path) == data


def test_missing_file_returns_empty_dict(tmp_path) -> None:
    assert load_json(os.path.join(tmp_path, "nope.json")) == {}


def test_corrupt_file_returns_empty_dict(tmp_path) -> None:
    path = os.path.join(tmp_path, "bad.json")
    with open(path, "w", encoding="utf-8") as handle:
        handle.write("{ not valid json ")
    assert load_json(path) == {}


def test_save_json_quiet_reports_failure() -> None:
    # An unwritable path (directory that does not exist) must not raise.
    assert save_json_quiet("/this/path/should/not/exist/x.json", {"a": 1}) is False
