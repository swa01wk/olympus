"""SupportDesk fixture must pass merge-time integration checks."""

from __future__ import annotations

from pathlib import Path

from core.integration.checks import run_integration_checks

_SUPPORTDESK = Path(__file__).resolve().parents[2] / "fixtures" / "repos" / "supportdesk_r1"


def test_supportdesk_fixture_passes_integration_checks() -> None:
    result = run_integration_checks(_SUPPORTDESK, timeout_s=120)
    assert result.ok, result.output
