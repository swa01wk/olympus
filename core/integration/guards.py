"""Delivery-cycle guards for integration phase."""

from __future__ import annotations

from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.assurance.models import Finding
from core.domain.delivery_cycles.models import DeliveryCycle
from core.domain.enums import TaskOrigin, TaskStatus, WorkType
from core.domain.repositories.models import Repository
from core.domain.tasks.models import Task
from core.integration.enums import FindingStatus, ICStatus
from core.integration.models import IntegrationCandidate
from core.intelligence.code_index.models import CodeIndexVersion
from core.state.guards import GuardResult
from core.traceability.models import RepositoryIndexPointer


async def all_code_tasks_completed(
    session: AsyncSession,
    cycle: DeliveryCycle,
    _ctx: Any,
) -> GuardResult:
    origins = (TaskOrigin.IMPLEMENTATION_PLAN, TaskOrigin.REMEDIATION, TaskOrigin.REPAIR)
    tasks = await session.execute(
        select(Task).where(
            Task.delivery_cycle_id == cycle.id,
            Task.work_type == WorkType.CODE_CHANGE,
            Task.origin.in_(origins),
        )
    )
    reasons: list[str] = []
    for task in tasks.scalars():
        if task.status not in (TaskStatus.COMPLETED, TaskStatus.CANCELLED):
            reasons.append(f"TASK_INCOMPLETE:{task.key}")
    return GuardResult(ok=not reasons, reasons=tuple(reasons))


async def ic_ready_and_canonical_index_current(
    session: AsyncSession,
    cycle: DeliveryCycle,
    _ctx: Any,
) -> GuardResult:
    if cycle.repository_id is None:
        return GuardResult(ok=False, reasons=("REPOSITORY_NOT_BOUND",))
    ic = await session.execute(
        select(IntegrationCandidate)
        .where(
            IntegrationCandidate.delivery_cycle_id == cycle.id,
            IntegrationCandidate.status == ICStatus.READY,
        )
        .order_by(IntegrationCandidate.created_at.desc())
        .limit(1)
    )
    row = ic.scalar_one_or_none()
    if row is None or row.integrated_sha is None:
        return GuardResult(ok=False, reasons=("IC_NOT_READY",))
    repo = await session.get(Repository, cycle.repository_id)
    if repo is None or repo.canonical_commit != row.integrated_sha:
        return GuardResult(ok=False, reasons=("CANONICAL_COMMIT_MISMATCH",))
    pointer = await session.get(RepositoryIndexPointer, cycle.repository_id)
    if pointer is None or pointer.canonical_index_version_id is None:
        return GuardResult(ok=False, reasons=("CANONICAL_POINTER_MISSING",))
    version = await session.get(CodeIndexVersion, pointer.canonical_index_version_id)
    if version is None or version.commit_sha != row.integrated_sha:
        return GuardResult(ok=False, reasons=("POINTER_SHA_MISMATCH",))
    return GuardResult(ok=True)


async def remediation_tasks_exist(
    session: AsyncSession,
    cycle: DeliveryCycle,
    _ctx: Any,
) -> GuardResult:
    findings = await session.execute(
        select(Finding).where(
            Finding.delivery_cycle_id == cycle.id,
            Finding.status.in_([FindingStatus.OPEN, FindingStatus.IN_REMEDIATION]),
            Finding.blocking.is_(True),
        )
    )
    for finding in findings.scalars():
        if finding.remediation_task_id is None:
            continue
        task = await session.get(Task, finding.remediation_task_id)
        if task and task.status in (TaskStatus.READY, TaskStatus.QUEUED):
            return GuardResult(ok=True)
    return GuardResult(ok=False, reasons=("NO_REMEDIATION_TASKS",))
