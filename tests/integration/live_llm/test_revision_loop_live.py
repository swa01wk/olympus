"""RL2.10 — live revision loop on Atlas architecture (optional; requires LLM keys)."""

from __future__ import annotations

import json
import os
import uuid
from unittest.mock import patch

import pytest
from core.commands.context import CommandContext
from core.domain.approvals.models import Approval
from core.domain.enums import ApprovalStatus, ExecutionStatus, SpecStatus
from core.domain.executions.models import Execution
from core.execution.worker import ExecutionWorker
from core.planning.models import Architecture
from core.review.service import RevisionService
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

REVISION_NOTE = "Put the archived-project rule in one ProjectGuard used by the service layer"


async def _run_task_to_completion(
    factory: async_sessionmaker,
    task_id: uuid.UUID,
    *,
    correlation: str,
    max_attempts: int = 40,
) -> Execution:
    async with factory() as session, session.begin():
        actor = await ensure_system_actor(session)
        ctx = CommandContext(actor=actor, correlation_id=correlation)
        execution = await AdmissionService().admit_task(session, task_id, ctx)
        execution_id = execution.id

    with patch("core.runtime.model_router.build_providers", side_effect=build_providers):
        async with factory() as session, session.begin():
            actor = await ensure_system_actor(session)
            ctx = CommandContext(actor=actor, correlation_id=f"{correlation}-run")
            worker = ExecutionWorker(worker_id=f"live-rev-{uuid.uuid4().hex[:4]}")
            ex: Execution | None = None
            for _ in range(max_attempts):
                await worker.run_once(session, ctx)
                ex = await session.get(Execution, execution_id)
                assert ex is not None
                if ex.status in {ExecutionStatus.COMPLETED, ExecutionStatus.FAILED}:
                    break
            assert ex is not None
            assert ex.status == ExecutionStatus.COMPLETED, ex.failure_detail
            return ex


@pytest.mark.asyncio
async def test_revision_loop_architecture_live(
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
    suffix = f"live-rev-{uuid.uuid4().hex[:6]}"
    headers = {"Authorization": f"Bearer {operator_token}"}

    async with AsyncClient(transport=transport, base_url="http://test", headers=headers) as client:
        project_id, cycle_id = await create_greenfield_planning_cycle(
            client, idempotency_suffix=suffix
        )

    await seed_supportdesk_product_model_for_cycle(async_engine, project_id, cycle_id)

    async with AsyncClient(transport=transport, base_url="http://test", headers=headers) as client:
        await approve_scope_and_enter_architecture(
            client, project_id, cycle_id, async_engine=async_engine
        )
        propose = await client.post(f"/delivery-cycles/{cycle_id}/architecture/propose")
        assert propose.status_code == 200, propose.text
        atlas_task_id = uuid.UUID(propose.json()["task_id"])

    factory = async_sessionmaker(bind=async_engine, class_=AsyncSession, expire_on_commit=False)
    await _run_task_to_completion(factory, atlas_task_id, correlation="live-rev-v1")

    async with factory() as session:
        arch_v1 = (
            await session.execute(
                select(Architecture).where(Architecture.project_id == uuid.UUID(project_id))
            )
        ).scalar_one()
        assert arch_v1.status == SpecStatus.PROPOSED
        v1_id = arch_v1.id
        v1_version = arch_v1.version

        pending = (
            await session.execute(
                select(Approval).where(
                    Approval.delivery_cycle_id == uuid.UUID(cycle_id),
                    Approval.status == ApprovalStatus.PENDING,
                    Approval.subject_id == v1_id,
                )
            )
        ).scalar_one_or_none()
        assert pending is not None, "expected auto-requested ARCHITECTURE approval"
        approval_id = pending.id

    async with AsyncClient(transport=transport, base_url="http://test", headers=headers) as client:
        decision = await client.post(
            f"/approvals/{approval_id}/decision",
            json={"decision": "CHANGES_REQUESTED", "note": REVISION_NOTE},
            headers={"Idempotency-Key": f"rev-decide-{suffix}"},
        )
        assert decision.status_code == 200, decision.text

    async with factory() as session:
        rev_task_id = await RevisionService().find_revision_task_id(
            session, approval_id, uuid.UUID(cycle_id)
        )
        assert rev_task_id is not None

    await _run_task_to_completion(factory, rev_task_id, correlation="live-rev-v2")

    async with factory() as session:
        v1_row = await session.get(Architecture, v1_id)
        assert v1_row is not None
        assert v1_row.status == SpecStatus.SUPERSEDED

        arch_rows = (
            await session.execute(
                select(Architecture)
                .where(Architecture.project_id == uuid.UUID(project_id))
                .order_by(Architecture.version.desc())
            )
        ).scalars()
        versions = list(arch_rows)
        assert len(versions) >= 2
        v2 = versions[0]
        assert v2.version == v1_version + 1
        assert v2.status == SpecStatus.PROPOSED

        pending_v2 = (
            await session.execute(
                select(Approval).where(
                    Approval.delivery_cycle_id == uuid.UUID(cycle_id),
                    Approval.status == ApprovalStatus.PENDING,
                    Approval.subject_id == v2.id,
                )
            )
        ).scalar_one_or_none()
        assert pending_v2 is not None, "expected pending approval on revised architecture"

        body_blob = json.dumps(v2.body).lower()
        assert "guard" in body_blob
        normalized = body_blob.replace("_", "").replace("-", "")
        assert "projectguard" in normalized or "project guard" in body_blob
