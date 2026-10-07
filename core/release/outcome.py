"""DeliveryOutcome builder (ARCH §12.1)."""

from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from core.commands.context import CommandContext
from core.domain.delivery_cycles.models import DeliveryCycle
from core.domain.events.append import append_domain_event
from core.release.models import DeliveryOutcome, Release


class DeliveryOutcomeService:
    async def record_released(
        self,
        session: AsyncSession,
        cycle: DeliveryCycle,
        release: Release,
        ctx: CommandContext,
    ) -> DeliveryOutcome:
        content = {
            "delivery_cycle_id": str(cycle.id),
            "delivery_cycle_key": cycle.key,
            "release_id": str(release.id),
            "release_key": release.key,
            "integrated_sha": release.integrated_sha,
            "manifest_id": str(release.manifest_id) if release.manifest_id else None,
            "tag": release.tag,
        }
        from sqlalchemy import select

        existing = (
            await session.execute(
                select(DeliveryOutcome).where(DeliveryOutcome.delivery_cycle_id == cycle.id)
            )
        ).scalar_one_or_none()
        if existing is not None:
            return existing
        row = DeliveryOutcome(
            delivery_cycle_id=cycle.id,
            content=content,
            result="RELEASED",
        )
        session.add(row)
        await session.flush()
        await append_domain_event(
            session,
            aggregate_type="delivery_cycle",
            aggregate_id=cycle.id,
            event_type="delivery_outcome.recorded",
            payload={"result": "RELEASED", "release_key": release.key},
            actor_id=ctx.actor.id,
            correlation_id=ctx.correlation_id,
            project_id=cycle.project_id,
            delivery_cycle_id=cycle.id,
        )
        return row
