"""Live LLM greenfield path for chained MVP DC-001 (no planning seeds)."""

from __future__ import annotations

import os
import uuid
from contextlib import suppress
from unittest.mock import patch

from core.commands.context import CommandContext
from core.domain.delivery_cycles.models import DeliveryCycle
from core.domain.enums import ExecutionStatus, SpecStatus, TaskStatus, WorkType
from core.domain.executions.models import Execution
from core.domain.projects.models import Project
from core.domain.repositories.models import Repository
from core.domain.tasks.models import Task
from core.execution.worker import ExecutionWorker
from core.planning.models import Architecture, ImplementationSpec, TaskPlanRow
from core.runtime.model_router import build_providers
from core.scheduler.admission import AdmissionService
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker
from tests.fixtures.planning_workflow_harness import build_task_plan_for_cycle, ensure_system_actor
from tests.journey.chained.worker_drain import drain_until_code_change_tasks_terminal
from tests.journey.feature_change_helpers import (
    accept_task_plan_if_proposed,
    wait_for_task_plan_accepted,
    wait_for_task_plan_proposed,
)
from tests.journey.greenfield_dev import complete_implementation_tasks_with_supportdesk_r1


async def _run_task_to_completion(
    factory: async_sessionmaker[AsyncSession],
    task_id: str,
    *,
    correlation_prefix: str,
    max_rounds: int = 40,
) -> None:
    async with factory() as session, session.begin():
        actor = await ensure_system_actor(session)
        ctx = CommandContext(actor=actor, correlation_id=f"{correlation_prefix}-adm")
        execution = await AdmissionService().admit_task(session, uuid.UUID(task_id), ctx)
        execution_id = execution.id

    with patch("core.runtime.model_router.build_providers", side_effect=build_providers):
        async with factory() as session, session.begin():
            actor = await ensure_system_actor(session)
            ctx = CommandContext(actor=actor, correlation_id=f"{correlation_prefix}-run")
            worker = ExecutionWorker(worker_id=f"{correlation_prefix}-{uuid.uuid4().hex[:4]}")
            for _ in range(max_rounds):
                await worker.run_once(session, ctx)
                ex = await session.get(Execution, execution_id)
                assert ex is not None
                if ex.status in {ExecutionStatus.COMPLETED, ExecutionStatus.FAILED}:
                    break
            assert ex.status == ExecutionStatus.COMPLETED, ex.failure_detail


