"""RL2.4 — auto-request pending approvals after persist; endpoints stay idempotent."""

from __future__ import annotations

import pytest
from core.domain.approvals.models import Approval
from core.domain.delivery_cycles.models import DeliveryCycle
from core.domain.enums import ApprovalStatus, ApprovalType, DeliveryCycleType
from core.planning.architecture.service import ArchitectureService
from sqlalchemy import func, select
from tests.fixtures.planning_harness import supportdesk_architecture_proposal
from tests.fixtures.planning_workflow_harness import seed_supportdesk_product_and_approved_scope

pytestmark = pytest.mark.integration


@pytest.mark.asyncio
async def test_architecture_persist_auto_pending_and_endpoint_idempotent(
    db_session, sample_project, operator_ctx
) -> None:
    cycle = DeliveryCycle(
        project_id=sample_project.id,
        key="AUTO",
        type=DeliveryCycleType.GREENFIELD_BUILD,
        objective="auto approval",
        state="ARCHITECTURE",
        state_version=0,
        opened_by_actor_id=operator_ctx.actor.id,
    )
    db_session.add(cycle)
    await db_session.flush()

    await seed_supportdesk_product_and_approved_scope(
        db_session, sample_project.id, cycle.id, operator_ctx
    )

    arch = await ArchitectureService().persist_proposal(
        db_session,
        project_id=sample_project.id,
        proposal=supportdesk_architecture_proposal(),
        execution_id=None,
        ctx=operator_ctx,
        delivery_cycle_id=cycle.id,
    )

    pending_count = (
        await db_session.execute(
            select(func.count())
            .select_from(Approval)
            .where(
                Approval.approval_type == ApprovalType.ARCHITECTURE,
                Approval.subject_id == arch.id,
                Approval.status == ApprovalStatus.PENDING,
            )
        )
    ).scalar_one()
    assert pending_count == 1

    auto_id = (
        await db_session.execute(
            select(Approval.id).where(
                Approval.approval_type == ApprovalType.ARCHITECTURE,
                Approval.subject_id == arch.id,
                Approval.status == ApprovalStatus.PENDING,
            )
        )
    ).scalar_one()

    endpoint_id = await ArchitectureService().request_approval(
        db_session, arch.id, cycle.id, operator_ctx
    )
    assert endpoint_id == auto_id

    pending_count_after = (
        await db_session.execute(
            select(func.count())
            .select_from(Approval)
            .where(
                Approval.approval_type == ApprovalType.ARCHITECTURE,
                Approval.subject_id == arch.id,
                Approval.status == ApprovalStatus.PENDING,
            )
        )
    ).scalar_one()
    assert pending_count_after == 1
