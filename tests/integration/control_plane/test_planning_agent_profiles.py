"""Atlas / Kira planning profiles through ModelRouter + worker (FakeProvider)."""

from __future__ import annotations

import os
import uuid
from unittest.mock import patch

import pytest
from core.commands.context import CommandContext
from core.domain.enums import ActorKind, ExecutionStatus, SpecStatus
from core.domain.executions.models import Execution
from core.execution.worker import ExecutionWorker
from core.planning.models import Architecture, ImplementationSpec, TaskPlanRow
from core.planning.orchestrator import PlanningOrchestrator
from core.planning.schemas import ArchitectureBody
from core.runtime.providers.fake_provider import FakeProvider, FakeScriptStep
from core.scheduler.admission import AdmissionService
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from tests.fixtures.planning_harness import (
    create_ticket_implementation_spec,
    supportdesk_architecture_proposal,
)
from tests.fixtures.planning_workflow_harness import (
    approve_scope_and_enter_architecture,
    provision_greenfield_repository,
    seed_approved_architecture,
    supportdesk_decompose_script,
    supportdesk_upload_and_decompose_task,
)

pytestmark = [pytest.mark.integration, pytest.mark.usefixtures("empty_execution_queue")]


@pytest.mark.asyncio
async def test_atlas_proposal_persists_via_worker(
    control_app,
    operator_token,
    async_engine,
) -> None:
    os.environ["MODEL_PROVIDER"] = "anthropic"
    os.environ["MODEL_DEFAULT"] = "claude-3-5-haiku-20241022"
    os.environ["MODEL_ARCHITECTURE_REASONING"] = "claude-3-5-haiku-20241022"
    from core.config.settings import clear_settings_cache
    from core.runtime.model_policy import clear_models_config_cache

    clear_settings_cache()
    clear_models_config_cache()

    proposal = supportdesk_architecture_proposal()
    fake = FakeProvider()
    fake.set_script([FakeScriptStep(structured=proposal.model_dump(mode="json"))])
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
        project_id, cycle_id, _, decompose_task = await supportdesk_upload_and_decompose_task(
            client, idempotency_suffix=uuid.uuid4().hex[:8]
        )

    factory = async_sessionmaker(bind=async_engine, class_=AsyncSession, expire_on_commit=False)
    fake.set_script([FakeScriptStep(structured=supportdesk_decompose_script())])
    async with factory() as session, session.begin():
        from core.domain.actors.models import Actor
        from core.domain.enums import ActorRole

        actor = Actor(kind=ActorKind.SYSTEM, name="atlas-fake", roles=[ActorRole.SYSTEM.value])
        session.add(actor)
        await session.flush()
        ctx = CommandContext(actor=actor, correlation_id="atlas-fake")
        await AdmissionService().admit_task(session, uuid.UUID(decompose_task), ctx)

    with patch("core.runtime.model_router.build_providers", side_effect=_providers):
        async with factory() as session, session.begin():
            from core.domain.actors.models import Actor

            actor = (
                await session.execute(select(Actor).where(Actor.kind == ActorKind.SYSTEM).limit(1))
            ).scalar_one()
            ctx = CommandContext(actor=actor, correlation_id="decompose")
            worker = ExecutionWorker(worker_id="atlas-pre")
            for _ in range(12):
                await worker.run_once(session, ctx)

    async with AsyncClient(
        transport=transport,
        base_url="http://test",
        headers={"Authorization": f"Bearer {operator_token}"},
    ) as client:
        await approve_scope_and_enter_architecture(client, project_id, cycle_id)

    async with factory() as session, session.begin():
        from core.domain.actors.models import Actor
        from core.domain.enums import ActorRole

        actor = (
            await session.execute(select(Actor).where(Actor.kind == ActorKind.SYSTEM).limit(1))
        ).scalar_one()
        ctx = CommandContext(actor=actor, correlation_id="atlas-propose")
        started = await PlanningOrchestrator().start_architecture_proposal(
            session, uuid.UUID(cycle_id), ctx
        )
        execution = await AdmissionService().admit_task(session, uuid.UUID(started["task_id"]), ctx)
        execution_id = execution.id

    fake.set_script([FakeScriptStep(structured=proposal.model_dump(mode="json"))])
    with patch("core.runtime.model_router.build_providers", side_effect=_providers):
        async with factory() as session, session.begin():
            from core.domain.actors.models import Actor

            actor = (
                await session.execute(select(Actor).where(Actor.kind == ActorKind.SYSTEM).limit(1))
            ).scalar_one()
            ctx = CommandContext(actor=actor, correlation_id="atlas-run")
            worker = ExecutionWorker(worker_id="atlas-run")
            for _ in range(8):
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
        assert "fastapi" in body.technology_stack.web.lower()