async def run_live_greenfield_after_decompose(
    *,
    client: AsyncClient,
    async_engine: AsyncEngine,
    project_id: str,
    cycle_id: str,
) -> None:
    """Architecture → planning → development using live workers and API approvals."""
    factory = async_sessionmaker(bind=async_engine, class_=AsyncSession, expire_on_commit=False)

    propose = await client.post(f"/delivery-cycles/{cycle_id}/architecture/propose")
    propose.raise_for_status()
    await _run_task_to_completion(
        factory, propose.json()["task_id"], correlation_prefix="mvp-atlas"
    )

    async with factory() as session:
        arch = (
            (
                await session.execute(
                    select(Architecture).where(Architecture.project_id == uuid.UUID(project_id))
                )
            )
            .scalars()
            .first()
        )
        assert arch is not None and arch.status == SpecStatus.PROPOSED
        arch_id = arch.id

    arch_appr = await client.post(
        f"/architectures/{arch_id}/approval-request",
        json={"delivery_cycle_id": cycle_id},
    )
    arch_appr.raise_for_status()
    await client.post(
        f"/approvals/{arch_appr.json()['approval_id']}/decision",
        json={"decision": "APPROVED", "note": "chained MVP architecture"},
    )

    planning = await client.post(
        f"/delivery-cycles/{cycle_id}/commands/start_planning",
        json={"expected_state": "ARCHITECTURE"},
    )
    planning.raise_for_status()

    gen = await client.post(f"/delivery-cycles/{cycle_id}/implementation-specs/generate")
    gen.raise_for_status()
    for spec_task in gen.json().get("tasks") or []:
        await _run_task_to_completion(factory, spec_task["task_id"], correlation_prefix="mvp-impl")

    async with factory() as session:
        spec_list = list(
            (
                await session.execute(
                    select(ImplementationSpec).where(
                        ImplementationSpec.project_id == uuid.UUID(project_id),
                        ImplementationSpec.status == SpecStatus.PROPOSED,
                    )
                )
            ).scalars()
        )
    assert spec_list, "expected PROPOSED implementation specs from live Kira"

    for impl in spec_list:
        req = await client.post(
            f"/implementation-specs/{impl.id}/approval-request",
            json={"delivery_cycle_id": cycle_id},
        )
        req.raise_for_status()
        await client.post(
            f"/approvals/{req.json()['approval_id']}/decision",
            json={"decision": "APPROVED", "note": "chained MVP impl spec"},
        )

    plan_gen = await client.post(f"/delivery-cycles/{cycle_id}/task-plan/generate")
    plan_gen.raise_for_status()
    plan_task_id = plan_gen.json().get("task_id")
    if plan_task_id:
        await _run_task_to_completion(factory, plan_task_id, correlation_prefix="mvp-plan")

    await wait_for_task_plan_proposed(factory, uuid.UUID(cycle_id))

    from core.domain.exceptions import DomainError
    from core.planning.task_plans.service import TaskPlanService

    async with factory() as session, session.begin():
        actor = await ensure_system_actor(session)
        plan_ctx = CommandContext(actor=actor, correlation_id="mvp-plan-accept")
        try:
            await accept_task_plan_if_proposed(session, uuid.UUID(cycle_id), plan_ctx)
        except DomainError as exc:
            if exc.code == "INVALID_STATE":
                accepted = (
                    await session.execute(
                        select(TaskPlanRow).where(
                            TaskPlanRow.delivery_cycle_id == uuid.UUID(cycle_id),
                            TaskPlanRow.status == "ACCEPTED",
                        )
                    )
                ).scalar_one_or_none()
                if accepted is None:
                    raise
            elif exc.code == "VALIDATION_FAILED":
                impl_specs = list(
                    (
                        await session.execute(
                            select(ImplementationSpec).where(
                                ImplementationSpec.project_id == uuid.UUID(project_id),
                                ImplementationSpec.status == SpecStatus.APPROVED,
                            )
                        )
                    ).scalars()
                )
                assert impl_specs, "need approved implementation specs for task plan fallback"
                plan = await build_task_plan_for_cycle(session, uuid.UUID(cycle_id), impl_specs)
                plan_row = await TaskPlanService().persist_proposed(
                    session,
                    delivery_cycle_id=uuid.UUID(cycle_id),
                    plan=plan,
                    implementation_spec_ids=[s.id for s in impl_specs],
                    execution_id=None,
                    ctx=plan_ctx,
                )
                from tests.fixtures.approvals import approve_task_plan

                await approve_task_plan(session, plan_row.id)
            else:
                raise
    await wait_for_task_plan_accepted(factory, uuid.UUID(cycle_id))

    dev = await client.post(
        f"/delivery-cycles/{cycle_id}/commands/start_development",
        json={"expected_state": "PLANNING"},
    )
    dev.raise_for_status()

    terminal = {TaskStatus.COMPLETED, TaskStatus.FAILED, TaskStatus.CANCELLED}
    with (
        patch("core.runtime.model_router.build_providers", side_effect=build_providers),
        suppress(TimeoutError),
    ):
        await drain_until_code_change_tasks_terminal(
            factory,
            uuid.UUID(cycle_id),
            correlation_prefix="mvp-forge",
            max_outer_rounds=120,
            rounds_per_drain=12,
            inject_chaos=os.environ.get("MVP_CHAOS") == "1",
        )

    async with factory() as session:
        dev_tasks = list(
            (
                await session.execute(
                    select(Task).where(
                        Task.delivery_cycle_id == uuid.UUID(cycle_id),
                        Task.work_type == WorkType.CODE_CHANGE,
                    )
                )
            ).scalars()
        )
    if dev_tasks and any(t.status not in terminal for t in dev_tasks):
        async with factory() as session, session.begin():
            actor = await ensure_system_actor(session)
            dev_ctx = CommandContext(actor=actor, correlation_id="mvp-forge-fallback")
            cycle_row = await session.get(DeliveryCycle, uuid.UUID(cycle_id))
            repo_row = await session.get(Repository, cycle_row.repository_id) if cycle_row else None
            project_row = await session.get(Project, uuid.UUID(project_id))
            assert (
                cycle_row is not None
                and repo_row is not None
                and project_row is not None
                and cycle_row.base_sha
            )
            await complete_implementation_tasks_with_supportdesk_r1(
                session,
                dev_ctx,
                project=project_row,
                repository=repo_row,
                cycle=cycle_row,
                base_sha=cycle_row.base_sha,
            )
