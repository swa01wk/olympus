"""Journey 1 — Greenfield SupportDesk PRD upload through Release R1 (control-plane API path)."""

from __future__ import annotations

import uuid
from pathlib import Path

import pytest
from core.commands.context import CommandContext
from core.domain.delivery_cycles.models import DeliveryCycle
from core.domain.enums import ActorKind, RepositoryStatus
from core.domain.projects.models import Project
from core.domain.repositories.models import Repository
from core.release.enums import ReleaseStatus
from core.repositories.materialization_loop import MaterializationLoop
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from tests.fixtures.planning_workflow_harness import (
    approve_scope_and_enter_architecture,
    build_task_plan_for_cycle,
    ensure_system_actor,
    run_supportdesk_decompose_worker,
    seed_approved_architecture,
    seed_approved_implementation_specs_for_cycle,
)
from tests.fixtures.release_harness import finish_assurance_and_release_for_cycle
from tests.journey.greenfield_dev import complete_implementation_tasks_minimal_passing

pytestmark = [pytest.mark.journey]


@pytest.mark.asyncio
async def test_greenfield_supportdesk_end_to_end(
    control_app,
    operator_token,
    async_engine,
) -> None:
    """PRD → decompose → scope → architecture → planning → dev → assurance → Release R1.

    Live LLM at all seven model-dependent stages is covered by ``tests/integration/live_llm/*``
    and ``make test-live``; this journey proves the same API-driven path as production with
    deterministic decompose/architecture seeds for stable release acceptance.
    """
    suffix = uuid.uuid4().hex[:8]
    transport = ASGITransport(app=control_app)
    async with AsyncClient(
        transport=transport,
        base_url="http://test",
        headers={"Authorization": f"Bearer {operator_token}"},
    ) as client:
        project = await client.post(
            "/projects",
            json={"key": f"SUPPORTDESK-{suffix}", "name": "SupportDesk Journey"},
        )
        assert project.status_code == 201
        project_id = project.json()["id"]
        cycle = await client.post(
            f"/projects/{project_id}/delivery-cycles",
            json={"type": "GREENFIELD_BUILD", "objective": "Journey 1"},
        )
        assert cycle.status_code == 201
        cycle_id = cycle.json()["id"]
        repo_id = cycle.json()["repository_id"]

    factory = async_sessionmaker(bind=async_engine, class_=AsyncSession, expire_on_commit=False)
    async with factory() as session, session.begin():
        actor = await ensure_system_actor(session)
        ctx = CommandContext(actor=actor, correlation_id="journey-mat")
        for _ in range(10):
            await MaterializationLoop().run_once(session, ctx)
            repo = await session.get(Repository, uuid.UUID(repo_id))
            if repo and repo.status == RepositoryStatus.READY and repo.canonical_commit:
                break

    prd = Path(__file__).resolve().parents[1] / "fixtures" / "supportdesk" / "PRD.md"
    async with AsyncClient(
        transport=transport,
        base_url="http://test",
        headers={"Authorization": f"Bearer {operator_token}"},
    ) as client:
        up = await client.post(
            f"/projects/{project_id}/sources",
            params={"delivery_cycle_id": cycle_id},
            files={"file": ("PRD.md", prd.read_bytes(), "text/markdown")},
            headers={"Idempotency-Key": f"journey-{suffix}"},
        )
        assert up.status_code == 200
        source_id = up.json()["result"]["product_source_id"]
        decompose = await client.post(
            f"/sources/{source_id}/decompose",
            json={"delivery_cycle_id": cycle_id},
        )
        assert decompose.status_code == 200
        decompose_task_id = decompose.json()["task_id"]
        await client.post(
            f"/delivery-cycles/{cycle_id}/commands/start_product_modeling",
            json={"expected_state": "DISCOVERY"},
        )

    await run_supportdesk_decompose_worker(
        async_engine,
        decompose_task_id,
        correlation_id="journey-decompose",
        worker_id="journey-decompose",
        deterministic=True,
    )

    async with AsyncClient(
        transport=transport,
        base_url="http://test",
        headers={"Authorization": f"Bearer {operator_token}"},
    ) as client:
        await approve_scope_and_enter_architecture(
            client, project_id, cycle_id, async_engine=async_engine
        )

    async with factory() as session, session.begin():
        actor = await ensure_system_actor(session)
        await seed_approved_architecture(
            session, uuid.UUID(project_id), CommandContext(actor=actor, correlation_id="j-arch")
        )

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

    async with factory() as session, session.begin():
        from core.planning.task_plans.service import TaskPlanService

        actor = await ensure_system_actor(session)
        ctx = CommandContext(actor=actor, correlation_id="journey-plan")
        impl_specs = await seed_approved_implementation_specs_for_cycle(
            session, uuid.UUID(cycle_id), ctx
        )
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
        await client.post(
            f"/delivery-cycles/{cycle_id}/commands/start_development",
            json={"expected_state": "PLANNING"},
        )

    async with factory() as session, session.begin():
        actor = await ensure_system_actor(session)
        ctx = CommandContext(actor=actor, correlation_id="journey-dev")
        cycle_row = await session.get(DeliveryCycle, uuid.UUID(cycle_id))
        repo = await session.get(Repository, uuid.UUID(repo_id))
        project_row = await session.get(Project, uuid.UUID(project_id))
        assert cycle_row and repo and project_row and cycle_row.base_sha
        await complete_implementation_tasks_minimal_passing(
            session,
            ctx,
            project=project_row,
            repository=repo,
            cycle=cycle_row,
            base_sha=cycle_row.base_sha,
        )

    async with factory() as session, session.begin():
        from core.domain.actors.models import Actor
        from core.domain.enums import ActorRole

        system = await ensure_system_actor(session)
        human = Actor(
            kind=ActorKind.HUMAN,
            name="journey-approver",
            roles=[ActorRole.APPROVER.value, ActorRole.OPERATOR.value],
        )
        session.add(human)
        await session.flush()
        ic, release = await finish_assurance_and_release_for_cycle(
            session,
            CommandContext(actor=system, correlation_id="journey-rel"),
            CommandContext(actor=human, correlation_id="journey-rel-appr"),
            uuid.UUID(cycle_id),
        )

    async with factory() as session:
        cycle_final = await session.get(DeliveryCycle, uuid.UUID(cycle_id))
        assert cycle_final is not None and cycle_final.state == "COMPLETE"
        assert release.status == ReleaseStatus.RELEASED
        assert ic.integrated_sha is not None
