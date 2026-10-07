from __future__ import annotations

import os
import uuid
from unittest.mock import patch

import pytest
from core.commands.context import CommandContext
from core.domain.delivery_cycles.service import DeliveryCycleService
from core.domain.enums import ExecutionStatus, SpecStatus
from core.domain.executions.models import Execution
from core.execution.worker import ExecutionWorker
from core.planning.models import ImplementationSpec
from core.product_model.models import Feature, FeatureSpec
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
    seed_supportdesk_product_model_for_cycle,
)
from tests.live_credentials import any_live_provider_configured

pytestmark = [pytest.mark.live_llm, pytest.mark.integration]


@pytest.mark.asyncio
async def test_kira_impl_spec_create_ticket_live(
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
    suffix = f"live-impl-{uuid.uuid4().hex[:6]}"
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
        ctx = CommandContext(actor=actor, correlation_id="live-impl-seed")
        await seed_approved_architecture(session, uuid.UUID(project_id), ctx)
        cycle = await session.get(DeliveryCycle, uuid.UUID(cycle_id))
        assert cycle is not None
        await provision_greenfield_repository(session, cycle, ctx)
        cycle.state = "ARCHITECTURE"
        await session.flush()
        await DeliveryCycleService().run_command(
            session, cycle.id, "start_planning", "ARCHITECTURE", ctx
        )

    async with AsyncClient(
        transport=transport,
        base_url="http://test",
        headers={"Authorization": f"Bearer {operator_token}"},
    ) as client:
        gen = await client.post(f"/delivery-cycles/{cycle_id}/implementation-specs/generate")
        assert gen.status_code == 200, gen.text
        all_tasks = gen.json()["tasks"]
        assert all_tasks

    async with factory() as session:
        create_ticket_tasks: list[dict[str, str]] = []
        for spec_task in all_tasks:
            spec = await session.get(FeatureSpec, uuid.UUID(spec_task["feature_spec_id"]))
            if spec is None:
                continue
            feature = await session.get(Feature, spec.feature_id)
            if feature is not None and feature.name == "Create Ticket":
                create_ticket_tasks.append(spec_task)
        assert create_ticket_tasks, "Create Ticket feature spec task required"
        spec_task = create_ticket_tasks[0]

    with patch("core.runtime.model_router.build_providers", side_effect=build_providers):
        async with factory() as session, session.begin():
            actor = await ensure_system_actor(session)
            ctx = CommandContext(actor=actor, correlation_id="live-impl-run")
            worker = ExecutionWorker(worker_id=f"live-impl-{uuid.uuid4().hex[:4]}")
            execution = await AdmissionService().admit_task(
                session, uuid.UUID(spec_task["task_id"]), ctx
            )
            for _ in range(40):
                await worker.run_once(session, ctx)
                ex = await session.get(Execution, execution.id)
                assert ex is not None
                if ex.status in {ExecutionStatus.COMPLETED, ExecutionStatus.FAILED}:
                    break
            assert ex.status == ExecutionStatus.COMPLETED, ex.failure_detail

    async with factory() as session:
        row = (
            await session.execute(
                select(ImplementationSpec)
                .where(
                    ImplementationSpec.project_id == uuid.UUID(project_id),
                    ImplementationSpec.feature_spec_id == uuid.UUID(spec_task["feature_spec_id"]),
                    ImplementationSpec.status == SpecStatus.PROPOSED,
                )
                .order_by(ImplementationSpec.version.desc())
                .limit(1)
            )
        ).scalar_one_or_none()
        assert row is not None
        assert row.conformance_report.get("ok") is True
