from __future__ import annotations

from core.execution.executors.base import ExecutionContext, ExecutorOutcome
from core.execution.executors.deterministic import register_deterministic_executor


def register_brownfield_executors() -> None:
    from core.intelligence.baselines.register import register_baseline_executors

    register_baseline_executors()
    register_deterministic_executor("brownfield.run_existing_tests", _run_existing_tests)


async def _run_existing_tests(ctx: ExecutionContext) -> ExecutorOutcome:
    session = ctx.session
    if session is None:
        return ExecutorOutcome(
            status="FAILED",
            error_code="NO_SESSION",
            error_message="brownfield.run_existing_tests requires database session",
        )
    from sqlalchemy import select

    from core.commands.context import CommandContext
    from core.domain.actors.models import Actor
    from core.domain.enums import ActorKind
    from core.intelligence.recovered_specs.existing_tests_executor import (
        run_brownfield_existing_tests,
    )

    actor = (
        await session.execute(select(Actor).where(Actor.kind == ActorKind.SYSTEM).limit(1))
    ).scalar_one()
    command_ctx = CommandContext(
        actor=actor,
        correlation_id=str(ctx.execution.id),
    )
    return await run_brownfield_existing_tests(session, ctx, command_ctx)
