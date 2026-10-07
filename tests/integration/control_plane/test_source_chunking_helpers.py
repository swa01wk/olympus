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


def chunk_a_decomposition() -> ProductDecomposition:
    return ProductDecomposition(
        capabilities=[
            CapabilityDraft(
                ref="CAP-1",
                name="Create area",
                description="Create tickets",
                source_sections=["Create Ticket"],
            )
        ],
        features=[
            FeatureDraft(
                ref="FEAT-1",
                capability_ref="CAP-1",
                name="Create Ticket",
                description="Create",
                source_sections=["Create Ticket"],
            )
        ],
        feature_specs=[
            FeatureSpecDraft(
                ref="SPEC-1",
                feature_ref="FEAT-1",
                body=FeatureSpecBody(
                    behavior="create",
                    summary="create",
                    inputs=["subject"],
                    outputs=["ticket"],
                    rules=["default OPEN"],
                ),
            )
        ],
        requirements=[
            RequirementDraft(
                ref="REQ-1",
                feature_spec_ref="SPEC-1",
                statement="create",
                kind="FUNCTIONAL",
                priority="MUST",
            )
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
            )
        ],
        open_questions=[],
    )


def chunk_b_decomposition() -> ProductDecomposition:
    return ProductDecomposition(
        capabilities=[
            CapabilityDraft(
                ref="CAP-2",
                name="Update area",
                description="Update status",
                source_sections=["Update Ticket Status"],
            )
        ],
        features=[
            FeatureDraft(
                ref="FEAT-2",
                capability_ref="CAP-2",
                name="Update Ticket Status",
                description="Update",
                source_sections=["Update Ticket Status"],
            )
        ],
        feature_specs=[
            FeatureSpecDraft(
                ref="SPEC-2",
                feature_ref="FEAT-2",
                body=FeatureSpecBody(
                    behavior="update",
                    summary="update",
                    inputs=["status"],
                    outputs=["ticket"],
                    rules=["409 on closed"],
                ),
            )
        ],
        requirements=[
            RequirementDraft(
                ref="REQ-2",
                feature_spec_ref="SPEC-2",
                statement="update",
                kind="FUNCTIONAL",
                priority="MUST",
            )
        ],
        user_stories=[],
        acceptance_criteria=[
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
            )
        ],
        open_questions=[],
    )
