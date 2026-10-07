"""Read-only lifecycle guard preview (no locks, no writes)."""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from core.commands.context import CommandContext
from core.domain.delivery_cycles.models import DeliveryCycle
from core.domain.enums import ActorKind
from core.domain.exceptions import Unauthorized
from core.state.guards import GuardRegistry, guard_registry
from core.state.machines import DELIVERY_CYCLE_MACHINES
from core.state.types import Edge


@dataclass(frozen=True)
class GuardPreviewResult:
    guard_id: str
    ok: bool
    reasons: tuple[str, ...]


@dataclass(frozen=True)
class TransitionPreview:
    command: str
    to_state: str
    allowed: bool
    guard_results: tuple[GuardPreviewResult, ...]
    authorization_denied: bool = False


def _authorize(edge: Edge, ctx: CommandContext) -> None:
    if ctx.actor.kind not in edge.actor_kinds:
        raise Unauthorized(f"Actor kind {ctx.actor.kind} not permitted")
    if ctx.actor.kind == ActorKind.AGENT:
        raise Unauthorized("AGENT actors cannot invoke lifecycle commands")


class TransitionPreviewService:
    """Dry-run transition evaluation."""

    def __init__(self, registry: GuardRegistry | None = None) -> None:
        self.registry = registry or guard_registry

    async def preview(
        self,
        session: AsyncSession,
        aggregate: str,
        aggregate_id: uuid.UUID,
        ctx: CommandContext,
    ) -> list[TransitionPreview]:
        if aggregate != "delivery_cycle":
            return []
        cycle = await session.get(DeliveryCycle, aggregate_id)
        if cycle is None:
            return []
        return await self.preview_delivery_cycle(session, cycle, ctx)

    async def preview_delivery_cycle(
        self,
        session: AsyncSession,
        cycle: DeliveryCycle,
        ctx: CommandContext,
    ) -> list[TransitionPreview]:
        machine = DELIVERY_CYCLE_MACHINES[cycle.type]
        current = cycle.state
        previews: list[TransitionPreview] = []
        for (state, command), edge in machine.edges.items():
            if state != current:
                continue
            auth_denied = False
            try:
                _authorize(edge, ctx)
            except Unauthorized:
                auth_denied = True
            guard_results: list[GuardPreviewResult] = []
            for guard_id in edge.guards:
                result = await self.registry.evaluate(guard_id, session, cycle, ctx)
                guard_results.append(
                    GuardPreviewResult(
                        guard_id=guard_id,
                        ok=result.ok,
                        reasons=result.reasons,
                    )
                )
            allowed = (not auth_denied) and all(g.ok for g in guard_results)
            previews.append(
                TransitionPreview(
                    command=command,
                    to_state=edge.to,
                    allowed=allowed,
                    guard_results=tuple(guard_results),
                    authorization_denied=auth_denied,
                )
            )
        return previews


def preview_to_api(row: TransitionPreview) -> dict[str, Any]:
    reasons: list[str] = []
    if row.authorization_denied:
        reasons.append("ACTOR_NOT_PERMITTED")
    for g in row.guard_results:
        if not g.ok:
            reasons.extend(g.reasons)
    return {
        "command": row.command,
        "to_state": row.to_state,
        "target_state": row.to_state,
        "allowed": row.allowed,
        "guard_preview": reasons,
        "guard_results": [
            {"guard_id": g.guard_id, "ok": g.ok, "reasons": list(g.reasons)}
            for g in row.guard_results
        ],
        "authorization_denied": row.authorization_denied,
    }
