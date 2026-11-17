"""Autopilot: move delivery cycles forward on their own, pausing only for the person.

The scheduler worker calls :meth:`AutopilotService.tick` every poll. For each cycle with
Autopilot on, the journey planner looks at the cycle and returns one decision. When the
decision carries an action (start an agent step, request a review, run a transition), the
service runs it inside a savepoint. An action that raises is recorded and not run again
until the person asks for a retry, so a broken step never loops.

Autopilot acts as the SYSTEM actor. It never decides approvals, answers questions or runs
human-only commands: those surface as NEEDS_YOU and stay with the person.
"""

from __future__ import annotations

import uuid
from collections.abc import Awaitable, Callable

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from core.autopilot.brownfield import plan_brownfield
from core.autopilot.greenfield import plan_greenfield
from core.autopilot.models import AutopilotState
from core.autopilot.types import Decision, blocked
from core.commands.context import CommandContext
from core.domain.delivery_cycles.models import DeliveryCycle
from core.domain.enums import DeliveryCycleType
from core.domain.events.append import append_domain_event
from core.domain.exceptions import DomainError
from core.observability.logging import get_logger

# Attempts a person's "Try again" grants a failed task (the scheduler stops at max_attempts).
RETRY_ATTEMPTS = 3

Planner = Callable[
    [AsyncSession, DeliveryCycle, CommandContext, AutopilotState], Awaitable[Decision]
]

PLANNERS: dict[DeliveryCycleType, Planner] = {
    DeliveryCycleType.GREENFIELD_BUILD: plan_greenfield,
    DeliveryCycleType.BROWNFIELD_ONBOARDING: plan_brownfield,
}

_log = get_logger("core.autopilot")


def supports(cycle_type: DeliveryCycleType) -> bool:
    return cycle_type in PLANNERS


async def system_context(session: AsyncSession, correlation_id: str) -> CommandContext:
    """Autopilot always acts as the SYSTEM actor, even when a person's request woke it."""
    from core.domain.actors.models import Actor
    from core.domain.enums import ActorKind, ActorRole

    actor = (
        await session.execute(select(Actor).where(Actor.kind == ActorKind.SYSTEM).limit(1))
    ).scalar_one_or_none()
    if actor is None:
        actor = Actor(kind=ActorKind.SYSTEM, name="autopilot", roles=[ActorRole.SYSTEM.value])
        session.add(actor)
        await session.flush()
    return CommandContext(actor=actor, correlation_id=correlation_id)


def _error_text(exc: BaseException) -> str:
    message = getattr(exc, "message", None) or str(exc) or type(exc).__name__
    return str(message)[:1000]


