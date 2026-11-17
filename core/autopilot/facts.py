"""Read-only queries the Autopilot planners use to see where a cycle stands."""

from __future__ import annotations

import uuid
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.domain.approvals.models import Approval
from core.domain.delivery_cycles.models import DeliveryCycle
from core.domain.enums import ApprovalStatus, ClarificationStatus, TaskStatus
from core.domain.executions.models import Clarification, Execution
from core.domain.task_contracts.models import TaskContract
from core.domain.tasks.models import Task

OPEN_TASK_STATUSES = frozenset(
    {
        TaskStatus.DRAFT,
        TaskStatus.BLOCKED,
        TaskStatus.READY,
        TaskStatus.QUEUED,
        TaskStatus.RUNNING,
        TaskStatus.REVALIDATION_REQUIRED,
    }
)

# Chat turns run as tasks too; they never mean the journey itself is busy.
IGNORED_PROFILES = frozenset({"orchestrator.converse"})


@dataclass(frozen=True)
class AgentTask:
    task: Task
    profile: str | None

    @property
    def is_open(self) -> bool:
        return self.task.status in OPEN_TASK_STATUSES

    @property
    def failed(self) -> bool:
        return self.task.status == TaskStatus.FAILED


async def cycle_tasks(session: AsyncSession, cycle_id: uuid.UUID) -> list[AgentTask]:
    """Every task in the cycle with the agent profile of its current contract, oldest first."""
    rows = await session.execute(
        select(Task, TaskContract)
        .outerjoin(TaskContract, TaskContract.id == Task.current_contract_id)
        .where(Task.delivery_cycle_id == cycle_id)
        .order_by(Task.created_at)
    )
    out: list[AgentTask] = []
    for task, contract in rows.all():
        profile = None
        if contract is not None and isinstance(contract.body, dict):
            raw = contract.body.get("agent_profile")
            profile = str(raw) if raw else None
        if profile in IGNORED_PROFILES:
            continue
        out.append(AgentTask(task=task, profile=profile))
    return out


def latest_for(tasks: list[AgentTask], profile: str) -> AgentTask | None:
    matching = [t for t in tasks if t.profile == profile]
    return matching[-1] if matching else None


def open_tasks(tasks: list[AgentTask]) -> list[AgentTask]:
    return [t for t in tasks if t.is_open]


async def failure_reason(session: AsyncSession, task: Task) -> str:
    """Short, readable reason for a failed task (from its latest execution)."""
    row = await session.execute(
        select(Execution)
        .where(Execution.task_id == task.id)
        .order_by(Execution.created_at.desc())
        .limit(1)
    )
    execution = row.scalar_one_or_none()
    detail = execution.failure_detail if execution is not None else None
    if isinstance(detail, dict):
        for key in ("message", "reason", "error", "code"):
            value = detail.get(key)
            if value:
                return str(value)[:500]
        errors = detail.get("errors")
        if isinstance(errors, list) and errors:
            return "Its result failed a check: " + "; ".join(str(e) for e in errors)[:500]
    if task.blocked_reason:
        return task.blocked_reason[:500]
    return "The agent did not finish this step."


async def pending_approvals(session: AsyncSession, cycle: DeliveryCycle) -> list[Approval]:
    rows = await session.execute(
        select(Approval)
        .where(
            Approval.delivery_cycle_id == cycle.id,
            Approval.status == ApprovalStatus.PENDING,
        )
        .order_by(Approval.created_at)
    )
    return list(rows.scalars())


async def open_questions(session: AsyncSession, cycle: DeliveryCycle) -> list[Clarification]:
    rows = await session.execute(
        select(Clarification)
        .where(
            Clarification.delivery_cycle_id == cycle.id,
            Clarification.status == ClarificationStatus.OPEN,
        )
        .order_by(Clarification.key)
    )
    return list(rows.scalars())
