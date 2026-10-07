from __future__ import annotations

import os
import uuid
from unittest.mock import patch

import pytest
from core.commands.context import CommandContext
from core.domain.delivery_cycles.service import DeliveryCycleService
from core.domain.enums import ExecutionStatus
from core.domain.executions.models import Execution
from core.execution.worker import ExecutionWorker
from core.planning.models import TaskPlanRow
from core.planning.orchestrator import PlanningOrchestrator
from core.runtime.model_router import build_providers
from core.scheduler.admission import AdmissionService
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from tests.fixtures.planning_workflow_harness import (
    approve_scope_and_enter_architecture,
    create_greenfield_planning_cycle,
    ensure_system_actor,
    provision_greenfield_repository,
    seed_approved_architecture,
    seed_approved_implementation_specs_for_cycle,
    seed_supportdesk_product_model_for_cycle,
)
from tests.live_credentials import any_live_provider_configured

pytestmark = [pytest.mark.live_llm, pytest.mark.integration]


@pytest.mark.asyncio
async def test_kira_task_plan_live(
    control_app,
    operator_token,
    async_engine,
) -> None:
    if os.getenv("LLM_LIVE_TESTS") != "1":
        pytest.skip("LLM_LIVE_TESTS=1 required")
    if not any_live_provider_configured():
        pytest.skip("No live provider API key configured")

    os.environ.setdefault("MODEL_PLANNING", os.environ.get("MODEL_DEFAULT", ""))
    from core.config.settings import clear_settings_cache
    from core.runtime.model_policy import clear_models_config_cache

    clear_settings_cache()
    clear_models_config_cache()

    transport = ASGITransport(app=control_app)
    suffix = f"live-plan-{uuid.uuid4().hex[:6]}"
    async with AsyncClient(
        transport=transport,
        base_url="http://test",
        headers={"Authorization": f"Bearer {operator_token}"},
    ) as client:
        project_id, cycle_id = await create_greenfield_planning_cycle(
            client, idempotency_suffix=suffix
        )

    await seed_supportdesk_product_model_for_cycle(async_engine, project_id, cycle_id)

    async with AsyncClient(
        transport=transport,
        base_url="http://test",
        headers={"Authorization": f"Bearer {operator_token}"},
    ) as client:
        await approve_scope_and_enter_architecture(
            client, project_id, cycle_id, async_engine=async_engine
        )

    factory = async_sessionmaker(bind=async_engine, class_=AsyncSession, expire_on_commit=False)
    async with factory() as session, session.begin():
        from core.domain.delivery_cycles.models import DeliveryCycle

        actor = await ensure_system_actor(session)
        ctx = CommandContext(actor=actor, correlation_id="live-plan-seed")
        await seed_approved_architecture(session, uuid.UUID(project_id), ctx)
        cycle = await session.get(DeliveryCycle, uuid.UUID(cycle_id))
        assert cycle is not None
        await provision_greenfield_repository(session, cycle, ctx)
        cycle.state = "ARCHITECTURE"
        await session.flush()
        await DeliveryCycleService().run_command(
            session, cycle.id, "start_planning", "ARCHITECTURE", ctx
        )
        await seed_approved_implementation_specs_for_cycle(session, uuid.UUID(cycle_id), ctx)
        started = await PlanningOrchestrator().start_task_plan_generation(
            session, uuid.UUID(cycle_id), ctx
        )
        plan_task_id = started["task_id"]

    with patch("core.runtime.model_router.build_providers", side_effect=build_providers):
        async with factory() as session, session.begin():
            actor = await ensure_system_actor(session)
            ctx = CommandContext(actor=actor, correlation_id="live-plan-run")
            execution = await AdmissionService().admit_task(session, uuid.UUID(plan_task_id), ctx)
            worker = ExecutionWorker(worker_id=f"live-plan-{uuid.uuid4().hex[:4]}")
            for _ in range(40):
                await worker.run_once(session, ctx)
                ex = await session.get(Execution, execution.id)
                assert ex is not None
                if ex.status in {ExecutionStatus.COMPLETED, ExecutionStatus.FAILED}:
                    break
            assert ex.status == ExecutionStatus.COMPLETED, ex.failure_detail

    async with factory() as session:
        row = (
            (
                await session.execute(
                    select(TaskPlanRow).where(TaskPlanRow.delivery_cycle_id == uuid.UUID(cycle_id))
                )
            )
            .scalars()
            .first()
        )
        assert row is not None
        assert len((row.body or {}).get("tasks") or []) >= 1
