"""Row-locked lifecycle transitions with guards, domain events, and audit in one transaction."""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any, Literal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from core.commands.context import CommandContext
from core.domain.approvals.models import Approval
from core.domain.audit.append import append_audit
from core.domain.delivery_cycles.models import DeliveryCycle
from core.domain.enums import ActorKind, ApprovalStatus, TaskContractStatus, TaskStatus
from core.domain.events.append import append_domain_event
from core.domain.exceptions import GuardFailed, IllegalTransition, StateConflict, Unauthorized
from core.domain.repositories.models import Repository
from core.domain.task_contracts.models import TaskContract
from core.domain.tasks.models import Task
from core.state.effects import run_effect
from core.state.guards import GuardRegistry, guard_registry
from core.state.machines import (
    APPROVAL_MACHINE,
    CONTRACT_MACHINE,
    DELIVERY_CYCLE_MACHINES,
    REPOSITORY_MACHINE,
    TASK_MACHINE,
)
from core.state.types import Edge, Machine

AggregateName = Literal["delivery_cycle", "task", "task_contract", "repository", "approval"]


@dataclass
class TransitionResult:
    aggregate: AggregateName
    aggregate_id: uuid.UUID
    from_state: str
    to_state: str


def _state_field(row: Any) -> str:
    if isinstance(row, Task):
        return row.status.value
    if isinstance(row, TaskContract | Repository | Approval):
        return row.status.value
    if isinstance(row, DeliveryCycle):
        return row.state
    return str(row)


def _set_state(row: Any, value: str) -> None:
    if isinstance(row, Task):
        row.status = TaskStatus(value)
    elif isinstance(row, TaskContract):
        row.status = TaskContractStatus(value)
    elif isinstance(row, Repository):
        from core.domain.enums import RepositoryStatus

        row.status = RepositoryStatus(value)
    elif isinstance(row, Approval):
        row.status = ApprovalStatus(value)
    else:
        row.state = value


def _machine_for(row: Any) -> Machine:
    if isinstance(row, DeliveryCycle):
        return DELIVERY_CYCLE_MACHINES[row.type]
    if isinstance(row, Task):
        return TASK_MACHINE
    if isinstance(row, TaskContract):
        return CONTRACT_MACHINE
    if isinstance(row, Repository):
        return REPOSITORY_MACHINE
    if isinstance(row, Approval):
        return APPROVAL_MACHINE
    raise ValueError("Unknown aggregate")


def _authorize(edge: Edge, ctx: CommandContext) -> None:
    if ctx.actor.kind not in edge.actor_kinds:
        raise Unauthorized(f"Actor kind {ctx.actor.kind} not permitted")
    if ctx.actor.kind == ActorKind.AGENT:
        raise Unauthorized("AGENT actors cannot invoke lifecycle commands")


async def _lock_row(session: AsyncSession, aggregate: AggregateName, id: uuid.UUID) -> Any:
    model_map = {
        "delivery_cycle": DeliveryCycle,
        "task": Task,
        "task_contract": TaskContract,
        "repository": Repository,
        "approval": Approval,
    }
    model = model_map[aggregate]
    model_id = model.id  # type: ignore[attr-defined]
    result = await session.execute(select(model).where(model_id == id).with_for_update())
    row = result.scalar_one_or_none()
    if row is None:
        raise ValueError(f"{aggregate} not found")
    return row


def _snapshot(row: Any) -> dict[str, Any]:
    if isinstance(row, DeliveryCycle):
        return {"state": row.state, "state_version": row.state_version, "base_sha": row.base_sha}
    if isinstance(row, Task):
        return {"status": row.status.value}
    if isinstance(row, Repository):
        return {"status": row.status.value, "state_version": row.state_version}
    if isinstance(row, TaskContract):
        return {"status": row.status.value, "version": row.version}
    if isinstance(row, Approval):
        return {"status": row.status.value}
    return {}


