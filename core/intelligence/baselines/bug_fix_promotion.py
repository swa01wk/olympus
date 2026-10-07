"""Release R3: promote regression test to baseline."""

from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from core.commands.context import CommandContext
from core.domain.delivery_cycles.models import DeliveryCycle
from core.domain.enums import DeliveryCycleType
from core.product_model.defects.models import Defect
from core.release.models import Release


class BugFixBaselinePromotionService:
    async def on_release(
        self,
        session: AsyncSession,
        release: Release,
        ctx: CommandContext,
    ) -> None:
        del ctx
        cycle = await session.get(DeliveryCycle, release.delivery_cycle_id)
        if cycle is None or cycle.type != DeliveryCycleType.BUG_FIX:
            return
        from sqlalchemy import select

        defect = (
            await session.execute(select(Defect).where(Defect.delivery_cycle_id == cycle.id))
        ).scalar_one_or_none()
        if defect is None:
            return
        defect.status = "RELEASED"
        await session.flush()
