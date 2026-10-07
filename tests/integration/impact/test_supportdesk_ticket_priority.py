from __future__ import annotations

import pytest
from core.domain.approvals.service import ApprovalService
from core.domain.enums import ApprovalStatus
from core.intelligence.impact.engine import ImpactEngine
from core.intelligence.impact.enums import ImpactItemType, ImpactRetrievalSource
from core.intelligence.impact.models import ImpactItem
from core.product_model.specifications.delta import SpecDeltaService
from sqlalchemy import select
from tests.fixtures.impact_harness import seed_supportdesk_ticket_priority_impact

pytestmark = [pytest.mark.integration, pytest.mark.asyncio]


async def test_priority_delta_impact_includes_ticket_surface(
    db_session, system_ctx, operator_ctx
) -> None:
    fx = await seed_supportdesk_ticket_priority_impact(db_session, system_ctx)
    delta = await SpecDeltaService().compute(
        db_session,
        from_spec_id=fx.spec_v1_id,
        to_spec_id=fx.spec_v2_id,
        delivery_cycle_id=fx.cycle_id,
        ctx=system_ctx,
    )
    approval_id = (
        await SpecDeltaService().request_approval(db_session, delta.id, system_ctx)
    ).approval_id
    assert approval_id is not None
    await ApprovalService().decide(
        db_session, approval_id, ApprovalStatus.APPROVED, None, operator_ctx
    )
    await SpecDeltaService().mark_approved(db_session, delta.id, approval_id, operator_ctx)

    ia = await ImpactEngine().assess(
        db_session,
        fx.cycle_id,
        spec_delta_id=delta.id,
        index_version_id=fx.index_version.id,
        ctx=system_ctx,
    )
    items = list(
        (
            await db_session.execute(
                select(ImpactItem).where(ImpactItem.impact_assessment_id == ia.id)
            )
        ).scalars()
    )
    refs = {i.ref for i in items}
    assert "ROUTE:POST /tickets" in refs
    assert any("TicketCreate" in r or "ticket" in r.lower() for r in refs)
    assert any("test" in r.lower() and "create" in r.lower() for r in refs)

    structural = [i for i in items if i.retrieval_source == ImpactRetrievalSource.STRUCTURAL.value]
    assert structural
    assert all(i.confidence > 0 for i in items)
    code_entities = [i for i in structural if i.item_type == ImpactItemType.CODE_ENTITY.value]
    assert all(i.path is not None for i in code_entities)

    contracts = [i for i in items if i.contract_surface]
    types = {i.ref for i in contracts}
    assert any("ROUTE:" in t for t in types)
