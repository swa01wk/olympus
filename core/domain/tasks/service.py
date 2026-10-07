"""Task lifecycle commands, dependency graph, and readiness computation."""

from __future__ import annotations

import uuid

from core.commands.context import CommandContext
from core.domain.enums import TaskOrigin, TaskStatus, WorkType
from core.domain.events.append import append_domain_event
from core.domain.exceptions import DomainError
from core.domain.sequences import next_project_key
from core.domain.tasks.models import Task, TaskDependency
from core.state.transition_service import TransitionService
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession


class TaskService:
    def __init__(self, transitions: TransitionService | None = None) -> None:
        self.transitions = transitions or TransitionService()

    async def create_task(
        self,
        session: AsyncSession,
        delivery_cycle_id: uuid.UUID,
        title: str,
        work_type: WorkType,
        origin: TaskOrigin,
        ctx: CommandContext,
        priority: int = 100,
    ) -> Task:
        from core.domain.delivery_cycles.models import DeliveryCycle

        cycle = await session.get(DeliveryCycle, delivery_cycle_id)
        if cycle is None:
            raise DomainError(code="NOT_FOUND", message="Delivery cycle not found")
        key = await next_project_key(session, cycle.project_id, "task", prefix="T")
        task = Task(
            delivery_cycle_id=delivery_cycle_id,
            key=key,
            title=title,
            work_type=work_type,
            origin=origin,
            status=TaskStatus.DRAFT,
            priority=priority,
        )
        session.add(task)
        await session.flush()
        await append_domain_event(
            session,
            aggregate_type="task",
            aggregate_id=task.id,
            event_type="task.created",
            payload={"key": key, "title": title},
            actor_id=ctx.actor.id,
            correlation_id=ctx.correlation_id,
            project_id=cycle.project_id,
            delivery_cycle_id=delivery_cycle_id,
        )
        return task

    async def add_dependency(
        self,
        session: AsyncSession,
        task_id: uuid.UUID,
        depends_on_task_id: uuid.UUID,
    ) -> None:
        if task_id == depends_on_task_id:
            raise DomainError(code="INVALID_DEPENDENCY", message="Task cannot depend on itself")
        if await self._has_cycle(session, task_id, depends_on_task_id):
            raise DomainError(code="DEPENDENCY_CYCLE", message="Dependency cycle detected")
        session.add(TaskDependency(task_id=task_id, depends_on_task_id=depends_on_task_id))
        await session.flush()

    async def _has_cycle(
        self,
        session: AsyncSession,
        start: uuid.UUID,
        target: uuid.UUID,
    ) -> bool:
        graph: dict[uuid.UUID, list[uuid.UUID]] = {}
        result = await session.execute(select(TaskDependency))
        for row in result.scalars():
            graph.setdefault(row.task_id, []).append(row.depends_on_task_id)
        stack = [target]
        seen: set[uuid.UUID] = set()
        while stack:
            node = stack.pop()
            if node == start:
                return True
            if node in seen:
                continue
            seen.add(node)
            stack.extend(graph.get(node, []))
        return False

    async def mark_ready(
        self,
        session: AsyncSession,
        task_id: uuid.UUID,
        ctx: CommandContext,
    ) -> Task:
        task = await session.get(Task, task_id)
        if task is None:
            raise DomainError(code="NOT_FOUND", message="Task not found")
        deps = await session.execute(
            select(TaskDependency).where(TaskDependency.task_id == task_id)
        )
        incomplete = []
        for dep in deps.scalars():
            other = await session.get(Task, dep.depends_on_task_id)
            if other and other.status != TaskStatus.COMPLETED:
                incomplete.append(str(dep.depends_on_task_id))
        command = "mark_blocked" if incomplete else "mark_ready"
        if incomplete:
            task.blocked_reason = "dependencies_incomplete"
        await self.transitions.transition(
            session,
            "task",
            task_id,
            task.status.value,
            command,
            ctx,
        )
        await session.refresh(task)
        event = "task.blocked" if command == "mark_blocked" else "task.ready"
        from core.domain.delivery_cycles.models import DeliveryCycle

        cycle = await session.get(DeliveryCycle, task.delivery_cycle_id)
        await append_domain_event(
            session,
            aggregate_type="task",
            aggregate_id=task.id,
            event_type=event,
            payload={"status": task.status.value},
            actor_id=ctx.actor.id,
            correlation_id=ctx.correlation_id,
            project_id=cycle.project_id if cycle else None,
            delivery_cycle_id=task.delivery_cycle_id,
        )
        return task

    async def on_dependency_completed(self, session: AsyncSession, task_id: uuid.UUID) -> None:
        task = await session.get(Task, task_id)
        if task is None or task.status != TaskStatus.BLOCKED:
            return
        deps = await session.execute(
            select(TaskDependency).where(TaskDependency.task_id == task_id)
        )
        for dep in deps.scalars():
            other = await session.get(Task, dep.depends_on_task_id)
            if other and other.status != TaskStatus.COMPLETED:
                return
        task.blocked_reason = None
        from core.commands.context import CommandContext
        from core.domain.actors.models import Actor
        from core.domain.enums import ActorKind

        actor = (
            await session.execute(select(Actor).where(Actor.kind == ActorKind.SYSTEM).limit(1))
        ).scalar_one_or_none()
        if actor is None:
            task.status = TaskStatus.READY
            return
        ctx = CommandContext(actor=actor, correlation_id="task-unblock-deps")
        await self.transitions.transition(
            session,
            "task",
            task_id,
            TaskStatus.BLOCKED.value,
            "unblock",
            ctx,
        )
