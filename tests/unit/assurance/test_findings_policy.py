from __future__ import annotations

import pytest
from core.assurance.findings_policy import FindingPolicy

pytestmark = pytest.mark.unit


def test_finding_policy_merge_conflict_is_blocking() -> None:
    assert FindingPolicy().is_blocking("MAJOR", "MERGE_CONFLICT") is True


def test_finding_policy_minor_style_not_blocking_by_default() -> None:
    assert FindingPolicy().is_blocking("MINOR", "STYLE") is False
