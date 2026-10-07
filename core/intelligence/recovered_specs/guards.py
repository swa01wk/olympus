from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.domain.delivery_cycles.models import DeliveryCycle
from core.domain.enums import TaskStatus
from core.domain.tasks.models import Task
from core.intelligence.brownfield.enums import RecoveryProposalStatus
from core.intelligence.brownfield.models import RecoveryProposal
from core.intelligence.code_index.enums import IndexVersionStatus
from core.intelligence.code_index.models import CodeIndexVersion
from core.state.guards import GuardResult
from core.traceability.models import RepositoryIndexPointer


async def canonical_repository_index_ready(
    session: AsyncSession,
    cycle: DeliveryCycle,
    _ctx: Any,
) -> GuardResult:
    if cycle.repository_id is None or cycle.base_sha is None:
        return GuardResult(ok=False, reasons=("BASE_SHA_MISSING",))
    pointer = await session.get(RepositoryIndexPointer, cycle.repository_id)
    if pointer is None or pointer.canonical_index_version_id is None:
        return GuardResult(ok=False, reasons=("CANONICAL_POINTER_MISSING",))
    version = await session.get(CodeIndexVersion, pointer.canonical_index_version_id)
    if version is None or version.status != IndexVersionStatus.READY:
        return GuardResult(ok=False, reasons=("INDEX_NOT_READY",))
    if version.commit_sha != cycle.base_sha:
        return GuardResult(ok=False, reasons=("INDEX_SHA_MISMATCH",))
    return GuardResult(ok=True)


async def recovery_proposal_persisted(
    session: AsyncSession,
    cycle: DeliveryCycle,
    _ctx: Any,
) -> GuardResult:
    proposal = (
        await session.execute(
            select(RecoveryProposal)
            .where(
                RecoveryProposal.delivery_cycle_id == cycle.id,
                RecoveryProposal.status == RecoveryProposalStatus.VALIDATED,
            )
            .order_by(RecoveryProposal.created_at.desc())
            .limit(1)
        )
    ).scalar_one_or_none()
    if proposal is None:
        return GuardResult(ok=False, reasons=("RECOVERY_PROPOSAL_MISSING",))
    feature_ids = proposal.feature_execution_ids or []
    if not feature_ids:
        return GuardResult(ok=False, reasons=("RECOVERY_FEATURES_MISSING",))
    for exec_id in feature_ids:
        from core.domain.executions.models import Execution

        execution = await session.get(Execution, uuid.UUID(str(exec_id)))
        if execution is None:
            return GuardResult(ok=False, reasons=(f"EXECUTION_MISSING:{exec_id}",))
        task = await session.get(Task, execution.task_id)
        if task is None or task.status not in (
            TaskStatus.COMPLETED,
            TaskStatus.FAILED,
            TaskStatus.CANCELLED,
        ):
            return GuardResult(
                ok=False, reasons=(f"SCOUT_TASK_NOT_TERMINAL:{task.status if task else 'missing'}",)
            )
    return GuardResult(ok=True)
