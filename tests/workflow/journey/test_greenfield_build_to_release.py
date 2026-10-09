"""GREENFIELD_BUILD pipeline through Release R1 (deterministic; SupportDesk R1 fixture Forge)."""

from __future__ import annotations

import uuid
from pathlib import Path

import pytest
from core.commands.context import CommandContext
from core.domain.delivery_cycles.models import DeliveryCycle
from core.domain.enums import ActorKind, RepositoryStatus, RevisionCause
from core.domain.execution_workspaces.models import ExecutionWorkspace
from core.domain.projects.models import Project
from core.domain.repositories.models import Repository, RepositoryRevision, RepositoryWorkspace
from core.release.enums import ReleaseStatus
from core.repositories.materialization_loop import MaterializationLoop
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from tests.fixtures.planning_workflow_harness import (
    build_task_plan_for_cycle,
    ensure_system_actor,
    seed_approved_architecture,
    seed_approved_implementation_specs_for_cycle,
    seed_supportdesk_product_and_approved_scope,
)
from tests.fixtures.release_harness import finish_assurance_and_release_for_cycle
from tests.journey.greenfield_dev import complete_implementation_tasks_minimal_passing

pytestmark = [pytest.mark.workflow, pytest.mark.integration, pytest.mark.git]


@pytest.mark.asyncio
async def test_greenfield_build_provisions_baseline_and_releases_r1(
    control_app,
    operator_token,
    async_engine,
) -> None:
    suffix = uuid.uuid4().hex[:8]
    transport = ASGITransport(app=control_app)
    async with AsyncClient(
        transport=transport,
        base_url="http://test",
        headers={"Authorization": f"Bearer {operator_token}"},
    ) as client:
        project = await client.post(
            "/projects",
            json={"key": f"SUPPORTDESK-{suffix}", "name": "SupportDesk Greenfield"},
        )
        assert project.status_code == 201
        project_id = project.json()["id"]
        cycle = await client.post(
            f"/projects/{project_id}/delivery-cycles",
            json={"type": "GREENFIELD_BUILD", "objective": "Journey 1 deterministic"},
        )
        assert cycle.status_code == 201
        cycle_id = cycle.json()["id"]
        repo_id = uuid.UUID(cycle.json()["repository_id"])

    factory = async_sessionmaker(bind=async_engine, class_=AsyncSession, expire_on_commit=False)
    baseline_sha: str
    async with factory() as session, session.begin():
        actor = await ensure_system_actor(session)
        ctx = CommandContext(actor=actor, correlation_id="gf-mat")
        for _ in range(10):
            await MaterializationLoop().run_once(session, ctx)
            repo = await session.get(Repository, repo_id)
            assert repo is not None
            if repo.status == RepositoryStatus.READY and repo.canonical_commit:
                baseline_sha = repo.canonical_commit
                break
        else:
            raise AssertionError("repository not READY after materialization")

    prd = Path(__file__).resolve().parents[2] / "fixtures" / "supportdesk" / "PRD.md"
    async with AsyncClient(
        transport=transport,
        base_url="http://test",
        headers={"Authorization": f"Bearer {operator_token}"},
    ) as client:
        up = await client.post(
            f"/projects/{project_id}/sources",
            params={"delivery_cycle_id": cycle_id},
            files={"file": ("PRD.md", prd.read_bytes(), "text/markdown")},
            headers={"Idempotency-Key": f"gf-{suffix}"},
        )
        assert up.status_code == 200, up.text
        pm = await client.post(
            f"/delivery-cycles/{cycle_id}/commands/start_product_modeling",
            json={"expected_state": "DISCOVERY"},
        )
        assert pm.status_code in (200, 409), pm.text

    async with factory() as session, session.begin():
        from core.domain.actors.models import Actor
        from core.domain.enums import ActorRole

        human = Actor(
            kind=ActorKind.HUMAN,
            name="gf-seed-approver",
            roles=[ActorRole.OPERATOR.value, ActorRole.APPROVER.value],
        )
        session.add(human)
        await session.flush()
        actor = await ensure_system_actor(session)
        sys_ctx = CommandContext(actor=actor, correlation_id="gf-seed")
        hum_ctx = CommandContext(actor=human, correlation_id="gf-seed-appr")
        await seed_supportdesk_product_and_approved_scope(
            session, uuid.UUID(project_id), uuid.UUID(cycle_id), hum_ctx
        )
        from core.domain.approvals.models import Approval
        from core.domain.enums import ApprovalStatus, ApprovalType
        from core.product_model.models import ScopeSet
        from core.product_model.specifications.scope import ScopeService

        scope_set = (
            await session.execute(
                select(ScopeSet)
                .where(ScopeSet.delivery_cycle_id == uuid.UUID(cycle_id))
                .order_by(ScopeSet.created_at.desc())
                .limit(1)
            )
        ).scalar_one()
        approval = (
            await session.execute(
                select(Approval).where(
                    Approval.approval_type == ApprovalType.SCOPE,
                    Approval.subject_id == scope_set.id,
                    Approval.status == ApprovalStatus.APPROVED,
                )
            )
        ).scalar_one()
        await ScopeService().on_scope_approved(session, scope_set.id, approval.id, hum_ctx)
        await seed_approved_architecture(session, uuid.UUID(project_id), sys_ctx)

    async with AsyncClient(
        transport=transport,
        base_url="http://test",
        headers={"Authorization": f"Bearer {operator_token}"},
    ) as client:
        arch = await client.post(
            f"/delivery-cycles/{cycle_id}/commands/start_architecture",
            json={"expected_state": "PRODUCT_MODEL"},
        )
        assert arch.status_code == 200, arch.text
        planning = await client.post(
            f"/delivery-cycles/{cycle_id}/commands/start_planning",
            json={"expected_state": "ARCHITECTURE"},
        )
        assert planning.status_code == 200, planning.text

    async with factory() as session, session.begin():
        from core.domain.actors.models import Actor
        from core.planning.task_plans.service import TaskPlanService

        actor = await ensure_system_actor(session)
        ctx = CommandContext(actor=actor, correlation_id="gf-plan")
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
        from tests.fixtures.approvals import approve_task_plan

        await approve_task_plan(session, plan_row.id)

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

    async with factory() as session, session.begin():
        actor = await ensure_system_actor(session)
        ctx = CommandContext(actor=actor, correlation_id="gf-dev")
        cycle_row = await session.get(DeliveryCycle, uuid.UUID(cycle_id))
        repo = await session.get(Repository, repo_id)
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
            name="gf-approver",
            roles=[ActorRole.APPROVER.value, ActorRole.OPERATOR.value],
        )
        session.add(human)
        await session.flush()
        ic, release = await finish_assurance_and_release_for_cycle(
            session,
            CommandContext(actor=system, correlation_id="gf-rel"),
            CommandContext(actor=human, correlation_id="gf-rel-appr"),
            uuid.UUID(cycle_id),
        )

    async with factory() as session:
        cycle_final = await session.get(DeliveryCycle, uuid.UUID(cycle_id))
        repo_final = await session.get(Repository, repo_id)
        assert cycle_final is not None and repo_final is not None
        assert cycle_final.state == "COMPLETE"
        assert release.status == ReleaseStatus.RELEASED
        assert repo_final.released_commit == ic.integrated_sha
        assert cycle_final.base_sha == baseline_sha
        revs = (
            await session.execute(
                select(RepositoryRevision)
                .where(RepositoryRevision.repository_id == repo_id)
                .order_by(RepositoryRevision.sequence)
            )
        ).scalars()
        causes = [r.cause for r in revs]
        assert RevisionCause.MATERIALIZED in causes
        assert RevisionCause.RELEASED in causes

        canonical_ws = await session.get(RepositoryWorkspace, repo_final.workspace_id)
        assert canonical_ws is not None
        from core.domain.candidate_commits.models import CandidateCommit
        from core.integration.models import IntegrationCandidateCommit

        cc_ids = (
            await session.execute(
                select(IntegrationCandidateCommit.candidate_commit_id).where(
                    IntegrationCandidateCommit.integration_candidate_id == ic.id
                )
            )
        ).scalars()
        for cc_id in cc_ids:
            cc = await session.get(CandidateCommit, cc_id)
            if cc and cc.execution_id:
                ex_ws = (
                    await session.execute(
                        select(ExecutionWorkspace).where(
                            ExecutionWorkspace.execution_id == cc.execution_id
                        )
                    )
                ).scalar_one()
                assert ex_ws.logical_location != canonical_ws.logical_location
