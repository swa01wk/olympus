from __future__ import annotations

import pytest
from core.domain.enums import EntityStatus, EvidenceRequirement, ModelOrigin, SpecStatus
from core.product_model.models import (
    AcceptanceCriterion,
    Capability,
    Feature,
    FeatureSpec,
    Requirement,
)
from core.product_model.specifications.scope import ScopeService


@pytest.mark.persistence
@pytest.mark.asyncio
async def test_scope_rejection_marks_proposed_specs_rejected(
    db_session, sample_project, operator_ctx
) -> None:
    cap = Capability(
        project_id=sample_project.id,
        key="CAP-R",
        name="Cap",
        description="d",
        status=EntityStatus.PROPOSED,
        origin=ModelOrigin.HUMAN,
        source_refs=[],
    )
    db_session.add(cap)
    await db_session.flush()
    feat = Feature(
        project_id=sample_project.id,
        capability_id=cap.id,
        key="FEAT-R",
        name="Feat",
        description="d",
        status=EntityStatus.PROPOSED,
        origin=ModelOrigin.HUMAN,
        source_refs=[],
    )
    db_session.add(feat)
    await db_session.flush()
    spec = FeatureSpec(
        project_id=sample_project.id,
        feature_id=feat.id,
        lineage_key="SPEC-R",
        version=1,
        status=SpecStatus.PROPOSED,
        body={"behavior": "b", "summary": "s", "inputs": [], "outputs": [], "rules": []},
        content_hash="abc",
    )
    db_session.add(spec)
    await db_session.flush()
    db_session.add(
        Requirement(
            feature_spec_id=spec.id,
            lineage_key="REQ-R",
            statement="r",
            kind="FUNCTIONAL",
            priority="MUST",
        )
    )
    db_session.add(
        AcceptanceCriterion(
            feature_spec_id=spec.id,
            lineage_key="AC-R",
            statement="a",
            mandatory=True,
            evidence_requirement=EvidenceRequirement.EXECUTABLE,
            requirement_keys=["REQ-R"],
        )
    )
    await db_session.flush()

    from core.domain.delivery_cycles.service import DeliveryCycleService
    from core.domain.enums import DeliveryCycleType

    cycle = await DeliveryCycleService().create(
        db_session,
        sample_project.id,
        DeliveryCycleType.GREENFIELD_BUILD,
        "reject",
        operator_ctx,
    )
    scope_set, approval_id = await ScopeService().request_scope_approval(
        db_session, cycle.id, [spec.id], sample_project.id, operator_ctx
    )
    from core.domain.approvals.service import ApprovalService
    from core.domain.enums import ApprovalStatus

    await ApprovalService().decide(
        db_session, approval_id, ApprovalStatus.REJECTED, "no", operator_ctx
    )
    await ScopeService().on_scope_rejected(db_session, scope_set.id, approval_id, operator_ctx)
    await db_session.refresh(spec)
    assert spec.status == SpecStatus.REJECTED
