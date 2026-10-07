from __future__ import annotations

from core.domain.enums import EvidenceRequirement
from core.product_model.changes.interpretation import ChangeInterpretationValidator
from core.product_model.changes.schemas import AcChange, ChangeInterpretation
from core.product_model.schemas import FeatureSpecBody


def _body() -> FeatureSpecBody:
    return FeatureSpecBody(
        behavior="x",
        summary="x",
        inputs=["a"],
        outputs=["b"],
        rules=[],
    )


def test_unknown_feature_key_rejected() -> None:
    interp = ChangeInterpretation(
        resolution="EXISTING_FEATURE",
        feature_key="FEAT-UNKNOWN",
        proposed_feature_spec=_body(),
        architecture_change_expected=False,
        architecture_rationale="none",
        candidate_ranking_rationale="test",
    )
    ok, errors = ChangeInterpretationValidator().validate(
        interp,
        candidate_feature_keys={"FEAT-TICKETS"},
        current_ac_lineage_keys=set(),
    )
    assert not ok
    assert any("not in candidates" in e for e in errors)


def test_add_ac_requires_evidence() -> None:
    interp = ChangeInterpretation(
        resolution="EXISTING_FEATURE",
        feature_key="FEAT-TICKETS",
        proposed_feature_spec=_body(),
        acceptance_criteria_changes=[
            AcChange(op="ADD", lineage_key="AC-NEW", statement="s", mandatory=True, rationale="r")
        ],
        architecture_change_expected=False,
        architecture_rationale="none",
        candidate_ranking_rationale="test",
    )
    ok, errors = ChangeInterpretationValidator().validate(
        interp,
        candidate_feature_keys={"FEAT-TICKETS"},
        current_ac_lineage_keys=set(),
    )
    assert not ok
    assert any("evidence_requirement" in e for e in errors)


def test_remove_mandatory_requires_note() -> None:
    interp = ChangeInterpretation(
        resolution="EXISTING_FEATURE",
        feature_key="FEAT-TICKETS",
        proposed_feature_spec=_body(),
        acceptance_criteria_changes=[
            AcChange(
                op="REMOVE",
                lineage_key="AC-OLD",
                mandatory=True,
                rationale="",
            )
        ],
        architecture_change_expected=False,
        architecture_rationale="none",
        candidate_ranking_rationale="test",
    )
    ok, errors = ChangeInterpretationValidator().validate(
        interp,
        candidate_feature_keys={"FEAT-TICKETS"},
        current_ac_lineage_keys={"AC-OLD"},
    )
    assert not ok
    assert any("requires rationale" in e for e in errors)


def test_valid_add_ac() -> None:
    interp = ChangeInterpretation(
        resolution="EXISTING_FEATURE",
        feature_key="FEAT-TICKETS",
        proposed_feature_spec=_body(),
        acceptance_criteria_changes=[
            AcChange(
                op="ADD",
                lineage_key="AC-PRIORITY",
                statement="priority enum",
                mandatory=True,
                evidence_requirement=EvidenceRequirement.EXECUTABLE,
                rationale="new behavior",
            )
        ],
        architecture_change_expected=False,
        architecture_rationale="none",
        candidate_ranking_rationale="test",
    )
    ok, errors = ChangeInterpretationValidator().validate(
        interp,
        candidate_feature_keys={"FEAT-TICKETS"},
        current_ac_lineage_keys={"AC-CREATE"},
    )
    assert ok, errors
