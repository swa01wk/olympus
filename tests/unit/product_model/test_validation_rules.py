from __future__ import annotations

import copy

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
from core.product_model.validation import validate_proposal


def _base() -> ProductDecomposition:
    return ProductDecomposition(
        capabilities=[
            CapabilityDraft(ref="CAP-1", name="C", description="d", source_sections=["S1"])
        ],
        features=[
            FeatureDraft(
                ref="FEAT-1",
                capability_ref="CAP-1",
                name="F",
                description="d",
                source_sections=["S2"],
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
                statement="r",
                kind="FUNCTIONAL",
                priority="MUST",
            )
        ],
        user_stories=[],
        acceptance_criteria=[
            AcceptanceCriterionDraft(
                ref="AC-1",
                feature_spec_ref="SPEC-1",
                statement="a",
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


def _mut_unknown_capability(p: ProductDecomposition) -> None:
    p.features.__setitem__(0, p.features[0].model_copy(update={"capability_ref": "CAP-X"}))


def _mut_empty_cap_section(p: ProductDecomposition) -> None:
    p.capabilities.__setitem__(0, p.capabilities[0].model_copy(update={"source_sections": [""]}))


def _mut_empty_feat_section(p: ProductDecomposition) -> None:
    p.features.__setitem__(0, p.features[0].model_copy(update={"source_sections": ["  "]}))


def _mut_unknown_feature_ref(p: ProductDecomposition) -> None:
    p.feature_specs.__setitem__(0, p.feature_specs[0].model_copy(update={"feature_ref": "FEAT-X"}))


def _mut_extra_feature(p: ProductDecomposition) -> None:
    p.features.append(p.features[0].model_copy(update={"ref": "FEAT-2"}))


def _mut_unknown_req_spec(p: ProductDecomposition) -> None:
    p.requirements.__setitem__(
        0, p.requirements[0].model_copy(update={"feature_spec_ref": "SPEC-X"})
    )


def _mut_no_requirements(p: ProductDecomposition) -> None:
    p.requirements.clear()


def _mut_unknown_ac_spec(p: ProductDecomposition) -> None:
    p.acceptance_criteria.__setitem__(
        0, p.acceptance_criteria[0].model_copy(update={"feature_spec_ref": "SPEC-X"})
    )


def _mut_ac_no_req_refs(p: ProductDecomposition) -> None:
    p.acceptance_criteria.__setitem__(
        0, p.acceptance_criteria[0].model_copy(update={"requirement_refs": []})
    )


def _mut_ac_bad_req_ref(p: ProductDecomposition) -> None:
    p.acceptance_criteria.__setitem__(
        0, p.acceptance_criteria[0].model_copy(update={"requirement_refs": ["REQ-X"]})
    )


@pytest.mark.unit
@pytest.mark.parametrize(
    "mutator,needle",
    [
        (_mut_unknown_capability, "references unknown capability"),
        (_mut_empty_cap_section, "empty source_sections entry"),
        (_mut_empty_feat_section, "empty source_sections entry"),
        (_mut_unknown_feature_ref, "references unknown feature"),
        (_mut_extra_feature, "exactly one feature_spec"),
        (_mut_unknown_req_spec, "references unknown spec"),
        (_mut_no_requirements, "must have at least one requirement"),
        (_mut_unknown_ac_spec, "references unknown spec"),
        (_mut_ac_no_req_refs, "must reference at least one requirement"),
        (_mut_ac_bad_req_ref, "not in same spec"),
    ],
)
def test_validate_proposal_rule_violations(mutator, needle: str) -> None:
    p = _base()
    mutator(p)
    errors = validate_proposal(p)
    assert any(needle in e for e in errors), errors


@pytest.mark.unit
def test_validate_proposal_rejects_review_allowed_on_functional_mandatory_ac() -> None:
    p = _base()
    p.acceptance_criteria[0] = p.acceptance_criteria[0].model_copy(
        update={"evidence_requirement": EvidenceRequirement.REVIEW_ALLOWED}
    )
    errors = validate_proposal(p)
    assert any("REVIEW_ALLOWED" in e for e in errors)


@pytest.mark.unit
def test_validate_proposal_allows_review_allowed_for_non_functional() -> None:
    p = _base()
    p.requirements[0] = p.requirements[0].model_copy(update={"kind": "NON_FUNCTIONAL"})
    p.acceptance_criteria[0] = p.acceptance_criteria[0].model_copy(
        update={"evidence_requirement": EvidenceRequirement.REVIEW_ALLOWED}
    )
    assert validate_proposal(p) == []


@pytest.mark.unit
def test_validate_proposal_rejects_duplicate_feature_spec_refs() -> None:
    p = _base()
    extra = copy.deepcopy(p.feature_specs[0])
    extra.ref = "SPEC-1"
    p.feature_specs.append(extra)
    assert any("duplicate feature_spec" in e for e in validate_proposal(p))
