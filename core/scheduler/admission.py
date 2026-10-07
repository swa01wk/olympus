from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.commands.context import CommandContext
from core.domain.delivery_cycles.models import DeliveryCycle
from core.domain.enums import ExecutionStatus, TaskContractStatus, TaskStatus
from core.domain.events.append import append_domain_event
from core.domain.exceptions import DomainError
from core.domain.executions.models import Execution
from core.domain.sequences import next_project_key
from core.domain.task_contracts.models import TaskContract
from core.domain.task_contracts.schemas import parse_task_contract_body
from core.domain.tasks.models import Task
from core.execution.snapshots.base_commit import BaseCommitResolver
from core.scheduler.context_loader import load_eligibility_context, load_task_view
from core.scheduler.eligibility import evaluate
from core.scheduler.refs import RefResolverRegistry, build_default_registry
from core.state.transition_service import TransitionService


class AdmissionService:
    def __init__(
        self,
        *,
        transitions: TransitionService | None = None,
        ref_registry: RefResolverRegistry | None = None,
        base_resolver: BaseCommitResolver | None = None,
    ) -> None:
        self.transitions = transitions or TransitionService()
        self.ref_registry = ref_registry or build_default_registry()
        self.base_resolver = base_resolver or BaseCommitResolver()

    async def admit_batch(
        self,
        session: AsyncSession,
        limit: int,
        ctx: CommandContext,
    ) -> list[uuid.UUID]:
        from core.observability.instrumentation import scheduler_span

        with scheduler_span(correlation_id=ctx.correlation_id):
            return await self._admit_batch_inner(session, limit, ctx)

    async def _admit_batch_inner(
        self,
        session: AsyncSession,
        limit: int,
        ctx: CommandContext,
    ) -> list[uuid.UUID]:
        result = await session.execute(
            select(Task)
            .where(Task.status == TaskStatus.READY)
            .order_by(Task.priority, Task.created_at)
            .limit(limit)
            .with_for_update(skip_locked=True)
        )
        admitted: list[uuid.UUID] = []
        for task in result.scalars():
            exec_id = await self._admit_locked_task(session, task, ctx)
            if exec_id is not None:
                admitted.append(exec_id)
        return admitted

    async def admit_task(
        self,
        session: AsyncSession,
        task_id: uuid.UUID,
        ctx: CommandContext,
    ) -> Execution:
        result = await session.execute(select(Task).where(Task.id == task_id).with_for_update())
        task = result.scalar_one_or_none()
        if task is None:
            raise DomainError(code="NOT_FOUND", message="Task not found")
        exec_id = await self._admit_locked_task(session, task, ctx)
        if exec_id is None:
            elig_ctx = await load_eligibility_context(
                session,
                task,
                ref_registry=self.ref_registry,
                base_resolver=self.base_resolver,
            )
            view = await load_task_view(session, task)
            result_elig = evaluate(view, elig_ctx)
            raise DomainError(
                code="NOT_ELIGIBLE",
                message="Task is not eligible for execution",
                details={"reasons": result_elig.reasons},
            )
        row = await session.get(Execution, exec_id)
        assert row is not None
        return row

    async def _admit_locked_task(
        self,
        session: AsyncSession,
        task: Task,
        ctx: CommandContext,
    ) -> uuid.UUID | None:
        if task.status != TaskStatus.READY:
            return None
        elig_ctx = await load_eligibility_context(
            session,
            task,
            ref_registry=self.ref_registry,
            base_resolver=self.base_resolver,
        )
        view = await load_task_view(session, task)
        elig = evaluate(view, elig_ctx)
        if not elig.eligible:
            return None
        if task.current_contract_id is None:
            return None
        contract = await session.get(TaskContract, task.current_contract_id)
        if contract is None or contract.status != TaskContractStatus.ISSUED:
            return None
        body = parse_task_contract_body(contract.body)
        cycle = await session.get(DeliveryCycle, task.delivery_cycle_id)
        if cycle is None:
            return None
        attempt = elig_ctx.attempt_count + 1
        key = await next_project_key(session, cycle.project_id, "execution", prefix="EX")
        execution = Execution(
            key=key,
            task_id=task.id,
            delivery_cycle_id=task.delivery_cycle_id,
            task_contract_id=contract.id,
            attempt_number=attempt,
            status=ExecutionStatus.QUEUED,
            executor_kind=body.executor_kind,
            agent_profile=body.agent_profile,
        )
        session.add(execution)
        await session.flush()
        await self.transitions.transition(
            session,
            "task",
            task.id,
            TaskStatus.READY.value,
            "enqueue",
            ctx,
        )
        await append_domain_event(
            session,
            aggregate_type="execution",
            aggregate_id=execution.id,
            event_type="execution.created",
            payload={"task_id": str(task.id), "attempt_number": attempt, "key": key},
            actor_id=ctx.actor.id,
            correlation_id=ctx.correlation_id,
            project_id=cycle.project_id,
            delivery_cycle_id=task.delivery_cycle_id,
        )
        await append_domain_event(
            session,
            aggregate_type="task",
            aggregate_id=task.id,
            event_type="task.queued",
            payload={"execution_id": str(execution.id)},
            actor_id=ctx.actor.id,
            correlation_id=ctx.correlation_id,
            project_id=cycle.project_id,
            delivery_cycle_id=task.delivery_cycle_id,
        )
        return execution.id
