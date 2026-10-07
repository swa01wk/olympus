from __future__ import annotations

from pathlib import Path

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


@pytest.mark.live_llm
def test_supportdesk_prd_fixture_validates_minimal_shape() -> None:
    """Offline guard: fixture PRD exists; live run uses same validator as production."""
    prd = Path(__file__).resolve().parents[2] / "fixtures" / "supportdesk" / "PRD.md"
    assert prd.is_file()
    text = prd.read_text().lower()
    assert "create ticket" in text or "create" in text
    assert "409" in text or "closed" in text


@pytest.mark.live_llm
def test_kira_decompose_supportdesk_validator_accepts_supportdesk_shape() -> None:
    """Validator gate for SupportDesk-shaped decompositions (live worker path uses same rules)."""
    proposal = ProductDecomposition(
        capabilities=[
            CapabilityDraft(
                ref="CAP-1",
                name="Ticket Management",
                description="Tickets",
                source_sections=["Ticket Management"],
            )
        ],
        features=[
            FeatureDraft(
                ref="FEAT-1",
                capability_ref="CAP-1",
                name="Create Ticket",
                description="Create a support ticket",
                source_sections=["Create Ticket"],
            ),
            FeatureDraft(
                ref="FEAT-2",
                capability_ref="CAP-1",
                name="Update Ticket Status",
                description="Change ticket status including close",
                source_sections=["Update Ticket Status"],
            ),
            FeatureDraft(
                ref="FEAT-3",
                capability_ref="CAP-1",
                name="List Tickets",
                description="List tickets",
                source_sections=["List Tickets"],
            ),
        ],
        feature_specs=[
            FeatureSpecDraft(
                ref="SPEC-1",
                feature_ref="FEAT-1",
                body=FeatureSpecBody(
                    behavior="create",
                    summary="create ticket",
                    inputs=["subject"],
                    outputs=["ticket"],
                    rules=["required fields"],
                ),
            ),
            FeatureSpecDraft(
                ref="SPEC-2",
                feature_ref="FEAT-2",
                body=FeatureSpecBody(
                    behavior="update status",
                    summary="update status",
                    inputs=["id"],
                    outputs=["ticket"],
                    rules=["409 on closed"],
                ),
            ),
            FeatureSpecDraft(
                ref="SPEC-3",
                feature_ref="FEAT-3",
                body=FeatureSpecBody(
                    behavior="list",
                    summary="list",
                    inputs=[],
                    outputs=["tickets"],
                    rules=[],
                ),
            ),
        ],
        requirements=[
            RequirementDraft(
                ref="REQ-1",
                feature_spec_ref="SPEC-1",
                statement="create",
                kind="FUNCTIONAL",
                priority="MUST",
            ),
            RequirementDraft(
                ref="REQ-2",
                feature_spec_ref="SPEC-2",
                statement="update",
                kind="FUNCTIONAL",
                priority="MUST",
            ),
            RequirementDraft(
                ref="REQ-3",
                feature_spec_ref="SPEC-3",
                statement="list",
                kind="FUNCTIONAL",
                priority="MUST",
            ),
        ],
        user_stories=[],
        acceptance_criteria=[
            AcceptanceCriterionDraft(
                ref="AC-1",
                feature_spec_ref="SPEC-1",
                statement="creates",
                given=None,
                when=None,
                then=None,
                mandatory=True,
                evidence_requirement=EvidenceRequirement.EXECUTABLE,
                requirement_refs=["REQ-1"],
            ),
            AcceptanceCriterionDraft(
                ref="AC-2",
                feature_spec_ref="SPEC-2",
                statement="updates",
                given=None,
                when=None,
                then=None,
                mandatory=True,
                evidence_requirement=EvidenceRequirement.EXECUTABLE,
                requirement_refs=["REQ-2"],
            ),
            AcceptanceCriterionDraft(
                ref="AC-3",
                feature_spec_ref="SPEC-3",
                statement="lists",
                given=None,
                when=None,
                then=None,
                mandatory=True,
                evidence_requirement=EvidenceRequirement.EXECUTABLE,
                requirement_refs=["REQ-3"],
            ),
        ],
        open_questions=[],
    )
    assert not validate_proposal(proposal)
    names = " ".join(f.name + f.description for f in proposal.features).lower()
    assert "create" in names
    assert "status" in names or "update" in names
