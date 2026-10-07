"""Contract input ref resolvers for integration artifacts."""

from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from core.domain.task_contracts.schemas import VersionedRef
from core.integration.models import IntegrationCandidate


class IntegrationCandidateRefResolver:
    ref_type = "INTEGRATION_CANDIDATE"

    async def exists(self, session: AsyncSession, ref: VersionedRef) -> bool:
        return await session.get(IntegrationCandidate, ref.ref_id) is not None

    async def is_current(self, session: AsyncSession, ref: VersionedRef) -> bool:
        return await self.exists(session, ref)
