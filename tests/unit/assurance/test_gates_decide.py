from __future__ import annotations

import pytest
from core.assurance.enums import GateType
from core.assurance.gates import GateDecisionInputs, decide

pytestmark = pytest.mark.unit


def test_missing_mandatory_evidence_fails() -> None:
    inputs = GateDecisionInputs(
        integrated_sha="abc",
        canonical_commit="abc",
        gate_type=GateType.SENTINEL.value,
        obligations=(
            {
                "id": "1",
                "required": True,
                "status": "OPEN",
                "subject_key": "AC-1",
                "allowed_evidence_types": ["UNIT_TEST"],
            },
        ),
        coverage_rows=(),
        evidence_rows=(),
        blocking_findings=(),
        agent_recommendation=None,
        policy={"assurance": {"warden_review_required": True}},
    )
    decision = decide(inputs)
    assert decision.status.value == "FAIL"
    assert any("OBLIGATION_UNSATISFIED" in r for r in decision.reasons)


def test_recommendation_fail_overridden_when_deterministic_pass() -> None:
    inputs = GateDecisionInputs(
        integrated_sha="abc",
        canonical_commit="abc",
        gate_type=GateType.INTEGRATION.value,
        obligations=(),
        coverage_rows=(),
        evidence_rows=(
            {
                "id": "e1",
                "key": "EV-1",
                "commit_sha": "abc",
                "evidence_type": "INTEGRATION_CHECK",
                "result": "PASS",
            },
        ),
        blocking_findings=(),
        agent_recommendation={"recommended": "FAIL"},
        policy={"assurance": {"warden_review_required": True}},
    )
    decision = decide(inputs)
    assert decision.status.value == "PASS"
    assert decision.recommendation_overridden is True


def test_model_assessment_does_not_satisfy_executable_ac() -> None:
    from core.assurance.evidence_rules import evidence_satisfies_mandatory

    assert not evidence_satisfies_mandatory(
        "MODEL_ASSESSMENT",
        ["UNIT_TEST"],
        required=True,
    )


def test_static_review_satisfies_review_allowed() -> None:
    from core.assurance.evidence_rules import evidence_satisfies_mandatory

    assert evidence_satisfies_mandatory(
        "STATIC_REVIEW",
        ["UNIT_TEST", "STATIC_REVIEW"],
        required=True,
    )
