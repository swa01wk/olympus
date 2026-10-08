"""Emit revision.completed and supersede the prior subject when a revision run persists."""

from __future__ import annotations

import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from core.commands.context import CommandContext
from core.domain.approvals.models import Approval
from core.domain.enums import SpecStatus
from core.domain.events.append import append_domain_event
from core.domain.executions.models import Execution
from core.domain.task_contracts.models import TaskContract
from core.intelligence.impact.enums import SpecDeltaStatus
from core.intelligence.impact.models import SpecDelta
from core.planning.models import Architecture, ImplementationSpec


async def revision_approval_id_from_execution(
    session: AsyncSession,
    execution: Execution,
) -> uuid.UUID | None:
    contract = await session.get(TaskContract, execution.task_contract_id)
    if contract is None or not isinstance(contract.body, dict):
        return None
    snap = contract.body.get("_snapshot")
    if not isinstance(snap, dict):
        return None
    raw = snap.get("revision_of_approval_id")
    if not raw:
        return None
    try:
        return uuid.UUID(str(raw))
    except ValueError:
        return None


async def _supersede_subject(
    session: AsyncSession,
    approval: Approval,
    subject_id: uuid.UUID,
) -> None:
    subject_type = approval.subject_type
    if subject_type == "architecture":
        arch = await session.get(Architecture, subject_id)
        if arch is not None and arch.status == SpecStatus.PROPOSED:
            arch.status = SpecStatus.SUPERSEDED
        return
    if subject_type == "implementation_spec":
        impl = await session.get(ImplementationSpec, subject_id)
        if impl is not None and impl.status == SpecStatus.PROPOSED:
            impl.status = SpecStatus.SUPERSEDED
        return
    if subject_type == "SPEC_DELTA":
        delta = await session.get(SpecDelta, subject_id)
        if delta is not None and delta.status == SpecDeltaStatus.PROPOSED.value:
            delta.status = SpecDeltaStatus.SUPERSEDED.value


async def complete_revision_if_needed(
    session: AsyncSession,
    execution: Execution,
    new_subject_id: uuid.UUID,
    ctx: CommandContext,
) -> None:
    approval_id = await revision_approval_id_from_execution(session, execution)
    if approval_id is None:
        return
    approval = await session.get(Approval, approval_id)
    if approval is None:
        return
    old_subject_id = approval.subject_id
    await _supersede_subject(session, approval, old_subject_id)
    await append_domain_event(
        session,
        aggregate_type="revision",
        aggregate_id=approval_id,
        event_type="revision.completed",
        payload={
            "approval_id": str(approval_id),
            "old_subject_id": str(old_subject_id),
            "new_subject_id": str(new_subject_id),
        },
        actor_id=ctx.actor.id,
        correlation_id=ctx.correlation_id,
        project_id=approval.project_id,
        delivery_cycle_id=approval.delivery_cycle_id,
    )
