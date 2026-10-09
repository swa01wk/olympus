from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.commands.context import CommandContext
from core.domain.canonical_json import sha256_hex
from core.domain.delivery_cycles.models import DeliveryCycle
from core.domain.enums import (
    SpecKind,
    SpecStatus,
    TaskContractStatus,
    TaskOrigin,
    TaskStatus,
    WorkType,
)
from core.domain.task_contracts.models import TaskContract
from core.domain.task_contracts.schemas import TaskContractBody, VersionedRef
from core.domain.tasks.models import Task
from core.domain.tasks.service import TaskService
from core.intelligence.baselines.characterization_context import build_characterization_snapshot
from core.intelligence.baselines.execution import BaselineExecutionService
from core.intelligence.baselines.proposals import BaselineProposalService
from core.product_model.models import AcceptanceCriterion, FeatureSpec

_CHARACTERIZE_PREFIX = "Characterize "
_EXECUTE_TITLE = "Execute baseline checks at onboarding SHA"
_SETTLED = frozenset({TaskStatus.COMPLETED, TaskStatus.FAILED, TaskStatus.CANCELLED})


class BaselineOrchestrator:
    async def run_baseline_stage(
        self,
        session: AsyncSession,
        cycle_id: uuid.UUID,
        ctx: CommandContext,
    ) -> dict[str, str]:
        await BaselineProposalService().propose_for_cycle(session, cycle_id, ctx)
        characterize_ids = await self._schedule_characterization(session, cycle_id, ctx)
        if characterize_ids:
            # Execution runs once every characterize task settles, so authored checks
            # are proposed before the onboarding-SHA run.
            return {"characterize_task_ids": ",".join(characterize_ids)}
        exec_task = await self._schedule_baseline_execution(session, cycle_id, ctx)
        return {"baseline_execution_task_id": str(exec_task.id)}

    async def schedule_execution_if_characterized(
        self,
        session: AsyncSession,
        cycle_id: uuid.UUID,
        ctx: CommandContext,
    ) -> Task | None:
        rows = (
            await session.execute(
                select(Task.title, Task.status, Task.created_at).where(
                    Task.delivery_cycle_id == cycle_id,
                    Task.title.startswith(_CHARACTERIZE_PREFIX)
                    | Task.title.startswith(_EXECUTE_TITLE),
                )
            )
        ).all()
        characterize = [r for r in rows if r.title.startswith(_CHARACTERIZE_PREFIX)]
        if not characterize or any(r.status not in _SETTLED for r in characterize):
            return None
        newest = max(r.created_at for r in characterize)
        if any(r.title == _EXECUTE_TITLE and r.created_at >= newest for r in rows):
            return None
        return await self._schedule_baseline_execution(session, cycle_id, ctx)

    async def _schedule_characterization(
        self,
        session: AsyncSession,
        cycle_id: uuid.UUID,
        ctx: CommandContext,
    ) -> list[str]:
        cycle = await session.get(DeliveryCycle, cycle_id)
        if cycle is None:
            return []
        scheduled: list[str] = []
        specs = (
            (
                await session.execute(
                    select(FeatureSpec).where(
                        FeatureSpec.project_id == cycle.project_id,
                        FeatureSpec.spec_kind == SpecKind.RECOVERED,
                        FeatureSpec.status == SpecStatus.PROPOSED,
                    )
                )
            )
            .scalars()
            .all()
        )
        for spec in specs:
            acs = (
                (
                    await session.execute(
                        select(AcceptanceCriterion).where(
                            AcceptanceCriterion.feature_spec_id == spec.id
                        )
                    )
                )
                .scalars()
                .all()
            )
            if not acs:
                continue
            task = await TaskService().create_task(
                session,
                cycle_id,
                f"{_CHARACTERIZE_PREFIX}{spec.lineage_key}",
                WorkType.VERIFICATION,
                TaskOrigin.CONTROL_PLANE,
                ctx,
            )
            snapshot = await build_characterization_snapshot(session, cycle, spec, list(acs))
            body = TaskContractBody(
                objective="Author characterization checks for recovered ACs",
                work_type=WorkType.VERIFICATION,
                inputs=[VersionedRef(ref_type="FEATURE_SPEC", ref_id=spec.id)],
                repository_id=cycle.repository_id,
                executor_kind="AGENT_RUNTIME",
                agent_profile="sentinel.characterize",
                model_alias="verification_planning",
                required_outputs=["artifact:CHARACTERIZATION_PLAN"],
            )
            contract_body = {**body.model_dump(mode="json"), "_snapshot": snapshot}
            contract = TaskContract(
                task_id=task.id,
                key="v1",
                version=1,
                status=TaskContractStatus.ISSUED,
                body=contract_body,
                content_hash=sha256_hex(contract_body),
                compiled_by="baselines",
            )
            session.add(contract)
            await session.flush()
            task.current_contract_id = contract.id
            await TaskService().mark_ready(session, task.id, ctx)
            scheduled.append(str(task.id))
        return scheduled

    async def _schedule_baseline_execution(
        self,
        session: AsyncSession,
        cycle_id: uuid.UUID,
        ctx: CommandContext,
    ) -> Task:
        cycle = await session.get(DeliveryCycle, cycle_id)
        task = await TaskService().create_task(
            session,
            cycle_id,
            _EXECUTE_TITLE,
            WorkType.VERIFICATION,
            TaskOrigin.CONTROL_PLANE,
            ctx,
        )
        body = TaskContractBody(
            objective="Run proposed behavioral baselines at base SHA",
            work_type=WorkType.VERIFICATION,
            inputs=[VersionedRef(ref_type="DELIVERY_CYCLE", ref_id=cycle_id)],
            repository_id=cycle.repository_id if cycle else None,
            executor_kind="DETERMINISTIC",
            deterministic_executor="brownfield.run_baselines",
            required_outputs=["artifact:BASELINE_RUN"],
        )
        contract = TaskContract(
            task_id=task.id,
            key="v1",
            version=1,
            status=TaskContractStatus.ISSUED,
            body=body.model_dump(mode="json"),
            content_hash=f"baselines-{cycle_id}",
            compiled_by="baselines",
        )
        session.add(contract)
        await session.flush()
        task.current_contract_id = contract.id
        await TaskService().mark_ready(session, task.id, ctx)
        return task

    async def after_baseline_execution(
        self,
        session: AsyncSession,
        cycle_id: uuid.UUID,
        execution_id: uuid.UUID,
        ctx: CommandContext,
    ) -> None:
        await BaselineExecutionService().execute_proposed(session, cycle_id, execution_id, ctx)
