"""Unit tests for MVP DoD check helpers (no DB)."""

from __future__ import annotations

from scripts.acceptance.dod_checks import check_restart_fingerprints


def test_restart_fingerprints_all_boundaries_equal() -> None:
    fp = {
        "RB-A": ("abc", "abc"),
        "RB-B": ("def", "def"),
        "RB-C": ("ghi", "ghi"),
        "RB-D": ("jkl", "jkl"),
    }
    check = check_restart_fingerprints(fp)
    assert check.ok is True


def test_restart_fingerprints_fail_on_mismatch() -> None:
    fp = {
        "RB-A": ("abc", "abc"),
        "RB-B": ("def", "xyz"),
        "RB-C": ("ghi", "ghi"),
        "RB-D": ("jkl", "jkl"),
    }
    check = check_restart_fingerprints(fp)
    assert check.ok is False
