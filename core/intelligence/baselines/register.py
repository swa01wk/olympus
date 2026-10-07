from __future__ import annotations

from core.execution.executors.base import ExecutionContext, ExecutorOutcome
from core.execution.executors.deterministic import register_deterministic_executor


def register_baseline_executors() -> None:
    register_deterministic_executor("brownfield.run_baselines", _run_baselines)


async def _run_baselines(ctx: ExecutionContext) -> ExecutorOutcome:
    session = ctx.session
    if session is None:
        return ExecutorOutcome(
            status="FAILED",
            error_code="NO_SESSION",
            error_message="brownfield.run_baselines requires database session",
        )
    from sqlalchemy import select

    from core.commands.context import CommandContext
    from core.domain.actors.models import Actor
    from core.domain.enums import ActorKind
    from core.intelligence.baselines.orchestrator import BaselineOrchestrator

    actor = (
        await session.execute(select(Actor).where(Actor.kind == ActorKind.SYSTEM).limit(1))
    ).scalar_one()
    command_ctx = CommandContext(
        actor=actor,
        correlation_id=str(ctx.execution.id),
    )
    await BaselineOrchestrator().after_baseline_execution(
        session,
        ctx.execution.delivery_cycle_id,
        ctx.execution.id,
        command_ctx,
    )
    return ExecutorOutcome(status="OUTPUT_PRODUCED", output={"status": "completed"})
