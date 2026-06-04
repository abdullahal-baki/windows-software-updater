"""Tests for winget upgrade-output parsing."""

from __future__ import annotations

from wsu.services.parser import parse_upgrade_output

SAMPLE = """\
Name                     Id                       Version       Available
-------------------------------------------------------------------------
Mozilla Firefox          Mozilla.Firefox          124.0         125.0
7-Zip                    7zip.7zip                22.01         23.01
Microsoft Edge           Microsoft.Edge           124.0.1 (x64) 125.0.2 (x64)
"""


def test_parses_all_rows() -> None:
    entries = parse_upgrade_output(SAMPLE)
    assert len(entries) == 3


def test_extracts_columns() -> None:
    entries = parse_upgrade_output(SAMPLE)
    name, package_id, installed, available = entries[0]
    assert name == "Mozilla Firefox"
    assert package_id == "Mozilla.Firefox"
    assert installed == "124.0"
    assert available == "125.0"


def test_handles_versions_with_parenthetical_notes() -> None:
    entries = parse_upgrade_output(SAMPLE)
    _, package_id, installed, available = entries[2]
    assert package_id == "Microsoft.Edge"
    assert "124.0.1" in installed
    assert "125.0.2" in available


def test_empty_output_yields_no_entries() -> None:
    assert parse_upgrade_output("") == []
    assert parse_upgrade_output("no header here\njust noise") == []
