from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.domain.artifacts.models import Artifact
from core.domain.executions.models import Execution, ExecutionSnapshot
from core.domain.executions.schemas import ContinuationPackage
from core.domain.task_contracts.models import TaskContract
from core.domain.task_contracts.schemas import VersionedRef


async def build_continuation_package(
    session: AsyncSession,
    execution: Execution,
    snapshot: ExecutionSnapshot,
    *,
    pending: dict[str, object],
    progress_summary: str = "",
    resolution: dict[str, object] | None = None,
) -> ContinuationPackage:
    contract = await session.get(TaskContract, execution.task_contract_id)
    if contract is None:
        raise ValueError("contract missing")
    arts = await session.execute(select(Artifact).where(Artifact.execution_id == execution.id))
    produced = [VersionedRef(ref_type="ARTIFACT", ref_id=a.id, key=a.key) for a in arts.scalars()]
    return ContinuationPackage(
        execution_id=execution.id,
        task_contract_ref=VersionedRef(
            ref_type="TASK_CONTRACT",
            ref_id=contract.id,
            version=contract.version,
            key=contract.key,
        ),
        snapshot_hash=snapshot.snapshot_hash,
        produced_artifacts=produced,
        progress_summary=progress_summary,
        pending=pending,
        resolution=resolution,
    )
