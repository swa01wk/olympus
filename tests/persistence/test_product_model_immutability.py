from __future__ import annotations

import uuid

import pytest
from core.domain.enums import EntityStatus, EvidenceRequirement, ModelOrigin, SpecStatus
from core.product_model.models import (
    AcceptanceCriterion,
    Capability,
    Feature,
    FeatureSpec,
    Requirement,
)
from core.product_model.service import ProductModelService
from core.product_model.specifications.scope import ScopeService
from sqlalchemy import select
from sqlalchemy.exc import DBAPIError
from tests.fixtures.product_model_harness import supportdesk_decomposition

pytestmark = pytest.mark.persistence


@pytest.mark.asyncio
async def test_approved_feature_spec_and_locked_children_immutable(
    db_session, sample_project, operator_actor, operator_ctx
) -> None:
    from core.domain.delivery_cycles.service import DeliveryCycleService
    from core.domain.enums import DeliveryCycleType
    from core.product_model.models import ProductSource
    from core.product_model.sources.service import ProductSourceService

    cycle = await DeliveryCycleService().create(
        db_session,
        sample_project.id,
        DeliveryCycleType.GREENFIELD_BUILD,
        "immutability",
        operator_ctx,
    )
    ingest = await ProductSourceService().ingest(
        db_session,
        project_id=sample_project.id,
        lineage_key="imm",
        source_type="PRD",
        title="t",
        mime_type="text/plain",
        content_hash="abc123",
        raw_storage_ref="inbound/sha256/x/abc123",
        text="hello",
        ctx=operator_ctx,
        delivery_cycle_id=cycle.id,
    )
    source = await db_session.get(ProductSource, uuid.UUID(ingest["product_source_id"]))
    assert source is not None
    await ProductModelService().persist_proposal(
        db_session,
        project_id=sample_project.id,
        delivery_cycle_id=cycle.id,
        product_source_version_id=source.id,
        execution_id=None,
        proposal=supportdesk_decomposition(),
        ctx=operator_ctx,
    )
    specs = (
        await db_session.execute(
            select(FeatureSpec).where(FeatureSpec.project_id == sample_project.id)
        )
    ).scalars()
    spec_ids = [s.id for s in specs]
    scope_set, approval_id = await ScopeService().request_scope_approval(
        db_session,
        cycle.id,
        spec_ids,
        sample_project.id,
        operator_ctx,
    )
    from core.domain.approvals.service import ApprovalService
    from core.domain.enums import ApprovalStatus

    await ApprovalService().decide(
        db_session, approval_id, ApprovalStatus.APPROVED, None, operator_ctx
    )
    await ScopeService().on_scope_approved(db_session, scope_set.id, approval_id, operator_ctx)

    spec = await db_session.get(FeatureSpec, spec_ids[0])
    assert spec is not None
    assert spec.status == SpecStatus.APPROVED

    spec_id = spec_ids[0]
    with pytest.raises(DBAPIError):
        async with db_session.begin_nested():
            spec.body = {"tampered": True}
            await db_session.flush()

    req = (
        await db_session.execute(select(Requirement).where(Requirement.feature_spec_id == spec_id))
    ).scalar_one()
    assert req.locked is True
    with pytest.raises(DBAPIError):
        async with db_session.begin_nested():
            req.statement = "changed"
            await db_session.flush()


@pytest.mark.asyncio
async def test_scope_approval_cascade_approves_entities(
    db_session, sample_project, operator_actor, operator_ctx
) -> None:
    cap = Capability(
        project_id=sample_project.id,
        key="CAP-X",
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
        key="FEAT-X",
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
        lineage_key="SPEC-FEAT-X",
        version=1,
        status=SpecStatus.PROPOSED,
        body={"behavior": "b", "summary": "s", "inputs": [], "outputs": [], "rules": []},
        content_hash="deadbeef",
    )
    db_session.add(spec)
    await db_session.flush()
    db_session.add(
        Requirement(
            feature_spec_id=spec.id,
            lineage_key="REQ-1",
            statement="r",
            kind="FUNCTIONAL",
            priority="MUST",
        )
    )
    db_session.add(
        AcceptanceCriterion(
            feature_spec_id=spec.id,
            lineage_key="AC-1",
            statement="a",
            mandatory=True,
            evidence_requirement=EvidenceRequirement.EXECUTABLE,
            requirement_keys=["REQ-1"],
        )
    )
    await db_session.flush()

    from core.domain.delivery_cycles.service import DeliveryCycleService
    from core.domain.enums import DeliveryCycleType

    cycle = await DeliveryCycleService().create(
        db_session,
        sample_project.id,
        DeliveryCycleType.GREENFIELD_BUILD,
        "scope",
        operator_ctx,
    )
    scope_set, approval_id = await ScopeService().request_scope_approval(
        db_session, cycle.id, [spec.id], sample_project.id, operator_ctx
    )
    from core.domain.approvals.service import ApprovalService
    from core.domain.enums import ApprovalStatus

    await ApprovalService().decide(
        db_session, approval_id, ApprovalStatus.APPROVED, None, operator_ctx
    )
    await ScopeService().on_scope_approved(db_session, scope_set.id, approval_id, operator_ctx)

    await db_session.refresh(spec)
    await db_session.refresh(feat)
    await db_session.refresh(cap)
    assert spec.status == SpecStatus.APPROVED
    assert feat.status == EntityStatus.APPROVED
    assert cap.status == EntityStatus.APPROVED
