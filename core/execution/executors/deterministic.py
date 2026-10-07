from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable

from core.execution.executors.base import ExecutionContext, ExecutorOutcome

DeterministicFn = Callable[[ExecutionContext], Awaitable[ExecutorOutcome]]

_REGISTRY: dict[str, DeterministicFn] = {}


def register_deterministic_executor(name: str, fn: DeterministicFn) -> None:
    _REGISTRY[name] = fn


def get_deterministic_executor(name: str) -> DeterministicFn | None:
    return _REGISTRY.get(name)


async def _noop_verify_artifact(ctx: ExecutionContext) -> ExecutorOutcome:
    return ExecutorOutcome(status="OUTPUT_PRODUCED", output={"verified": True})


async def _sleep_past_wall_clock(ctx: ExecutionContext) -> ExecutorOutcome:
    delay = int(ctx.contract.timeouts.get("wall_clock_s", 1)) + 2
    await asyncio.sleep(delay)
    return ExecutorOutcome(status="OUTPUT_PRODUCED", output={"slept": delay})


async def _fail_runtime(ctx: ExecutionContext) -> ExecutorOutcome:
    return ExecutorOutcome(
        status="FAILED",
        error_code="RUNTIME_ERROR",
        error_message="deterministic failure",
    )


def register_builtin_deterministic_executors() -> None:
    register_deterministic_executor("noop.verify_artifact", _noop_verify_artifact)
    register_deterministic_executor("noop.sleep_past_wall_clock", _sleep_past_wall_clock)
    register_deterministic_executor("noop.fail", _fail_runtime)
    from core.assurance.reproduction.register import register_reproduction_executors

    register_reproduction_executors()


class DeterministicExecutor:
    async def execute(self, ctx: ExecutionContext) -> ExecutorOutcome:
        name = ctx.contract.deterministic_executor
        if not name:
            return ExecutorOutcome(
                status="FAILED",
                error_code="MISSING_EXECUTOR",
                error_message="deterministic_executor not set",
            )
        fn = get_deterministic_executor(name)
        if fn is None:
            return ExecutorOutcome(
                status="FAILED",
                error_code="UNKNOWN_EXECUTOR",
                error_message=f"unknown deterministic executor: {name}",
            )
        return await fn(ctx)
