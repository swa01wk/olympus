"""Release eligibility condition registry (Phase 10)."""

from __future__ import annotations

import pytest
from core.release.eligibility import get_eligibility_registry, register_core_eligibility_conditions

pytestmark = pytest.mark.unit


def test_core_conditions_registered() -> None:
    register_core_eligibility_conditions()
    reg = get_eligibility_registry()
    for name in (
        "manifest_valid",
        "integration_candidate_is_current",
        "required_gates_pass",
        "required_approvals_exist",
        "required_executions_not_stale",
        "blocking_findings",
        "mandatory_acceptance_criteria_have_evidence",
        "required_behavioral_baselines_pass",
    ):
        assert reg.get(name) is not None
