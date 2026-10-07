"""Contract ref resolvers for assurance artifacts."""

from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from core.assurance.enums import VerificationPlanStatus
from core.assurance.models import Finding, VerificationPlanRow
from core.domain.task_contracts.schemas import VersionedRef


class FindingRefResolver:
    ref_type = "FINDING"

    async def exists(self, session: AsyncSession, ref: VersionedRef) -> bool:
        return await session.get(Finding, ref.ref_id) is not None

    async def is_current(self, session: AsyncSession, ref: VersionedRef) -> bool:
        return await self.exists(session, ref)


class VerificationPlanRefResolver:
    ref_type = "VERIFICATION_PLAN"

    async def exists(self, session: AsyncSession, ref: VersionedRef) -> bool:
        row = await session.get(VerificationPlanRow, ref.ref_id)
        return row is not None and row.status == VerificationPlanStatus.VALIDATED

    async def is_current(self, session: AsyncSession, ref: VersionedRef) -> bool:
        return await self.exists(session, ref)
