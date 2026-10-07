from __future__ import annotations

import os
import uuid
from unittest.mock import patch

import pytest
from core.commands.context import CommandContext
from core.domain.enums import ExecutionStatus, SpecStatus
from core.domain.executions.models import Execution
from core.execution.worker import ExecutionWorker
from core.planning.models import Architecture
from core.planning.schemas import ArchitectureBody
from core.runtime.model_router import build_providers
from core.scheduler.admission import AdmissionService
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from tests.fixtures.planning_workflow_harness import (
    approve_scope_and_enter_architecture,
    create_greenfield_planning_cycle,
    ensure_system_actor,
    seed_supportdesk_product_model_for_cycle,
)
from tests.live_credentials import any_live_provider_configured

pytestmark = [pytest.mark.live_llm, pytest.mark.integration]


@pytest.mark.asyncio
async def test_atlas_supportdesk_live(
    control_app,
    operator_token,
    async_engine,
) -> None:
    if os.getenv("LLM_LIVE_TESTS") != "1":
        pytest.skip("LLM_LIVE_TESTS=1 required")
    if not any_live_provider_configured():
        pytest.skip("No live provider API key configured")

    os.environ.setdefault("MODEL_ARCHITECTURE_REASONING", os.environ.get("MODEL_DEFAULT", ""))
    from core.config.settings import clear_settings_cache
    from core.runtime.model_policy import clear_models_config_cache

    clear_settings_cache()
    clear_models_config_cache()

    transport = ASGITransport(app=control_app)
    suffix = f"live-atlas-{uuid.uuid4().hex[:6]}"
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
        propose = await client.post(f"/delivery-cycles/{cycle_id}/architecture/propose")
        assert propose.status_code == 200, propose.text
        atlas_task_id = propose.json()["task_id"]

    factory = async_sessionmaker(bind=async_engine, class_=AsyncSession, expire_on_commit=False)
    async with factory() as session, session.begin():
        actor = await ensure_system_actor(session)
        ctx = CommandContext(actor=actor, correlation_id="live-atlas-propose")
        execution = await AdmissionService().admit_task(session, uuid.UUID(atlas_task_id), ctx)
        execution_id = execution.id

    with patch("core.runtime.model_router.build_providers", side_effect=build_providers):
        async with factory() as session, session.begin():
            actor = await ensure_system_actor(session)
            ctx = CommandContext(actor=actor, correlation_id="live-atlas-run")
            worker = ExecutionWorker(worker_id=f"live-atlas-p-{uuid.uuid4().hex[:4]}")
            for _ in range(30):
                await worker.run_once(session, ctx)
                ex = await session.get(Execution, execution_id)
                assert ex is not None
                if ex.status in {ExecutionStatus.COMPLETED, ExecutionStatus.FAILED}:
                    break
            assert ex.status == ExecutionStatus.COMPLETED, ex.failure_detail

    async with factory() as session:
        arch = await session.execute(
            select(Architecture).where(Architecture.project_id == uuid.UUID(project_id))
        )
        row = arch.scalars().first()
        assert row is not None
        assert row.status == SpecStatus.PROPOSED
        body = ArchitectureBody.model_validate(row.body)
        stack = body.technology_stack
        assert stack.language
        assert stack.web
        assert stack.orm
        assert stack.tests
        assert len(body.components) >= 1
        assert len(body.layers) >= 1