class AutopilotService:
    async def get(self, session: AsyncSession, cycle_id: uuid.UUID) -> AutopilotState | None:
        return await session.get(AutopilotState, cycle_id)

    async def set_enabled(
        self,
        session: AsyncSession,
        cycle_id: uuid.UUID,
        enabled: bool,
        ctx: CommandContext,
    ) -> AutopilotState:
        cycle = await session.get(DeliveryCycle, cycle_id)
        if cycle is None:
            raise DomainError(code="NOT_FOUND", message="Delivery cycle not found")
        if enabled and not supports(cycle.type):
            raise DomainError(
                code="AUTOPILOT_UNSUPPORTED",
                message=f"Autopilot does not support {cycle.type.value} yet",
            )
        state = await session.get(AutopilotState, cycle_id)
        if state is None:
            state = AutopilotState(
                delivery_cycle_id=cycle_id,
                enabled=enabled,
                status="WORKING",
                step="starting",
                message="Starting",
                detail={},
            )
            session.add(state)
        else:
            state.enabled = enabled
        await session.flush()
        if enabled:
            await self._advance_state(
                session, state, await system_context(session, ctx.correlation_id)
            )
        return state

    async def request_retry(
        self,
        session: AsyncSession,
        cycle_id: uuid.UUID,
        ctx: CommandContext,
    ) -> AutopilotState:
        """Retry the step Autopilot stopped at.

        Failed agent tasks are put back to READY with the human-only ``retry_task`` command,
        so ``ctx`` must be the person's context. Steps that failed before any task existed
        are re-run by the planner on the next pass.
        """
        state = await session.get(AutopilotState, cycle_id)
        if state is None:
            raise DomainError(code="NOT_FOUND", message="Autopilot is not on for this cycle")
        task_ids = state.detail.get("task_ids") if isinstance(state.detail, dict) else None
        retry_tasks = state.step == "development" or (
            isinstance(state.detail, dict) and bool(state.detail.get("retry_tasks"))
        )
        if retry_tasks and task_ids:
            from core.domain.enums import TaskStatus
            from core.domain.executions.models import Execution
            from core.domain.tasks.models import Task
            from core.state.transition_service import TransitionService

            for raw in task_ids:
                task = await session.get(Task, uuid.UUID(str(raw)))
                if task is not None and task.status == TaskStatus.FAILED:
                    await TransitionService().transition(
                        session, "task", task.id, TaskStatus.FAILED.value, "retry_task", ctx
                    )
                    # The scheduler refuses a task whose executions reach max_attempts, so a
                    # task that used up its attempts would sit READY forever. A person asking
                    # to try again grants a fresh set of attempts.
                    used = (
                        await session.execute(
                            select(func.count())
                            .select_from(Execution)
                            .where(Execution.task_id == task.id)
                        )
                    ).scalar_one()
                    task.max_attempts = max(task.max_attempts, int(used) + RETRY_ATTEMPTS)
        else:
            state.retry_step = state.step
        state.failed_step = None
        state.last_error = None
        await session.flush()
        return await self._advance_state(
            session, state, await system_context(session, ctx.correlation_id)
        )

    async def tick(self, session: AsyncSession, ctx: CommandContext, limit: int = 25) -> int:
        """Advance every cycle with Autopilot on. Returns how many cycles were looked at."""
        rows = await session.execute(
            select(AutopilotState)
            .where(AutopilotState.enabled.is_(True), AutopilotState.status != "DONE")
            .order_by(AutopilotState.updated_at)
            .limit(limit)
            .with_for_update(skip_locked=True)
        )
        states = list(rows.scalars())
        for state in states:
            await self._advance_state(session, state, ctx)
        return len(states)

    async def advance_as_system(
        self, session: AsyncSession, cycle_id: uuid.UUID, correlation_id: str
    ) -> AutopilotState:
        """Re-plan right away after a person's action (runs as SYSTEM, like a tick)."""
        return await self.advance(session, cycle_id, await system_context(session, correlation_id))

    async def advance(
        self, session: AsyncSession, cycle_id: uuid.UUID, ctx: CommandContext
    ) -> AutopilotState:
        state = await session.get(AutopilotState, cycle_id)
        if state is None:
            raise DomainError(code="NOT_FOUND", message="Autopilot is not on for this cycle")
        return await self._advance_state(session, state, ctx)

    # --- internals ----------------------------------------------------------------------

    async def _advance_state(
        self, session: AsyncSession, state: AutopilotState, ctx: CommandContext
    ) -> AutopilotState:
        cycle = await session.get(DeliveryCycle, state.delivery_cycle_id)
        if cycle is None:
            return state
        if not state.enabled:
            return state
        planner = PLANNERS.get(cycle.type)
        if planner is None:
            decision = blocked("unsupported", f"Autopilot does not support {cycle.type.value} yet")
            await self._record(session, cycle, state, decision, ctx)
            return state

        try:
            async with session.begin_nested():
                decision = await planner(session, cycle, ctx, state)
        except Exception as exc:  # planner bugs must not stop the scheduler tick
            _log.exception("autopilot.plan_failed", delivery_cycle_id=str(cycle.id))
            decision = blocked("internal", f"Autopilot hit an internal error: {_error_text(exc)}")
            await self._record(session, cycle, state, decision, ctx)
            return state

        if decision.action is not None:
            decision = await self._run_action(session, cycle, state, decision, ctx)
        elif decision.step != state.failed_step:
            state.failed_step = None
            state.last_error = None
        if decision.status == "DONE":
            state.retry_step = None
        await self._record(session, cycle, state, decision, ctx)
        return state

    async def _run_action(
        self,
        session: AsyncSession,
        cycle: DeliveryCycle,
        state: AutopilotState,
        decision: Decision,
        ctx: CommandContext,
    ) -> Decision:
        assert decision.action is not None
        retrying = state.retry_step == decision.step
        if state.failed_step == decision.step and not retrying:
            return blocked(
                decision.step,
                f"{decision.message} failed: {state.last_error or 'unknown error'}",
                retryable=True,
            )
        try:
            async with session.begin_nested():
                await decision.action(session, ctx)
        except Exception as exc:
            error = _error_text(exc)
            _log.warning(
                "autopilot.action_failed",
                delivery_cycle_id=str(cycle.id),
                step=decision.step,
                error=error,
            )
            state.failed_step = decision.step
            state.last_error = error
            if retrying:
                state.retry_step = None
            return blocked(decision.step, f"{decision.message} failed: {error}", retryable=True)
        state.failed_step = None
        state.last_error = None
        if retrying:
            state.retry_step = None
        _log.info("autopilot.acted", delivery_cycle_id=str(cycle.id), step=decision.step)
        return Decision(decision.status, decision.step, decision.message, detail=decision.detail)

    async def _record(
        self,
        session: AsyncSession,
        cycle: DeliveryCycle,
        state: AutopilotState,
        decision: Decision,
        ctx: CommandContext,
    ) -> None:
        # The activity log is for people: record a line only when what they see changes.
        changed = state.status != decision.status or state.message != decision.message
        state.status = decision.status
        state.step = decision.step
        state.message = decision.message
        state.detail = dict(decision.detail)
        await session.flush()
        if not changed:
            return
        await append_domain_event(
            session,
            aggregate_type="delivery_cycle",
            aggregate_id=cycle.id,
            event_type="autopilot.updated",
            payload={
                "status": decision.status,
                "step": decision.step,
                "message": decision.message,
            },
            actor_id=ctx.actor.id,
            correlation_id=ctx.correlation_id,
            project_id=cycle.project_id,
            delivery_cycle_id=cycle.id,
        )
