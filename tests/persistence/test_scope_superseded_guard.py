from __future__ import annotations

import pytest
from core.domain.approvals.service import ApprovalService
from core.domain.enums import ApprovalStatus, SpecStatus
from core.product_model.guards import scope_approved
from core.product_model.models import FeatureSpec
from core.product_model.schemas import FeatureSpecBody
from core.product_model.service import ProductModelService
from core.product_model.specifications.scope import ScopeService
from core.product_model.specifications.service import FeatureSpecService
from sqlalchemy import select
from tests.fixtures.product_model_harness import supportdesk_decomposition

pytestmark = pytest.mark.persistence


@pytest.mark.asyncio
async def test_scope_guard_rejects_superseded_spec_in_approved_scope(
    db_session, sample_project, operator_ctx
) -> None:
    from core.domain.delivery_cycles.service import DeliveryCycleService
    from core.domain.enums import DeliveryCycleType
    from core.product_model.models import ProductSource
    from core.product_model.sources.service import ProductSourceService

    cycle = await DeliveryCycleService().create(
        db_session,
        sample_project.id,
        DeliveryCycleType.GREENFIELD_BUILD,
        "superseded-scope",
        operator_ctx,
    )
    ingest = await ProductSourceService().ingest(
        db_session,
        project_id=sample_project.id,
        lineage_key="sup-scope",
        source_type="PRD",
        title="t",
        mime_type="text/plain",
        content_hash="superseded-scope-hash",
        raw_storage_ref="inbound/sha256/x/superseded",
        text="hello",
        ctx=operator_ctx,
        delivery_cycle_id=cycle.id,
    )
    source = await db_session.get(ProductSource, ingest["product_source_id"])
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
    first_spec = await db_session.get(FeatureSpec, spec_ids[0])
    assert first_spec is not None
    await FeatureSpecService().create_draft_version(
        db_session,
        first_spec.feature_id,
        FeatureSpecBody(
            behavior="rev",
            summary="v2",
            inputs=["a"],
            outputs=["b"],
            rules=["r"],
        ),
        operator_ctx,
    )
    superseded = await db_session.get(FeatureSpec, spec_ids[0])
    assert superseded is not None
    assert superseded.status == SpecStatus.SUPERSEDED

    await ApprovalService().decide(
        db_session, approval_id, ApprovalStatus.APPROVED, None, operator_ctx
    )

    result = await scope_approved(db_session, cycle, operator_ctx)
    assert result.ok is False
    assert "SCOPE_SPEC_SUPERSEDED" in result.reasons
