from __future__ import annotations

import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from core.commands.context import CommandContext
from core.domain.delivery_cycles.models import DeliveryCycle
from core.domain.enums import CheckpointReason, ClarificationStatus, TaskStatus
from core.domain.executions.models import Checkpoint, Clarification, Execution, ExecutionSnapshot
from core.domain.sequences import next_project_key
from core.execution.continuation import build_continuation_package
from core.execution.leases.manager import LeaseManager
from core.execution.service import ExecutionService
from core.state.transition_service import TransitionService


class CheckpointService:
    def __init__(
        self,
        *,
        executions: ExecutionService | None = None,
        leases: LeaseManager | None = None,
        transitions: TransitionService | None = None,
    ) -> None:
        self._executions = executions or ExecutionService()
        self._leases = leases or LeaseManager()
        self._transitions = transitions or TransitionService()

    async def handle_checkpoint(
        self,
        session: AsyncSession,
        execution: Execution,
        snapshot: ExecutionSnapshot,
        lease_id: uuid.UUID,
        *,
        question: str,
        ctx: CommandContext,
    ) -> Clarification:
        cycle = await session.get(DeliveryCycle, execution.delivery_cycle_id)
        if cycle is None:
            raise ValueError("cycle missing")
        pending: dict[str, object] = {"type": "clarification", "question": question}
        package = await build_continuation_package(
            session, execution, snapshot, pending=pending, progress_summary=question
        )
        clarification = Clarification(
            key=await next_project_key(session, cycle.project_id, "clarification", prefix="CL"),
            project_id=cycle.project_id,
            delivery_cycle_id=execution.delivery_cycle_id,
            execution_id=execution.id,
            question=question,
            context={"execution_id": str(execution.id)},
            options=[],
            blocking=True,
            status=ClarificationStatus.OPEN,
        )
        session.add(clarification)
        await session.flush()
        checkpoint = Checkpoint(
            execution_id=execution.id,
            reason=CheckpointReason.CLARIFICATION,
            pending_ref_type="clarification",
            pending_ref_id=clarification.id,
            continuation=package.model_dump(mode="json"),
        )
        session.add(checkpoint)
        await self._executions.transition(
            session,
            execution.id,
            "checkpoint",
            ctx,
            lease_id=lease_id,
        )
        from core.domain.executions.models import ExecutionLease

        lease_row = await session.get(ExecutionLease, lease_id)
        if lease_row:
            await self._leases.release(session, lease_row)
        await self._transitions.transition(
            session,
            "task",
            execution.task_id,
            TaskStatus.RUNNING.value,
            "checkpoint_blocked",
            ctx,
        )
        return clarification
