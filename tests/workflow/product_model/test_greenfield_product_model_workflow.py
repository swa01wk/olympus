"""Deterministic Greenfield product-model workflow (FakeProvider stand-in for live decompose)."""

from __future__ import annotations

import os
import uuid
from pathlib import Path
from unittest.mock import patch

import pytest
from core.commands.context import CommandContext
from core.domain.enums import ActorKind, ExecutionStatus
from core.domain.executions.models import Execution
from core.execution.worker import ExecutionWorker
from core.runtime.providers.fake_provider import FakeProvider, FakeScriptStep
from core.scheduler.admission import AdmissionService
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from tests.fixtures.product_model_harness import supportdesk_decomposition

pytestmark = [pytest.mark.workflow, pytest.mark.integration]


@pytest.mark.asyncio
async def test_greenfield_upload_decompose_scope_architecture(
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

    fake = FakeProvider()
    fake.set_script(
        [FakeScriptStep(structured=supportdesk_decomposition().model_dump(mode="json"))]
    )
    fake_instance = fake

    def _providers(*, fake=None):
        provider = fake if fake is not None else fake_instance
        return {"anthropic": provider, "openai": provider}

    prd = Path(__file__).resolve().parents[2] / "fixtures" / "supportdesk" / "PRD.md"
    transport = ASGITransport(app=control_app)
    async with AsyncClient(
        transport=transport,
        base_url="http://test",
        headers={"Authorization": f"Bearer {operator_token}"},
    ) as client:
        project = await client.post("/projects", json={"key": "wf-pm", "name": "WF PM"})
        project_id = project.json()["id"]
        cycle = await client.post(
            f"/projects/{project_id}/delivery-cycles",
            json={"type": "GREENFIELD_BUILD", "objective": "wf"},
        )
        cycle_id = cycle.json()["id"]
        up = await client.post(
            f"/projects/{project_id}/sources",
            params={"delivery_cycle_id": cycle_id},
            files={"file": ("PRD.md", prd.read_bytes(), "text/markdown")},
            headers={"Idempotency-Key": f"wf-{uuid.uuid4().hex[:8]}"},
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
        from sqlalchemy import select

        actor = (
            await session.execute(select(Actor).where(Actor.kind == ActorKind.SYSTEM).limit(1))
        ).scalar_one_or_none()
        if actor is None:
            actor = Actor(kind=ActorKind.SYSTEM, name="wf-pm-worker", roles=["SYSTEM"])
            session.add(actor)
            await session.flush()
        ctx = CommandContext(actor=actor, correlation_id="wf-pm")
        execution = await AdmissionService().admit_task(session, uuid.UUID(task_id), ctx)
        execution_id = execution.id

    with patch("core.runtime.model_router.build_providers", side_effect=_providers):
        async with factory() as session, session.begin():
            from core.domain.actors.models import Actor
            from sqlalchemy import select

            actor = (
                await session.execute(select(Actor).where(Actor.kind == ActorKind.SYSTEM).limit(1))
            ).scalar_one()
            ctx = CommandContext(actor=actor, correlation_id="wf-pm-run")
            worker = ExecutionWorker(worker_id=f"wf-{uuid.uuid4().hex[:6]}")
            for _ in range(12):
                await worker.run_once(session, ctx)
                ex = await session.get(Execution, execution_id)
                assert ex is not None
                if ex.status in {ExecutionStatus.COMPLETED, ExecutionStatus.FAILED}:
                    break

    async with factory() as session:
        ex = await session.get(Execution, execution_id)
        assert ex is not None
        assert ex.status == ExecutionStatus.COMPLETED, ex.failure_detail

    async with AsyncClient(
        transport=transport,
        base_url="http://test",
        headers={"Authorization": f"Bearer {operator_token}"},
    ) as client:
        advance = await client.post(
            f"/delivery-cycles/{cycle_id}/commands/start_product_modeling",
            json={"expected_state": "DISCOVERY"},
        )
        assert advance.status_code == 200, advance.text
        assert advance.json()["to_state"] == "PRODUCT_MODEL"

    async with AsyncClient(
        transport=transport,
        base_url="http://test",
        headers={"Authorization": f"Bearer {operator_token}"},
    ) as client:
        features = await client.get(f"/projects/{project_id}/features")
        all_specs: list[str] = []
        for feat in features.json():
            spec_list = await client.get(f"/features/{feat['id']}/specs")
            all_specs.extend(s["id"] for s in spec_list.json())
        scope_req = await client.post(
            f"/delivery-cycles/{cycle_id}/scope/approval-request",
            json={"feature_spec_ids": all_specs},
        )
        assert scope_req.status_code == 200
        approval_id = scope_req.json()["approval_id"]
        await client.post(
            f"/approvals/{approval_id}/decision",
            json={"decision": "APPROVED", "note": "wf"},
        )
        arch = await client.post(
            f"/delivery-cycles/{cycle_id}/commands/start_architecture",
            json={"expected_state": "PRODUCT_MODEL"},
        )
        assert arch.status_code == 200, arch.text
        assert arch.json()["to_state"] == "ARCHITECTURE"
