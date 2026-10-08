from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.commands.context import CommandContext
from core.domain.enums import TaskContractStatus, TaskOrigin, WorkType
from core.domain.task_contracts.models import TaskContract
from core.domain.task_contracts.schemas import TaskContractBody, VersionedRef
from core.domain.tasks.service import TaskService
from core.product_model.models import ProductSource
from core.review.context import RevisionContext
from core.review.contract_snapshot import attach_snapshot


class DecompositionOrchestrator:
    async def start_decomposition(
        self,
        session: AsyncSession,
        *,
        source: ProductSource,
        delivery_cycle_id: uuid.UUID,
        ctx: CommandContext,
        revision: RevisionContext | None = None,
    ) -> dict[str, str]:
        task = await TaskService().create_task(
            session,
            delivery_cycle_id,
            f"Decompose {source.title}",
            WorkType.ANALYSIS,
            TaskOrigin.CONTROL_PLANE,
            ctx,
        )
        task.governing_ref_type = "PRODUCT_SOURCE_VERSION"
        task.governing_ref_id = source.id
        body = TaskContractBody(
            objective=(
                f"Decompose product source {source.title} into capabilities, features, and specs"
            ),
            work_type=WorkType.ANALYSIS,
            inputs=[
                VersionedRef(
                    ref_type="ARTIFACT",
                    ref_id=source.text_artifact_id,
                    version=1,
                ),
                VersionedRef(
                    ref_type="PRODUCT_SOURCE_VERSION",
                    ref_id=source.id,
                    version=source.version,
                ),
            ],
            executor_kind="AGENT_RUNTIME",
            agent_profile="kira.decompose",
            model_alias="product_decomposition",
            required_outputs=["artifact:PRODUCT_DECOMPOSITION"],
        )
        contract = TaskContract(
            task_id=task.id,
            key="v1",
            version=1,
            status=TaskContractStatus.ISSUED,
            body=attach_snapshot(body.model_dump(mode="json"), revision=revision),
            content_hash=f"decompose-{source.id}",
            compiled_by="product_model",
        )
        session.add(contract)
        await session.flush()
        task.current_contract_id = contract.id
        await TaskService().mark_ready(session, task.id, ctx)
        return {"task_id": str(task.id), "contract_id": str(contract.id)}

    async def redecompose_after_clarification(
        self,
        session: AsyncSession,
        *,
        delivery_cycle_id: uuid.UUID,
        ctx: CommandContext,
    ) -> dict[str, str] | None:
        from core.domain.delivery_cycles.models import DeliveryCycle

        cycle = await session.get(DeliveryCycle, delivery_cycle_id)
        if cycle is None or cycle.state not in {"DISCOVERY", "PRODUCT_MODEL"}:
            return None
        source = (
            await session.execute(
                select(ProductSource)
                .where(ProductSource.delivery_cycle_id == delivery_cycle_id)
                .order_by(ProductSource.version.desc())
                .limit(1)
            )
        ).scalar_one_or_none()
        if source is None:
            return None
        return await self.start_decomposition(
            session,
            source=source,
            delivery_cycle_id=delivery_cycle_id,
            ctx=ctx,
        )
