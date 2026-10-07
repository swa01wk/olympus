"""System invariant assertions for recovery and ops endpoints."""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from core.domain.enums import ExecutionStatus, LeaseState
from core.domain.executions.models import Execution, ExecutionLease
from core.domain.tasks.models import Task
from core.security.audit_chain import verify_project_chain


@dataclass
class InvariantReport:
    project_id: uuid.UUID | None
    ok: bool
    violations: list[str] = field(default_factory=list)


async def assert_system_invariants(
    session: AsyncSession,
    project_id: uuid.UUID | None = None,
) -> InvariantReport:
    report = InvariantReport(project_id=project_id, ok=True)

    active_leases = await session.execute(
        select(ExecutionLease.execution_id, func.count())
        .where(ExecutionLease.state == LeaseState.ACTIVE)
        .group_by(ExecutionLease.execution_id)
        .having(func.count() > 1)
    )
    for exec_id, count in active_leases:
        report.ok = False
        report.violations.append(f"multiple ACTIVE leases on execution {exec_id}: {count}")

    if project_id is not None:
        chain = await verify_project_chain(session, project_id)
        if not chain.valid:
            report.ok = False
            report.violations.append(f"audit chain invalid: {chain.message}")

    # Executions terminal or resumable
    resumable_or_terminal = {
        ExecutionStatus.QUEUED,
        ExecutionStatus.LEASED,
        ExecutionStatus.STARTED,
        ExecutionStatus.CHECKPOINTED,
        ExecutionStatus.OUTPUT_PRODUCED,
        ExecutionStatus.VALIDATING,
        ExecutionStatus.COMMITTED,
        ExecutionStatus.COMPLETED,
        ExecutionStatus.FAILED,
        ExecutionStatus.TIMED_OUT,
        ExecutionStatus.CANCELLED,
        ExecutionStatus.STALE,
    }
    bad_exec = await session.execute(
        select(Execution.id, Execution.status).where(
            Execution.status.notin_(list(resumable_or_terminal))
        )
    )
    for eid, status in bad_exec:
        report.ok = False
        report.violations.append(f"execution {eid} in unexpected status {status}")

    _ = Task

    return report
