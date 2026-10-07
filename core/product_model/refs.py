from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from core.domain.task_contracts.schemas import VersionedRef
from core.product_model.models import AcceptanceCriterion, FeatureSpec, ProductSource, Requirement


class ProductSourceVersionRefResolver:
    ref_type = "PRODUCT_SOURCE_VERSION"

    async def exists(self, session: AsyncSession, ref: VersionedRef) -> bool:
        row = await session.get(ProductSource, ref.ref_id)
        if row is None:
            return False
        if ref.version is None:
            return True
        return row.version == ref.version

    async def is_current(self, session: AsyncSession, ref: VersionedRef) -> bool:
        return await self.exists(session, ref)


class FeatureSpecRefResolver:
    ref_type = "FEATURE_SPEC"

    async def exists(self, session: AsyncSession, ref: VersionedRef) -> bool:
        row = await session.get(FeatureSpec, ref.ref_id)
        return row is not None

    async def is_current(self, session: AsyncSession, ref: VersionedRef) -> bool:
        row = await session.get(FeatureSpec, ref.ref_id)
        if row is None:
            return False
        if ref.version is None:
            return True
        return row.version == ref.version


class RequirementRefResolver:
    ref_type = "REQUIREMENT"

    async def exists(self, session: AsyncSession, ref: VersionedRef) -> bool:
        row = await session.get(Requirement, ref.ref_id)
        return row is not None

    async def is_current(self, session: AsyncSession, ref: VersionedRef) -> bool:
        return await self.exists(session, ref)


class AcceptanceCriterionRefResolver:
    ref_type = "ACCEPTANCE_CRITERION"

    async def exists(self, session: AsyncSession, ref: VersionedRef) -> bool:
        row = await session.get(AcceptanceCriterion, ref.ref_id)
        return row is not None

    async def is_current(self, session: AsyncSession, ref: VersionedRef) -> bool:
        return await self.exists(session, ref)
