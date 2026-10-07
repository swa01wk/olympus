"""Deterministic planning workflow through compiled contracts (FakeProvider for decompose)."""

from __future__ import annotations

import os
import uuid
from unittest.mock import patch

import pytest
from core.commands.context import CommandContext
from core.domain.enums import (
    ActorKind,
    ExecutionStatus,
    TaskContractStatus,
    TaskOrigin,
)
from core.domain.executions.models import Execution
from core.domain.task_contracts.models import TaskContract
from core.domain.tasks.models import Task
from core.execution.worker import ExecutionWorker
from core.planning.task_plans.service import TaskPlanService
from core.runtime.providers.fake_provider import FakeProvider, FakeScriptStep
from core.scheduler.admission import AdmissionService
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from tests.fixtures.planning_workflow_harness import (
    approve_scope_and_enter_architecture,
    build_task_plan_for_cycle,
    provision_greenfield_repository,
    seed_approved_architecture,
    seed_approved_implementation_specs_for_cycle,
    supportdesk_decompose_script,
    supportdesk_upload_and_decompose_task,
)

pytestmark = [pytest.mark.workflow, pytest.mark.integration]


@pytest.mark.asyncio
async def test_planning_through_development_with_compiled_contracts(
    control_app,
    operator_token,
    async_engine,
) -> None:
    os.environ["MODEL_PROVIDER"] = "anthropic"
    os.environ["MODEL_DEFAULT"] = "claude-3-5-haiku-20241022"
    from core.config.settings import clear_settings_cache
    from core.runtime.model_policy import clear_models_config_cache

    clear_settings_cache()
    clear_models_config_cache()

    fake = FakeProvider()
    fake.set_script([FakeScriptStep(structured=supportdesk_decompose_script())])
    fake_instance = fake

    def _providers(*, fake=None):
        provider = fake if fake is not None else fake_instance
        return {"anthropic": provider, "openai": provider}

    transport = ASGITransport(app=control_app)
    async with AsyncClient(
        transport=transport,
        base_url="http://test",
        headers={"Authorization": f"Bearer {operator_token}"},
    ) as client:
        (
            project_id,
            cycle_id,
            _repo_id,
            decompose_task_id,
        ) = await supportdesk_upload_and_decompose_task(
            client, idempotency_suffix=uuid.uuid4().hex[:8]
        )

    factory = async_sessionmaker(bind=async_engine, class_=AsyncSession, expire_on_commit=False)
    async with factory() as session, session.begin():
        from core.domain.actors.models import Actor
        from core.domain.enums import ActorRole

        actor = Actor(kind=ActorKind.SYSTEM, name="plan-wf", roles=[ActorRole.SYSTEM.value])
        session.add(actor)
        await session.flush()
        ctx = CommandContext(actor=actor, correlation_id="plan-wf")
        execution = await AdmissionService().admit_task(session, uuid.UUID(decompose_task_id), ctx)
        execution_id = execution.id

    with patch("core.runtime.model_router.build_providers", side_effect=_providers):
        async with factory() as session, session.begin():
            from core.domain.actors.models import Actor
            from core.domain.enums import ActorRole

            actor = (
                await session.execute(select(Actor).where(Actor.kind == ActorKind.SYSTEM).limit(1))
            ).scalar_one()
            ctx = CommandContext(actor=actor, correlation_id="plan-wf-run")
            worker = ExecutionWorker(worker_id=f"plan-wf-{uuid.uuid4().hex[:6]}")
            for _ in range(12):
                await worker.run_once(session, ctx)
                ex = await session.get(Execution, execution_id)
                assert ex is not None
                if ex.status in {ExecutionStatus.COMPLETED, ExecutionStatus.FAILED}:
                    break
            assert ex.status == ExecutionStatus.COMPLETED

    async with AsyncClient(
        transport=transport,
        base_url="http://test",
        headers={"Authorization": f"Bearer {operator_token}"},
    ) as client:
        await approve_scope_and_enter_architecture(client, project_id, cycle_id)

    async with factory() as session, session.begin():
        from core.domain.actors.models import Actor
        from core.domain.delivery_cycles.models import DeliveryCycle
        from core.domain.enums import ActorRole

        actor = (
            await session.execute(select(Actor).where(Actor.kind == ActorKind.SYSTEM).limit(1))
        ).scalar_one()
        ctx = CommandContext(actor=actor, correlation_id="plan-seed")
        cycle = await session.get(DeliveryCycle, uuid.UUID(cycle_id))
        assert cycle is not None
        await seed_approved_architecture(session, uuid.UUID(project_id), ctx)
        await provision_greenfield_repository(session, cycle, ctx)

    async with AsyncClient(
        transport=transport,
        base_url="http://test",
        headers={"Authorization": f"Bearer {operator_token}"},
    ) as client:
        planning = await client.post(
            f"/delivery-cycles/{cycle_id}/commands/start_planning",
            json={"expected_state": "ARCHITECTURE"},
        )
        assert planning.status_code == 200, planning.text
        assert planning.json()["to_state"] == "PLANNING"

    async with factory() as session, session.begin():
        from core.domain.actors.models import Actor
        from core.domain.delivery_cycles.models import DeliveryCycle
        from core.domain.enums import ActorRole

        actor = (
            await session.execute(select(Actor).where(Actor.kind == ActorKind.SYSTEM).limit(1))
        ).scalar_one()
        ctx = CommandContext(actor=actor, correlation_id="plan-impl")
        cycle = await session.get(DeliveryCycle, uuid.UUID(cycle_id))
        assert cycle is not None
        impl_specs = await seed_approved_implementation_specs_for_cycle(
            session, uuid.UUID(cycle_id), ctx
        )
        assert impl_specs
        plan = await build_task_plan_for_cycle(session, uuid.UUID(cycle_id), impl_specs)
        plan_row = await TaskPlanService().persist_proposed(
            session,
            delivery_cycle_id=uuid.UUID(cycle_id),
            plan=plan,
            implementation_spec_ids=[s.id for s in impl_specs],
            execution_id=None,
            ctx=ctx,
        )
        await TaskPlanService().accept(session, plan_row.id, ctx)

    async with AsyncClient(
        transport=transport,
        base_url="http://test",
        headers={"Authorization": f"Bearer {operator_token}"},
    ) as client:
        dev = await client.post(
            f"/delivery-cycles/{cycle_id}/commands/start_development",
            json={"expected_state": "PLANNING"},
        )
        assert dev.status_code == 200, dev.text
        assert dev.json()["to_state"] == "DEVELOPMENT"

    async with factory() as session:
        from core.domain.delivery_cycles.models import DeliveryCycle

        cycle = await session.get(DeliveryCycle, uuid.UUID(cycle_id))
        assert cycle is not None
        assert cycle.base_sha is not None
        tasks = await session.execute(
            select(Task).where(
                Task.delivery_cycle_id == cycle.id,
                Task.origin == TaskOrigin.IMPLEMENTATION_PLAN,
            )
        )
        for task in tasks.scalars():
            assert task.implementation_spec_id is not None
            contract = await session.get(TaskContract, task.current_contract_id)
            assert contract is not None
            assert contract.status == TaskContractStatus.ISSUED
            assert (contract.compiled_by or "").startswith("compiler:")