@pytest.mark.asyncio
async def test_kira_implementation_spec_persists_via_worker(
    control_app,
    operator_token,
    async_engine,
) -> None:
    os.environ["MODEL_PLANNING"] = os.environ.get("MODEL_DEFAULT", "claude-3-5-haiku-20241022")
    draft = create_ticket_implementation_spec()
    fake = FakeProvider()
    fake.set_script([FakeScriptStep(structured=draft.model_dump(mode="json"))])
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
        project_id, cycle_id, _, decompose_task = await supportdesk_upload_and_decompose_task(
            client, idempotency_suffix=uuid.uuid4().hex[:8]
        )

    factory = async_sessionmaker(bind=async_engine, class_=AsyncSession, expire_on_commit=False)
    decompose_fake = FakeProvider()
    decompose_fake.set_script([FakeScriptStep(structured=supportdesk_decompose_script())])

    def _decompose_providers(*, fake=None):
        provider = fake if fake is not None else decompose_fake
        return {"anthropic": provider, "openai": provider}

    async with factory() as session, session.begin():
        from core.domain.actors.models import Actor
        from core.domain.enums import ActorRole

        actor = Actor(kind=ActorKind.SYSTEM, name="kira-impl", roles=[ActorRole.SYSTEM.value])
        session.add(actor)
        await session.flush()
        ctx = CommandContext(actor=actor, correlation_id="kira-impl")
        await AdmissionService().admit_task(session, uuid.UUID(decompose_task), ctx)

    with patch("core.runtime.model_router.build_providers", side_effect=_decompose_providers):
        async with factory() as session, session.begin():
            from core.domain.actors.models import Actor

            actor = (
                await session.execute(select(Actor).where(Actor.kind == ActorKind.SYSTEM).limit(1))
            ).scalar_one()
            ctx = CommandContext(actor=actor, correlation_id="decompose")
            worker = ExecutionWorker(worker_id="kira-decomp")
            for _ in range(12):
                await worker.run_once(session, ctx)

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
        from tests.fixtures.planning_workflow_harness import seed_approved_architecture

        actor = (
            await session.execute(select(Actor).where(Actor.kind == ActorKind.SYSTEM).limit(1))
        ).scalar_one()
        ctx = CommandContext(actor=actor, correlation_id="kira-impl-seed")
        await seed_approved_architecture(session, uuid.UUID(project_id), ctx)
        cycle = await session.get(DeliveryCycle, uuid.UUID(cycle_id))
        assert cycle is not None
        tasks = await PlanningOrchestrator().start_implementation_spec_generation(
            session, uuid.UUID(cycle_id), ctx
        )
        assert tasks
        execution = await AdmissionService().admit_task(
            session, uuid.UUID(tasks[0]["task_id"]), ctx
        )
        execution_id = execution.id

    with patch("core.runtime.model_router.build_providers", side_effect=_providers):
        async with factory() as session, session.begin():
            from core.domain.actors.models import Actor

            actor = (
                await session.execute(select(Actor).where(Actor.kind == ActorKind.SYSTEM).limit(1))
            ).scalar_one()
            ctx = CommandContext(actor=actor, correlation_id="kira-impl-run")
            worker = ExecutionWorker(worker_id="kira-impl-run")
            for _ in range(8):
                await worker.run_once(session, ctx)
                ex = await session.get(Execution, execution_id)
                assert ex is not None
                if ex.status in {ExecutionStatus.COMPLETED, ExecutionStatus.FAILED}:
                    break
            assert ex.status == ExecutionStatus.COMPLETED, ex.failure_detail

    async with factory() as session:
        impl = await session.execute(select(ImplementationSpec))
        assert impl.scalars().first() is not None


