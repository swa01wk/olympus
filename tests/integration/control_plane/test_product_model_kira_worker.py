from __future__ import annotations

import os
import uuid
from pathlib import Path
from unittest.mock import patch

import pytest
from core.commands.context import CommandContext
from core.domain.enums import ExecutionStatus
from core.domain.executions.models import Execution
from core.execution.worker import ExecutionWorker
from core.runtime.providers.fake_provider import FakeProvider, FakeScriptStep
from core.scheduler.admission import AdmissionService
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from tests.fixtures.product_model_harness import supportdesk_decomposition

pytestmark = [pytest.mark.integration]


@pytest.mark.asyncio
async def test_kira_decompose_execution_persists_via_worker(
    control_app,
    operator_token,
    async_engine,
) -> None:
    os.environ["MODEL_PROVIDER"] = "anthropic"
    os.environ["MODEL_DEFAULT"] = "claude-3-5-haiku-20241022"
    os.environ["MODEL_PRODUCT_REASONING"] = "claude-3-5-haiku-20241022"
    from core.config.settings import clear_settings_cache
    from core.runtime.model_policy import clear_models_config_cache

    clear_settings_cache()
    clear_models_config_cache()

    decomposition = supportdesk_decomposition().model_dump(mode="json")
    fake = FakeProvider()
    fake.set_script([FakeScriptStep(structured=decomposition)])

    fake_instance = fake

    def _providers(*, fake=None):
        provider = fake if fake is not None else fake_instance
        return {"anthropic": provider, "openai": provider}

    project = None
    transport = ASGITransport(app=control_app)
    async with AsyncClient(
        transport=transport,
        base_url="http://test",
        headers={"Authorization": f"Bearer {operator_token}"},
    ) as client:
        project = await client.post("/projects", json={"key": "kira-wf", "name": "Kira WF"})
        project_id = project.json()["id"]
        cycle = await client.post(
            f"/projects/{project_id}/delivery-cycles",
            json={"type": "GREENFIELD_BUILD", "objective": "kira"},
        )
        cycle_id = cycle.json()["id"]
        prd = Path(__file__).resolve().parents[2] / "fixtures" / "supportdesk" / "PRD.md"
        up = await client.post(
            f"/projects/{project_id}/sources",
            params={"delivery_cycle_id": cycle_id},
            files={"file": ("PRD.md", prd.read_bytes(), "text/markdown")},
            headers={"Idempotency-Key": f"kira-{uuid.uuid4().hex[:8]}"},
        )
        source_id = up.json()["result"]["product_source_id"]
        decompose = await client.post(
            f"/sources/{source_id}/decompose",
            json={"delivery_cycle_id": cycle_id},
        )
        assert decompose.status_code == 200, decompose.text
        task_id = decompose.json()["task_id"]

    factory = async_sessionmaker(bind=async_engine, class_=AsyncSession, expire_on_commit=False)
    execution_id: uuid.UUID
    async with factory() as session, session.begin():
        from core.domain.actors.models import Actor
        from core.domain.enums import ActorKind
        from sqlalchemy import select

        actor = (
            await session.execute(select(Actor).where(Actor.kind == ActorKind.SYSTEM).limit(1))
        ).scalar_one_or_none()
        if actor is None:
            actor = Actor(kind=ActorKind.SYSTEM, name="kira-worker", roles=["SYSTEM"])
            session.add(actor)
            await session.flush()
        ctx = CommandContext(actor=actor, correlation_id="kira-exec")
        execution = await AdmissionService().admit_task(session, uuid.UUID(task_id), ctx)
        execution_id = execution.id

    with patch(
        "core.runtime.model_router.build_providers",
        side_effect=_providers,
    ):
        async with factory() as session, session.begin():
            from core.domain.actors.models import Actor
            from core.domain.enums import ActorKind
            from sqlalchemy import select

            actor = (
                await session.execute(select(Actor).where(Actor.kind == ActorKind.SYSTEM).limit(1))
            ).scalar_one()
            ctx = CommandContext(actor=actor, correlation_id="kira-run")
            worker = ExecutionWorker(worker_id=f"kira-{uuid.uuid4().hex[:6]}")
            for _ in range(12):
                await worker.run_once(session, ctx)
                ex = await session.get(Execution, execution_id)
                assert ex is not None
                if ex.status in {ExecutionStatus.COMPLETED, ExecutionStatus.FAILED}:
                    break

    async with factory() as session:
        from core.domain.model_calls.models import ModelCall
        from sqlalchemy import select

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
        decomps = await client.get(f"/delivery-cycles/{cycle_id}/decompositions")
        assert len(decomps.json()) >= 1
