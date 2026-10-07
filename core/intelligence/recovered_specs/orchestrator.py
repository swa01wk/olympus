from __future__ import annotations

import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from core.commands.context import CommandContext
from core.domain.delivery_cycles.models import DeliveryCycle
from core.domain.enums import TaskContractStatus, TaskOrigin, WorkType
from core.domain.task_contracts.models import TaskContract
from core.domain.task_contracts.schemas import TaskContractBody, VersionedRef
from core.domain.tasks.models import TaskDependency
from core.domain.tasks.service import TaskService
from core.intelligence.code_index.canonical_service import CanonicalIndexService
from core.intelligence.repository.discovery import RepositoryDiscoveryService
from core.traceability.models import RepositoryIndexPointer


class BrownfieldOrchestrator:
    async def run_code_index_stage(
        self,
        session: AsyncSession,
        cycle_id: uuid.UUID,
        ctx: CommandContext,
    ) -> dict[str, str]:
        cycle = await session.get(DeliveryCycle, cycle_id)
        if cycle is None or cycle.repository_id is None:
            raise ValueError("cycle missing repository")
        sha = cycle.base_sha
        if sha is None:
            from core.domain.repositories.models import Repository

            repo = await session.get(Repository, cycle.repository_id)
            sha = repo.canonical_commit if repo else None
        if sha is None:
            raise ValueError("base sha missing")
        await RepositoryDiscoveryService().discover(
            session, cycle.repository_id, cycle_id, sha, ctx
        )
        version = await CanonicalIndexService().promote_repository_snapshot(
            session, cycle.repository_id, sha, ctx
        )
        pointer = await session.get(RepositoryIndexPointer, cycle.repository_id)
        if pointer is None:
            pointer = RepositoryIndexPointer(repository_id=cycle.repository_id)
            session.add(pointer)
        pointer.canonical_index_version_id = version.id
        await session.flush()
        return {"index_version_id": str(version.id), "commit_sha": sha}

    async def run_spec_recovery_stage(
        self,
        session: AsyncSession,
        cycle_id: uuid.UUID,
        ctx: CommandContext,
    ) -> dict[str, str]:
        cycle = await session.get(DeliveryCycle, cycle_id)
        if cycle is None:
            raise ValueError("cycle missing")
        task = await TaskService().create_task(
            session,
            cycle_id,
            "Run existing repository tests",
            WorkType.VERIFICATION,
            TaskOrigin.CONTROL_PLANE,
            ctx,
        )
        body = TaskContractBody(
            objective="Execute existing pytest suite at onboarding SHA",
            work_type=WorkType.VERIFICATION,
            inputs=[VersionedRef(ref_type="DELIVERY_CYCLE", ref_id=cycle_id)],
            repository_id=cycle.repository_id,
            executor_kind="DETERMINISTIC",
            deterministic_executor="brownfield.run_existing_tests",
            required_outputs=["artifact:TEST_RUN"],
        )
        contract = TaskContract(
            task_id=task.id,
            key="v1",
            version=1,
            status=TaskContractStatus.ISSUED,
            body=body.model_dump(mode="json"),
            content_hash=f"brownfield-tests-{cycle_id}",
            compiled_by="brownfield",
        )
        session.add(contract)
        await session.flush()
        task.current_contract_id = contract.id
        await TaskService().mark_ready(session, task.id, ctx)
        return {"tests_task_id": str(task.id)}

    async def schedule_survey(
        self,
        session: AsyncSession,
        cycle_id: uuid.UUID,
        ctx: CommandContext,
    ) -> dict[str, str]:
        task = await TaskService().create_task(
            session,
            cycle_id,
            "Scout repository survey",
            WorkType.ANALYSIS,
            TaskOrigin.CONTROL_PLANE,
            ctx,
        )
        cycle = await session.get(DeliveryCycle, cycle_id)
        body = TaskContractBody(
            objective="Survey repository and propose recovered product structure",
            work_type=WorkType.ANALYSIS,
            inputs=[VersionedRef(ref_type="DELIVERY_CYCLE", ref_id=cycle_id)],
            repository_id=cycle.repository_id if cycle else None,
            executor_kind="AGENT_RUNTIME",
            agent_profile="scout.survey",
            deterministic_executor=None,
            model_alias="repository_reasoning",
            required_outputs=["artifact:REPOSITORY_SURVEY"],
        )
        contract = TaskContract(
            task_id=task.id,
            key="v1",
            version=1,
            status=TaskContractStatus.ISSUED,
            body=body.model_dump(mode="json"),
            content_hash=f"scout-survey-{cycle_id}",
            compiled_by="brownfield",
        )
        session.add(contract)
        await session.flush()
        task.current_contract_id = contract.id
        await TaskService().mark_ready(session, task.id, ctx)
        return {"task_id": str(task.id), "contract_id": str(contract.id)}

    async def schedule_recover_feature_tasks(
        self,
        session: AsyncSession,
        cycle_id: uuid.UUID,
        feature_refs: list[str],
        survey_task_id: uuid.UUID,
        ctx: CommandContext,
    ) -> list[str]:
        cycle = await session.get(DeliveryCycle, cycle_id)
        task_ids: list[str] = []
        for ref in feature_refs:
            task = await TaskService().create_task(
                session,
                cycle_id,
                f"Recover feature {ref}",
                WorkType.ANALYSIS,
                TaskOrigin.CONTROL_PLANE,
                ctx,
            )
            session.add(
                TaskDependency(
                    task_id=task.id, depends_on_task_id=survey_task_id, kind="FINISH_TO_START"
                )
            )
            body = TaskContractBody(
                objective=f"Recover specification for feature draft {ref}",
                work_type=WorkType.ANALYSIS,
                inputs=[VersionedRef(ref_type="DELIVERY_CYCLE", ref_id=cycle_id)],
                repository_id=cycle.repository_id if cycle else None,
                executor_kind="AGENT_RUNTIME",
                agent_profile="scout.recover_feature",
                model_alias="repository_reasoning",
                required_outputs=["artifact:RECOVERED_FEATURE_SPEC"],
            )
            contract = TaskContract(
                task_id=task.id,
                key="v1",
                version=1,
                status=TaskContractStatus.ISSUED,
                body=body.model_dump(mode="json"),
                content_hash=f"scout-recover-{ref}-{cycle_id}",
                compiled_by="brownfield",
            )
            session.add(contract)
            await session.flush()
            task.current_contract_id = contract.id
            await TaskService().mark_ready(session, task.id, ctx)
            task_ids.append(str(task.id))
        return task_ids
