from __future__ import annotations

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


def supportdesk_decomposition() -> ProductDecomposition:
    """Minimal valid decomposition aligned with tests/fixtures/supportdesk/PRD.md themes."""
    return ProductDecomposition(
        capabilities=[
            CapabilityDraft(
                ref="CAP-1",
                name="Ticket Management",
                description="Support ticket lifecycle",
                source_sections=["Ticket Management"],
            )
        ],
        features=[
            FeatureDraft(
                ref="FEAT-1",
                capability_ref="CAP-1",
                name="Create Ticket",
                description="Create a support ticket with subject and description",
                source_sections=["Create Ticket"],
            ),
            FeatureDraft(
                ref="FEAT-2",
                capability_ref="CAP-1",
                name="Update Ticket Status",
                description="Update ticket status; reject changes to closed tickets with 409",
                source_sections=["Update Ticket Status"],
            ),
        ],
        feature_specs=[
            FeatureSpecDraft(
                ref="SPEC-1",
                feature_ref="FEAT-1",
                body=FeatureSpecBody(
                    behavior="Create tickets",
                    summary="Create ticket",
                    inputs=["subject", "description"],
                    outputs=["ticket"],
                    rules=["subject and description required", "default status OPEN"],
                ),
            ),
            FeatureSpecDraft(
                ref="SPEC-2",
                feature_ref="FEAT-2",
                body=FeatureSpecBody(
                    behavior="Update status",
                    summary="Update ticket status",
                    inputs=["ticket_id", "status"],
                    outputs=["ticket"],
                    rules=["closed tickets cannot be modified", "409 on closed update"],
                ),
            ),
        ],
        requirements=[
            RequirementDraft(
                ref="REQ-1",
                feature_spec_ref="SPEC-1",
                statement="Must create ticket",
                kind="FUNCTIONAL",
                priority="MUST",
            ),
            RequirementDraft(
                ref="REQ-2",
                feature_spec_ref="SPEC-2",
                statement="Must update status",
                kind="FUNCTIONAL",
                priority="MUST",
            ),
        ],
        user_stories=[],
        acceptance_criteria=[
            AcceptanceCriterionDraft(
                ref="AC-1",
                feature_spec_ref="SPEC-1",
                statement="Ticket is created",
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
                statement="Status updates apply",
                given=None,
                when=None,
                then=None,
                mandatory=True,
                evidence_requirement=EvidenceRequirement.EXECUTABLE,
                requirement_refs=["REQ-2"],
            ),
        ],
        open_questions=[],
    )


def supportdesk_three_ac_decomposition() -> ProductDecomposition:
    """SupportDesk PRD decomposition with a third mandatory AC (Phase 09 §12 supportdesk_r1 IC)."""
    base = supportdesk_decomposition()
    return base.model_copy(
        update={
            "acceptance_criteria": [
                *base.acceptance_criteria,
                AcceptanceCriterionDraft(
                    ref="AC-3",
                    feature_spec_ref="SPEC-2",
                    statement="Updated status is persisted on the ticket",
                    given=None,
                    when=None,
                    then=None,
                    mandatory=True,
                    evidence_requirement=EvidenceRequirement.EXECUTABLE,
                    requirement_refs=["REQ-2"],
                ),
            ]
        }
    )
