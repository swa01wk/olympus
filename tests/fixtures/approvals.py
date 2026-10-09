"""Human approval helpers for tests that drive gated subjects (RL3)."""

from __future__ import annotations

import uuid

from core.commands.handlers import handle_approval_decide
from core.domain.approvals.models import Approval
from core.domain.canonical_json import sha256_hex
from core.domain.enums import ApprovalStatus, ApprovalType
from core.domain.exceptions import DomainError
from core.planning.models import TaskPlanRow
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from tests.fixtures.brownfield_phase12_harness import ensure_human_approver


async def pending_task_plan_approval(session: AsyncSession, plan: TaskPlanRow) -> Approval | None:
    return (
        await session.execute(
            select(Approval).where(
                Approval.approval_type == ApprovalType.TASK_PLAN,
                Approval.subject_type == "task_plan",
                Approval.subject_id == plan.id,
                Approval.subject_hash == sha256_hex(plan.body or {}),
                Approval.status == ApprovalStatus.PENDING,
            )
        )
    ).scalar_one_or_none()


async def approve_task_plan(
    session: AsyncSession,
    plan_id: uuid.UUID,
    *,
    note: str = "test task plan accept",
) -> TaskPlanRow:
    """Approve the plan's pending TASK_PLAN approval as a human; approval accepts the plan."""
    plan = await session.get(TaskPlanRow, plan_id)
    assert plan is not None, "task plan missing"
    pending = await pending_task_plan_approval(session, plan)
    assert pending is not None, "no PENDING TASK_PLAN approval for plan"
    _human, human_ctx = await ensure_human_approver(session)
    try:
        await handle_approval_decide(
            session,
            human_ctx,
            {
                "approval_id": str(pending.id),
                "decision": ApprovalStatus.APPROVED.value,
                "note": note,
            },
        )
    except DomainError as exc:
        raise AssertionError(
            f"TASK_PLAN approval failed: {exc.code} {exc.message} {exc.details}; plan={plan.body}"
        ) from exc
    await session.refresh(plan)
    return plan