class TransitionService:
    def __init__(self, registry: GuardRegistry | None = None) -> None:
        self.registry = registry or guard_registry

    async def transition(
        self,
        session: AsyncSession,
        aggregate: AggregateName,
        id: uuid.UUID,
        expected_state: str,
        command: str,
        ctx: CommandContext,
        *,
        payload: dict[str, Any] | None = None,
    ) -> TransitionResult:
        from core.observability.instrumentation import command_span

        project_id: str | None = None
        delivery_cycle_id: str | None = None
        if payload:
            project_id = str(payload.get("project_id")) if payload.get("project_id") else None
            delivery_cycle_id = (
                str(payload.get("delivery_cycle_id")) if payload.get("delivery_cycle_id") else None
            )
        with command_span(
            f"{aggregate}.{command}",
            project_id=project_id,
            delivery_cycle_id=delivery_cycle_id,
            correlation_id=ctx.correlation_id,
        ):
            return await self._transition_inner(
                session,
                aggregate,
                id,
                expected_state,
                command,
                ctx,
                payload=payload,
            )

    async def _transition_inner(
        self,
        session: AsyncSession,
        aggregate: AggregateName,
        id: uuid.UUID,
        expected_state: str,
        command: str,
        ctx: CommandContext,
        *,
        payload: dict[str, Any] | None = None,
    ) -> TransitionResult:
        row = await _lock_row(session, aggregate, id)
        current = _state_field(row)
        if current != expected_state:
            raise StateConflict(current=current, expected=expected_state)
        machine = _machine_for(row)
        edge = machine.edge(current, command)
        if edge is None:
            raise IllegalTransition(aggregate=aggregate, state=current, command=command)
        _authorize(edge, ctx)
        guard_results = [await self.registry.evaluate(g, session, row, ctx) for g in edge.guards]
        failed = [r for r in guard_results if not r.ok]
        if failed:
            reasons: list[str] = []
            for r in failed:
                reasons.extend(r.reasons)
            raise GuardFailed(reasons)
        before = _snapshot(row)
        _set_state(row, edge.to)
        if hasattr(row, "state_version"):
            row.state_version += 1
        if aggregate == "delivery_cycle" and edge.to in {
            "CANCELLED",
            "FAILED",
            "COMPLETE",
            "READY",
        }:
            row.closed_at = datetime.now(UTC)
            if payload and "reason" in payload:
                row.terminal_reason = str(payload["reason"])
        for effect in edge.effects:
            await run_effect(effect, session, row, ctx)
        after = _snapshot(row)
        await self._emit_events(session, aggregate, row, command, before, after, ctx, edge)
        if isinstance(row, DeliveryCycle) and edge.to in {"CANCELLED", "FAILED"}:
            from core.integration.canonical_revision import CanonicalRevisionGuardian

            await CanonicalRevisionGuardian().on_cycle_terminal(session, row.id, ctx)
        return TransitionResult(
            aggregate=aggregate,
            aggregate_id=id,
            from_state=current,
            to_state=edge.to,
        )

    async def _emit_events(
        self,
        session: AsyncSession,
        aggregate: AggregateName,
        row: Any,
        command: str,
        before: dict[str, Any],
        after: dict[str, Any],
        ctx: CommandContext,
        edge: Edge,
    ) -> None:
        project_id: uuid.UUID | None = None
        delivery_cycle_id: uuid.UUID | None = None
        event_type = f"{aggregate}.transitioned"
        payload: dict[str, Any] = {
            "command": command,
            "from": before,
            "to": after,
        }
        if isinstance(row, DeliveryCycle):
            project_id = row.project_id
            delivery_cycle_id = row.id
            event_type = "delivery_cycle.transitioned"
            payload["base_sha"] = row.base_sha
        elif isinstance(row, Task):
            delivery_cycle_id = row.delivery_cycle_id
            cycle = await session.get(DeliveryCycle, row.delivery_cycle_id)
            project_id = cycle.project_id if cycle else None
            event_type = "task.transitioned"
        elif isinstance(row, Repository):
            cycle_result = await session.execute(
                select(DeliveryCycle).where(DeliveryCycle.repository_id == row.id).limit(1)
            )
            cycle = cycle_result.scalar_one_or_none()
            project_id = row.project_id
            event_type = "repository.status_changed"
        await append_domain_event(
            session,
            aggregate_type=aggregate,
            aggregate_id=row.id,
            event_type=event_type,
            payload=payload,
            actor_id=ctx.actor.id,
            correlation_id=ctx.correlation_id,
            project_id=project_id,
            delivery_cycle_id=delivery_cycle_id,
        )
        await append_audit(
            session,
            actor_id=ctx.actor.id,
            actor_kind=ctx.actor.kind,
            action="transition.accepted",
            target_type=aggregate,
            target_id=str(row.id),
            correlation_id=ctx.correlation_id,
            before=before,
            after=after,
            command_log_id=ctx.command_log_id,
            project_id=project_id,
        )

    async def record_rejection(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        *,
        aggregate: AggregateName,
        aggregate_id: uuid.UUID,
        command: str,
        reason: str,
        ctx: CommandContext,
    ) -> None:
        async with session_factory() as session, session.begin():
            await append_audit(
                session,
                actor_id=ctx.actor.id,
                actor_kind=ctx.actor.kind,
                action="transition.rejected",
                target_type=aggregate,
                target_id=str(aggregate_id),
                correlation_id=ctx.correlation_id,
                before=None,
                after={"command": command, "reason": reason},
                command_log_id=ctx.command_log_id,
            )
