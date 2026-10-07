"""Scheduler ref resolvers for defect domain entities."""

from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from core.domain.task_contracts.schemas import VersionedRef
from core.product_model.defects.models import Defect


class DefectRefResolver:
    ref_type = "DEFECT"

    async def exists(self, session: AsyncSession, ref: VersionedRef) -> bool:
        return await session.get(Defect, ref.ref_id) is not None

    async def is_current(self, session: AsyncSession, ref: VersionedRef) -> bool:
        return await self.exists(session, ref)