@pytest.mark.asyncio
async def test_kira_task_plan_persists_via_worker(
    control_app,
    operator_token,
    async_engine,
) -> None:
    fake = FakeProvider()
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
        project_id, cycle_id, _, decompose_task = await supportdesk_upload_and_decompose_task(
            client, idempotency_suffix=uuid.uuid4().hex[:8]
        )

    factory = async_sessionmaker(bind=async_engine, class_=AsyncSession, expire_on_commit=False)
    decompose_fake = FakeProvider()
    decompose_fake.set_script([FakeScriptStep(structured=supportdesk_decompose_script())])

    def _decompose_providers(*, fake=None):
        provider = fake if fake is not None else decompose_fake
        return {"anthropic": provider, "openai": provider}

    async with factory() as session, session.begin():
        from core.domain.actors.models import Actor
        from core.domain.enums import ActorRole

        actor = Actor(kind=ActorKind.SYSTEM, name="kira-plan", roles=[ActorRole.SYSTEM.value])
        session.add(actor)
        await session.flush()
        ctx = CommandContext(actor=actor, correlation_id="kira-plan")
        await AdmissionService().admit_task(session, uuid.UUID(decompose_task), ctx)

    with patch("core.runtime.model_router.build_providers", side_effect=_decompose_providers):
        async with factory() as session, session.begin():
            from core.domain.actors.models import Actor

            actor = (
                await session.execute(select(Actor).where(Actor.kind == ActorKind.SYSTEM).limit(1))
            ).scalar_one()
            ctx = CommandContext(actor=actor, correlation_id="decompose")
            worker = ExecutionWorker(worker_id="kira-plan-decomp")
            for _ in range(12):
                await worker.run_once(session, ctx)

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
        from tests.fixtures.planning_workflow_harness import (
            build_task_plan_for_cycle,
            seed_approved_implementation_specs_for_cycle,
        )

        actor = (
            await session.execute(select(Actor).where(Actor.kind == ActorKind.SYSTEM).limit(1))
        ).scalar_one()
        ctx = CommandContext(actor=actor, correlation_id="kira-plan-seed")
        await seed_approved_architecture(session, uuid.UUID(project_id), ctx)
        cycle = await session.get(DeliveryCycle, uuid.UUID(cycle_id))
        assert cycle is not None
        await provision_greenfield_repository(session, cycle, ctx)
        cycle.state = "PLANNING"
        await session.flush()
        impl_specs = await seed_approved_implementation_specs_for_cycle(
            session, uuid.UUID(cycle_id), ctx
        )
        plan = await build_task_plan_for_cycle(session, uuid.UUID(cycle_id), impl_specs)
        fake.set_script([FakeScriptStep(structured=plan.model_dump(mode="json"))])
        started = await PlanningOrchestrator().start_task_plan_generation(
            session, uuid.UUID(cycle_id), ctx
        )
        execution = await AdmissionService().admit_task(session, uuid.UUID(started["task_id"]), ctx)
        execution_id = execution.id

    with patch("core.runtime.model_router.build_providers", side_effect=_providers):
        async with factory() as session, session.begin():
            from core.domain.actors.models import Actor

            actor = (
                await session.execute(select(Actor).where(Actor.kind == ActorKind.SYSTEM).limit(1))
            ).scalar_one()
            ctx = CommandContext(actor=actor, correlation_id="kira-plan-run")
            worker = ExecutionWorker(worker_id="kira-plan-run")
            for _ in range(8):
                await worker.run_once(session, ctx)
                ex = await session.get(Execution, execution_id)
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
        assert row.status == "PROPOSED"
