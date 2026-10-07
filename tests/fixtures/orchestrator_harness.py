"""Minimal seeds for Orchestrator live / integration tests."""

from __future__ import annotations

import uuid

from core.assurance.findings import FindingService
from core.commands.context import CommandContext
from core.domain.approvals.models import Approval
from core.domain.enums import ApprovalStatus, ApprovalType, ClarificationStatus
from core.domain.executions.models import Clarification
from core.domain.sequences import next_project_key
from core.integration.enums import FindingSeverity, FindingSource
from sqlalchemy.ext.asyncio import AsyncSession


async def seed_open_clarification(
    session: AsyncSession,
    *,
    project_id: uuid.UUID,
    delivery_cycle_id: uuid.UUID,
    question: str,
    ctx: CommandContext,
) -> Clarification:
    key = await next_project_key(session, project_id, "clarification", prefix="CL")
    row = Clarification(
        key=key,
        project_id=project_id,
        delivery_cycle_id=delivery_cycle_id,
        question=question,
        context={"text": "orchestrator test"},
        options=[],
        blocking=True,
        status=ClarificationStatus.OPEN,
    )
    session.add(row)
    await session.flush()
    _ = ctx
    return row


async def seed_pending_scope_approval(
    session: AsyncSession,
    *,
    project_id: uuid.UUID,
    delivery_cycle_id: uuid.UUID,
    ctx: CommandContext,
) -> Approval:
    key = await next_project_key(session, project_id, "approval", prefix="A")
    row = Approval(
        key=key,
        project_id=project_id,
        delivery_cycle_id=delivery_cycle_id,
        approval_type=ApprovalType.SCOPE,
        subject_type="SCOPE_SET",
        subject_id=uuid.uuid4(),
        subject_version=1,
        subject_hash="orch-test-hash",
        status=ApprovalStatus.PENDING,
        requested_by_actor_id=ctx.actor.id,
    )
    session.add(row)
    await session.flush()
    return row


async def seed_blocking_finding_for_cycle(
    session: AsyncSession,
    *,
    project_id: uuid.UUID,
    delivery_cycle_id: uuid.UUID,
    ctx: CommandContext,
    ic_id: uuid.UUID | None = None,
) -> None:
    await FindingService().create(
        session,
        project_id=project_id,
        delivery_cycle_id=delivery_cycle_id,
        integration_candidate_id=ic_id,
        source=FindingSource.SENTINEL,
        category="CORRECTNESS",
        severity=FindingSeverity.BLOCKER,
        title="Blocking release test finding",
        detail={"test": True},
        ctx=ctx,
    )
