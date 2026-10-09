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
from core.runtime.providers.fake_provider import FakeProvider, FakeScriptStep
from core.scheduler.admission import AdmissionService
from httpx import ASGITransport, AsyncClient
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from tests.integration.control_plane.test_source_chunking_helpers import (
    chunk_a_decomposition,
    chunk_b_decomposition,
)

pytestmark = [pytest.mark.integration, pytest.mark.usefixtures("empty_execution_queue")]


@pytest.mark.asyncio
async def test_kira_decompose_chunks_large_prd_and_merges(
    control_app,
    operator_token,
    async_engine,
    monkeypatch,
) -> None:
    monkeypatch.setenv("OLYMPUS_PRODUCT_SOURCE_DECOMPOSE_MAX_CHARS", "600")
    from core.config.settings import clear_settings_cache
    from core.runtime.model_policy import clear_models_config_cache

    clear_settings_cache()
    clear_models_config_cache()

    os.environ["MODEL_PROVIDER"] = "anthropic"
    os.environ["MODEL_DEFAULT"] = "claude-3-5-haiku-20241022"
    os.environ["MODEL_PRODUCT_REASONING"] = "claude-3-5-haiku-20241022"
    clear_settings_cache()
    clear_models_config_cache()

    fake = FakeProvider()
    fake.set_script(
        [
            FakeScriptStep(structured=chunk_a_decomposition().model_dump(mode="json")),
            FakeScriptStep(structured=chunk_b_decomposition().model_dump(mode="json")),
        ]
    )
    fake_instance = fake

    def _providers(*, fake=None):
        provider = fake if fake is not None else fake_instance
        return {"anthropic": provider, "openai": provider}

    prd = Path(__file__).resolve().parents[2] / "fixtures" / "supportdesk" / "PRD_large.md"
    transport = ASGITransport(app=control_app)
    async with AsyncClient(
        transport=transport,
        base_url="http://test",
        headers={"Authorization": f"Bearer {operator_token}"},
    ) as client:
        project = await client.post("/projects", json={"key": "large-prd", "name": "Large PRD"})
        project_id = project.json()["id"]
        cycle = await client.post(
            f"/projects/{project_id}/delivery-cycles",
            json={"type": "GREENFIELD_BUILD", "objective": "chunk"},
        )
        cycle_id = cycle.json()["id"]
        up = await client.post(
            f"/projects/{project_id}/sources",
            params={"delivery_cycle_id": cycle_id},
            files={"file": ("PRD_large.md", prd.read_bytes(), "text/markdown")},
            headers={"Idempotency-Key": f"large-{uuid.uuid4().hex[:8]}"},
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
            actor = Actor(kind=ActorKind.SYSTEM, name="chunk-worker", roles=["SYSTEM"])
            session.add(actor)
            await session.flush()
        ctx = CommandContext(actor=actor, correlation_id="large-prd")
        execution = await AdmissionService().admit_task(session, uuid.UUID(task_id), ctx)
        execution_id = execution.id

    with patch("core.runtime.model_router.build_providers", side_effect=_providers):
        async with factory() as session, session.begin():
            from core.domain.actors.models import Actor

            actor = (
                await session.execute(select(Actor).where(Actor.kind == ActorKind.SYSTEM).limit(1))
            ).scalar_one()
            ctx = CommandContext(actor=actor, correlation_id="large-prd-run")
            worker = ExecutionWorker(worker_id=f"large-{uuid.uuid4().hex[:6]}")
            for _ in range(16):
                await worker.run_once(session, ctx)
                ex = await session.get(Execution, execution_id)
                assert ex is not None
                if ex.status in {ExecutionStatus.COMPLETED, ExecutionStatus.FAILED}:
                    break

    async with factory() as session:
        ex = await session.get(Execution, execution_id)
        assert ex is not None
        assert ex.status == ExecutionStatus.COMPLETED, ex.failure_detail
        call_count = (
            await session.execute(
                select(func.count())
                .select_from(ModelCall)
                .where(ModelCall.execution_id == execution_id)
            )
        ).scalar_one()
        assert call_count >= 2

    async with AsyncClient(
        transport=transport,
        base_url="http://test",
        headers={"Authorization": f"Bearer {operator_token}"},
    ) as client:
        caps = await client.get(f"/projects/{project_id}/capabilities")
        cap_refs = {c["key"] for c in caps.json()}
        assert "CAP-1" in cap_refs or any("CAP" in k for k in cap_refs)
        features = await client.get(f"/projects/{project_id}/features")
        assert len(features.json()) >= 2
