from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from core.domain.task_contracts.schemas import VersionedRef
from core.planning.models import Architecture, ImplementationSpec


class ArchitectureRefResolver:
    ref_type = "ARCHITECTURE"

    async def exists(self, session: AsyncSession, ref: VersionedRef) -> bool:
        row = await session.get(Architecture, ref.ref_id)
        if row is None:
            return False
        if ref.version is None:
            return True
        return row.version == ref.version

    async def is_current(self, session: AsyncSession, ref: VersionedRef) -> bool:
        return await self.exists(session, ref)


class ImplementationSpecRefResolver:
    ref_type = "IMPLEMENTATION_SPEC"

    async def exists(self, session: AsyncSession, ref: VersionedRef) -> bool:
        row = await session.get(ImplementationSpec, ref.ref_id)
        if row is None:
            return False
        if ref.version is None:
            return True
        return row.version == ref.version

    async def is_current(self, session: AsyncSession, ref: VersionedRef) -> bool:
        return await self.exists(session, ref)
