from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.commands.context import CommandContext
from core.domain.enums import CheckpointResolution, ExecutionStatus, TaskStatus
from core.domain.executions.models import Checkpoint, Clarification, Execution, ExecutionSnapshot
from core.domain.tasks.models import Task
from core.execution.continuation import build_continuation_package
from core.execution.service import ExecutionService
from core.execution.snapshots.builder import SnapshotBuilder
from core.scheduler.admission import AdmissionService
from core.state.transition_service import TransitionService


@dataclass(frozen=True)
class ResumeDecision:
    action: str
    execution_id: uuid.UUID
    continuation: dict[str, object] | None = None


class ResumeService:
    def __init__(
        self,
        *,
        executions: ExecutionService | None = None,
        transitions: TransitionService | None = None,
    ) -> None:
        self._executions = executions or ExecutionService()
        self._transitions = transitions or TransitionService()

    async def on_clarification_answered(
        self,
        session: AsyncSession,
        clarification_id: uuid.UUID,
        ctx: CommandContext,
    ) -> ResumeDecision:
        clarification = await session.get(Clarification, clarification_id)
        if clarification is None or clarification.execution_id is None:
            raise ValueError("clarification missing")
        execution = await session.get(Execution, clarification.execution_id)
        if execution is None:
            raise ValueError("execution missing")
        task = await session.get(Task, execution.task_id)
        if task is None:
            raise ValueError("task missing")
        terminal_exec = {
            ExecutionStatus.COMPLETED,
            ExecutionStatus.FAILED,
            ExecutionStatus.CANCELLED,
            ExecutionStatus.STALE,
        }
        if task.status == TaskStatus.COMPLETED or execution.status in terminal_exec:
            return ResumeDecision(action="ALREADY_COMPLETE", execution_id=execution.id)
        if task.status != TaskStatus.BLOCKED:
            return ResumeDecision(action="NO_RESUME", execution_id=execution.id)
        cp_result = await session.execute(
            select(Checkpoint)
            .where(Checkpoint.execution_id == execution.id)
            .order_by(Checkpoint.created_at.desc())
            .limit(1)
        )
        checkpoint = cp_result.scalar_one_or_none()
        original = await session.get(ExecutionSnapshot, execution.snapshot_id)
        if checkpoint is None:
            if original is None:
                raise ValueError("checkpoint missing")
            if clarification.answer is None:
                raise ValueError("checkpoint missing")
            pending: dict[str, object] = {
                "type": "clarification",
                "question": clarification.question or "",
            }
            package = await build_continuation_package(
                session,
                execution,
                original,
                pending=pending,
                progress_summary=clarification.question or "",
                resolution={"answer": clarification.answer},
            )
            await self._transitions.transition(
                session,
                "task",
                execution.task_id,
                TaskStatus.BLOCKED.value,
                "resume_execution",
                ctx,
            )
            await self._executions.transition(session, execution.id, "resume", ctx)
            return ResumeDecision(
                action="RESUME_SAME",
                execution_id=execution.id,
                continuation=package.model_dump(mode="json"),
            )

        original_hash = original.snapshot_hash if original else ""
        new_hash = await SnapshotBuilder().preview_hash(session, execution)
        if new_hash != original_hash:
            checkpoint.resolution = CheckpointResolution.NEW_EXECUTION
            checkpoint.resolved_at = datetime.now(UTC)
            await self._executions.transition(session, execution.id, "stale", ctx)
            await self._transitions.transition(
                session,
                "task",
                execution.task_id,
                TaskStatus.BLOCKED.value,
                "unblock",
                ctx,
            )
            new_exec = await AdmissionService().admit_task(session, execution.task_id, ctx)
            new_exec.previous_execution_id = execution.id
            await session.flush()
            return ResumeDecision(action="NEW_EXECUTION", execution_id=new_exec.id)

        checkpoint.resolution = CheckpointResolution.RESUME_SAME
        checkpoint.resolved_at = datetime.now(UTC)
        cont = dict(checkpoint.continuation)
        cont["resolution"] = {"answer": clarification.answer}
        await self._transitions.transition(
            session,
            "task",
            execution.task_id,
            TaskStatus.BLOCKED.value,
            "resume_execution",
            ctx,
        )
        await self._executions.transition(
            session,
            execution.id,
            "resume",
            ctx,
        )
        return ResumeDecision(
            action="RESUME_SAME",
            execution_id=execution.id,
            continuation=cont,
        )
