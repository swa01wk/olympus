"""Command-bus handlers for REST-parity generation steps (RL2.9)."""

from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from core.commands.context import CommandContext
from core.domain.exceptions import DomainError
from core.planning.orchestrator import PlanningOrchestrator
from core.product_model.changes.orchestrator import FeatureChangeOrchestrator
from core.release.service import ReleaseService


def _cycle_id(payload: dict[str, Any]) -> uuid.UUID:
    raw = payload.get("cycle_id") or payload.get("delivery_cycle_id")
    if raw is None:
        raise DomainError(code="INVALID_PAYLOAD", message="cycle_id required")
    return uuid.UUID(str(raw))


async def handle_architecture_propose(
    session: AsyncSession,
    ctx: CommandContext,
    payload: dict[str, Any],
) -> dict[str, Any]:
    return await PlanningOrchestrator().start_architecture_proposal(
        session, _cycle_id(payload), ctx
    )


async def handle_implementation_specs_generate(
    session: AsyncSession,
    ctx: CommandContext,
    payload: dict[str, Any],
) -> dict[str, Any]:
    feature_spec_id: uuid.UUID | None = None
    if payload.get("feature_spec_id"):
        feature_spec_id = uuid.UUID(str(payload["feature_spec_id"]))
    tasks = await PlanningOrchestrator().start_implementation_spec_generation(
        session,
        _cycle_id(payload),
        ctx,
        feature_spec_id=feature_spec_id,
    )
    return {"tasks": tasks}


async def handle_task_plan_generate(
    session: AsyncSession,
    ctx: CommandContext,
    payload: dict[str, Any],
) -> dict[str, Any]:
    return await PlanningOrchestrator().start_task_plan_generation(session, _cycle_id(payload), ctx)


async def handle_change_interpretation_rerun(
    session: AsyncSession,
    ctx: CommandContext,
    payload: dict[str, Any],
) -> dict[str, Any]:
    return await FeatureChangeOrchestrator().schedule_change_interpret(
        session, _cycle_id(payload), ctx
    )


async def handle_architecture_delta_propose(
    session: AsyncSession,
    ctx: CommandContext,
    payload: dict[str, Any],
) -> dict[str, Any]:
    return await FeatureChangeOrchestrator().schedule_architecture_delta(
        session, _cycle_id(payload), ctx
    )


async def handle_release_create(
    session: AsyncSession,
    ctx: CommandContext,
    payload: dict[str, Any],
) -> dict[str, Any]:
    release = await ReleaseService().create_release(session, _cycle_id(payload), ctx)
    return {"release_id": str(release.id), "key": release.key}
