from __future__ import annotations

import pytest
from core.domain.enums import EvidenceRequirement
from core.product_model.schemas import (
    AcceptanceCriterionDraft,
    CapabilityDraft,
    FeatureDraft,
    FeatureSpecBody,
    FeatureSpecDraft,
    ProductDecomposition,
    RequirementDraft,
)
from core.product_model.validation import sanitize_proposal_requirement_refs, validate_proposal


def _minimal_valid() -> ProductDecomposition:
    return ProductDecomposition(
        capabilities=[
            CapabilityDraft(ref="CAP-1", name="Cap", description="d", source_sections=["Overview"])
        ],
        features=[
            FeatureDraft(
                ref="FEAT-1",
                capability_ref="CAP-1",
                name="F",
                description="d",
                source_sections=["Feature"],
            )
        ],
        feature_specs=[
            FeatureSpecDraft(
                ref="SPEC-1",
                feature_ref="FEAT-1",
                body=FeatureSpecBody(
                    behavior="b",
                    summary="s",
                    inputs=["i"],
                    outputs=["o"],
                    rules=["r"],
                ),
            )
        ],
        requirements=[
            RequirementDraft(
                ref="REQ-1",
                feature_spec_ref="SPEC-1",
                statement="must work",
                kind="FUNCTIONAL",
                priority="MUST",
            )
        ],
        user_stories=[],
        acceptance_criteria=[
            AcceptanceCriterionDraft(
                ref="AC-1",
                feature_spec_ref="SPEC-1",
                statement="works",
                given=None,
                when=None,
                then=None,
                mandatory=True,
                evidence_requirement=EvidenceRequirement.EXECUTABLE,
                requirement_refs=["REQ-1"],
            )
        ],
        open_questions=[],
    )


@pytest.mark.unit
def test_validate_proposal_accepts_minimal() -> None:
    assert validate_proposal(_minimal_valid()) == []


@pytest.mark.unit
def test_validate_proposal_rejects_duplicate_refs() -> None:
    p = _minimal_valid()
    p.capabilities.append(p.capabilities[0])
    assert any("duplicate" in e for e in validate_proposal(p))


@pytest.mark.unit
def test_validate_proposal_requires_mandatory_ac() -> None:
    p = _minimal_valid()
    p.acceptance_criteria[0].mandatory = False
    assert any("mandatory AC" in e for e in validate_proposal(p))


@pytest.mark.unit
def test_sanitize_proposal_drops_cross_spec_requirement_refs() -> None:
    p = _minimal_valid()
    p = p.model_copy(
        update={
            "requirements": [
                *p.requirements,
                RequirementDraft(
                    ref="REQ-2",
                    feature_spec_ref="SPEC-1",
                    statement="other",
                    kind="FUNCTIONAL",
                    priority="SHOULD",
                ),
            ],
            "acceptance_criteria": [
                AcceptanceCriterionDraft(
                    ref="AC-1",
                    feature_spec_ref="SPEC-1",
                    statement="works",
                    given=None,
                    when=None,
                    then=None,
                    mandatory=True,
                    evidence_requirement=EvidenceRequirement.EXECUTABLE,
                    requirement_refs=["REQ-11"],
                )
            ],
        }
    )
    fixed = sanitize_proposal_requirement_refs(p)
    assert fixed.acceptance_criteria[0].requirement_refs == ["REQ-1"]
    assert validate_proposal(fixed) == []
