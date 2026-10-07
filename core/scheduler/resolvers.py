from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from core.domain.artifacts.models import Artifact
from core.domain.delivery_cycles.models import DeliveryCycle
from core.domain.enums import TaskContractStatus
from core.domain.task_contracts.models import TaskContract
from core.domain.task_contracts.schemas import VersionedRef


class ArtifactRefResolver:
    ref_type = "ARTIFACT"

    async def exists(self, session: AsyncSession, ref: VersionedRef) -> bool:
        row = await session.get(Artifact, ref.ref_id)
        return row is not None

    async def is_current(self, session: AsyncSession, ref: VersionedRef) -> bool:
        row = await session.get(Artifact, ref.ref_id)
        if row is None:
            return False
        if ref.version is None:
            return True
        return ref.version == 1


class DeliveryCycleRefResolver:
    ref_type = "DELIVERY_CYCLE"

    async def exists(self, session: AsyncSession, ref: VersionedRef) -> bool:
        return await session.get(DeliveryCycle, ref.ref_id) is not None

    async def is_current(self, session: AsyncSession, ref: VersionedRef) -> bool:
        return await self.exists(session, ref)


class TaskContractRefResolver:
    ref_type = "TASK_CONTRACT"

    async def exists(self, session: AsyncSession, ref: VersionedRef) -> bool:
        row = await session.get(TaskContract, ref.ref_id)
        return row is not None and row.status == TaskContractStatus.ISSUED

    async def is_current(self, session: AsyncSession, ref: VersionedRef) -> bool:
        row = await session.get(TaskContract, ref.ref_id)
        if row is None or row.status != TaskContractStatus.ISSUED:
            return False
        if ref.version is None:
            return True
        return row.version == ref.version
