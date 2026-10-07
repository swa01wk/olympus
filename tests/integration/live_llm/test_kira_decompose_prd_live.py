from __future__ import annotations

import os
import uuid
from pathlib import Path
from unittest.mock import patch

import pytest
from core.commands.context import CommandContext
from core.domain.enums import ActorKind, ExecutionStatus
from core.domain.executions.models import Execution
from core.domain.model_calls.models import ModelCall
from core.execution.worker import ExecutionWorker
from core.runtime.model_router import build_providers
from core.scheduler.admission import AdmissionService
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from tests.live_credentials import any_live_provider_configured

pytestmark = [pytest.mark.live_llm, pytest.mark.integration]


@pytest.mark.asyncio
async def test_kira_live_decompose_supportdesk_prd(
    control_app,
    operator_token,
    async_engine,
) -> None:
    if os.getenv("LLM_LIVE_TESTS") != "1":
        pytest.skip("LLM_LIVE_TESTS not enabled")
    if not any_live_provider_configured():
        pytest.skip("No live provider API key configured")

    from core.config.settings import clear_settings_cache
    from core.runtime.model_policy import clear_models_config_cache

    clear_settings_cache()
    clear_models_config_cache()

    prd = Path(__file__).resolve().parents[2] / "fixtures" / "supportdesk" / "PRD.md"
    transport = ASGITransport(app=control_app)
    async with AsyncClient(
        transport=transport,
        base_url="http://test",
        headers={"Authorization": f"Bearer {operator_token}"},
    ) as client:
        project = await client.post("/projects", json={"key": "live-kira", "name": "Live Kira"})
        project_id = project.json()["id"]
        cycle = await client.post(
            f"/projects/{project_id}/delivery-cycles",
            json={"type": "GREENFIELD_BUILD", "objective": "live kira"},
        )
        cycle_id = cycle.json()["id"]
        up = await client.post(
            f"/projects/{project_id}/sources",
            params={"delivery_cycle_id": cycle_id},
            files={"file": ("PRD.md", prd.read_bytes(), "text/markdown")},
            headers={"Idempotency-Key": f"live-{uuid.uuid4().hex[:8]}"},
        )
        assert up.status_code == 200
        source_id = up.json()["result"]["product_source_id"]
        decompose = await client.post(
            f"/sources/{source_id}/decompose",
            json={"delivery_cycle_id": cycle_id},
        )
        assert decompose.status_code == 200
        task_id = decompose.json()["task_id"]

    factory = async_sessionmaker(bind=async_engine, class_=AsyncSession, expire_on_commit=False)
    execution_id: uuid.UUID
    async with factory() as session, session.begin():
        from core.domain.actors.models import Actor

        actor = (
            await session.execute(select(Actor).where(Actor.kind == ActorKind.SYSTEM).limit(1))
        ).scalar_one_or_none()
        if actor is None:
            actor = Actor(kind=ActorKind.SYSTEM, name="live-kira-worker", roles=["SYSTEM"])
            session.add(actor)
            await session.flush()
        ctx = CommandContext(actor=actor, correlation_id="live-kira")
        execution = await AdmissionService().admit_task(session, uuid.UUID(task_id), ctx)
        execution_id = execution.id

    with patch("core.runtime.model_router.build_providers", side_effect=build_providers):
        async with factory() as session, session.begin():
            from core.domain.actors.models import Actor

            actor = (
                await session.execute(select(Actor).where(Actor.kind == ActorKind.SYSTEM).limit(1))
            ).scalar_one_or_none()
            if actor is None:
                actor = Actor(kind=ActorKind.SYSTEM, name="live-kira-worker", roles=["SYSTEM"])
                session.add(actor)
                await session.flush()
            ctx = CommandContext(actor=actor, correlation_id="live-kira-run")
            worker = ExecutionWorker(worker_id=f"live-{uuid.uuid4().hex[:6]}")
            for _ in range(20):
                await worker.run_once(session, ctx)
                ex = await session.get(Execution, execution_id)
                assert ex is not None
                if ex.status in {ExecutionStatus.COMPLETED, ExecutionStatus.FAILED}:
                    break

    async with factory() as session:
        ex = await session.get(Execution, execution_id)
        assert ex is not None
        assert ex.status == ExecutionStatus.COMPLETED, ex.failure_detail
        calls = await session.execute(
            select(ModelCall).where(ModelCall.execution_id == execution_id)
        )
        assert calls.scalars().first() is not None

    async with AsyncClient(
        transport=transport,
        base_url="http://test",
        headers={"Authorization": f"Bearer {operator_token}"},
    ) as client:
        caps = await client.get(f"/projects/{project_id}/capabilities")
        assert len(caps.json()) >= 1
        features = await client.get(f"/projects/{project_id}/features")
        assert len(features.json()) >= 2
        names = " ".join(f["name"] + f.get("description", "") for f in features.json()).lower()
        assert "create" in names or "ticket" in names
        assert "status" in names or "update" in names or "close" in names
