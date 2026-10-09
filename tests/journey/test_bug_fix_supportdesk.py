"""Journey 4 — Bug Fix: closed-ticket 500 → reproduction → repair → Release R3."""

from __future__ import annotations

import os
import uuid
from pathlib import Path
from unittest.mock import patch

import pytest
from core.commands.context import CommandContext
from core.domain.actors.models import Actor
from core.domain.delivery_cycles.models import DeliveryCycle
from core.domain.enums import (
    ActorKind,
    ActorRole,
    ProjectReadiness,
    SpecStatus,
    TaskStatus,
    WorkType,
)
from core.domain.projects.models import Project
from core.domain.repositories.models import Repository
from core.domain.tasks.models import Task
from core.planning.models import ImplementationSpec
from core.product_model.defects.models import Defect
from core.release.enums import ReleaseStatus
from core.runtime.model_router import build_providers
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker
from tests.fixtures.brownfield_phase12_harness import ensure_human_approver
from tests.fixtures.planning_workflow_harness import ensure_system_actor
from tests.fixtures.release_harness import finish_assurance_and_release_for_cycle
from tests.journey.bug_fix_acceptance import assert_bug_fix_phase15_acceptance
from tests.journey.bug_fix_dev import (
    complete_bug_fix_repair_tasks,
    complete_stale_code_change_tasks,
)
from tests.journey.bug_fix_helpers import (
    accept_task_plan_if_proposed,
    approve_repair_implementation_specs,
    drain_workers_factory,
    ensure_reproduction_started,
    maybe_advance_to_expected_behavior,
    maybe_apply_repair_implementation_spec_fallback,
    maybe_apply_root_cause_fallback,
    maybe_apply_triage_fallback,
    maybe_complete_expected_behavior_and_root_cause,
    maybe_complete_pre_repair_reproduction,
    run_bug_fix_regression_until_assurance,
    run_cycle_command,
    wait_for_development_tasks_complete,
    wait_for_task_plan_accepted,
    wait_for_task_plan_proposed,
)
from tests.journey.helpers import assert_bug_fix_live_llm_proof
from tests.journey.seed import seed_trusted_project
from tests.live_credentials import any_live_provider_configured

DEFECT_REPO = (
    Path(__file__).resolve().parents[1] / "fixtures" / "repos" / "supportdesk_defect_closed_update"
)
TRUSTED_SEED_DEFECT = (
    Path(__file__).resolve().parents[1] / "fixtures" / "supportdesk" / "trusted_seed_defect.yaml"
)
DEFECT_TEXT = (
    Path(__file__).resolve().parents[1] / "fixtures" / "supportdesk" / "defect_closed_update.md"
)

pytestmark = [
    pytest.mark.journey,
    pytest.mark.asyncio,
    pytest.mark.skipif(
        os.environ.get("LLM_LIVE_TESTS") != "1",
        reason="Set LLM_LIVE_TESTS=1 for Bug Fix journey",
    ),
]


@pytest.mark.asyncio
async def test_bug_fix_supportdesk_end_to_end(
    control_app,
    operator_token,
    async_engine: AsyncEngine,
) -> None:
    if not any_live_provider_configured():
        pytest.skip("No live provider API key configured")

    os.environ.setdefault("MODEL_PRODUCT_DECOMPOSITION", os.environ.get("MODEL_DEFAULT", ""))
    os.environ.setdefault("MODEL_PLANNING", os.environ.get("MODEL_DEFAULT", ""))
    os.environ.setdefault("MODEL_IMPLEMENTATION", os.environ.get("MODEL_DEFAULT", ""))
    os.environ.setdefault("MODEL_VERIFICATION_PLANNING", os.environ.get("MODEL_DEFAULT", ""))
    os.environ.setdefault("MODEL_REVIEW", os.environ.get("MODEL_DEFAULT", ""))
    from core.config.settings import clear_settings_cache
    from core.runtime.model_policy import clear_models_config_cache

    clear_settings_cache()
    clear_models_config_cache()

    factory = async_sessionmaker(bind=async_engine, class_=AsyncSession, expire_on_commit=False)
    project_id: uuid.UUID
    bf_cycle_id: uuid.UUID

    async with factory() as session, session.begin():
        actor = await ensure_system_actor(session)
        ctx = CommandContext(actor=actor, correlation_id="bf-seed")
        trusted = await seed_trusted_project(session, DEFECT_REPO, TRUSTED_SEED_DEFECT, ctx)
        project_id = trusted.project_id

    transport = ASGITransport(app=control_app)
    async with AsyncClient(
        transport=transport,
        base_url="http://test",
        headers={"Authorization": f"Bearer {operator_token}"},
    ) as client:
        resp = await client.post(
            f"/projects/{project_id}/defects",
            json={
                "title": "Updating a CLOSED ticket returns HTTP 500",
                "description": DEFECT_TEXT.read_text(encoding="utf-8"),
                "external_ref": f"BF-{uuid.uuid4().hex[:8]}",
            },
            headers={"Idempotency-Key": f"bf-intake-{uuid.uuid4().hex}"},
        )
        assert resp.status_code == 200, resp.text
        body = resp.json()
        result = body.get("result") if isinstance(body.get("result"), dict) else body
        raw_cycle = result.get("cycle_id") or result.get("delivery_cycle_id")
        assert raw_cycle is not None, result
        bf_cycle_id = uuid.UUID(str(raw_cycle))

    with patch("core.runtime.model_router.build_providers", side_effect=build_providers):
        from tests.journey.helpers import wait_for

        async def _defect_triaged() -> bool:
            async with factory() as session, session.begin():
                actor = await ensure_system_actor(session)
                ctx = CommandContext(actor=actor, correlation_id="bf-triage-fb")
                await maybe_apply_triage_fallback(session, bf_cycle_id, ctx)
            async with factory() as session:
                defect = (
                    await session.execute(
                        select(Defect).where(Defect.delivery_cycle_id == bf_cycle_id)
                    )
                ).scalar_one_or_none()
                if defect is not None and defect.status == "TRIAGED":
                    return True
            await drain_workers_factory(factory, correlation_prefix="bf-triage", rounds=2)
            async with factory() as session:
                defect = (
                    await session.execute(
                        select(Defect).where(Defect.delivery_cycle_id == bf_cycle_id)
                    )
                ).scalar_one_or_none()
                return defect is not None and defect.status == "TRIAGED"

        await wait_for(_defect_triaged, timeout=300.0, interval=4.0)

        repro_round = {"n": 0}

        async def _expected_behavior_ready() -> bool:
            i = repro_round["n"]
            repro_round["n"] += 1
            async with factory() as session, session.begin():
                actor = await ensure_system_actor(session)
                ctx = CommandContext(actor=actor, correlation_id=f"bf-repro-{i}")
                await ensure_reproduction_started(session, bf_cycle_id, ctx)
                await maybe_complete_pre_repair_reproduction(
                    session,
                    bf_cycle_id,
                    ctx,
                    apply_reproduce_fallback=i >= 2,
                    run_deterministic_if_missing=i >= 2,
                )
                await maybe_advance_to_expected_behavior(session, bf_cycle_id, ctx)
            async with factory() as session:
                cycle = await session.get(DeliveryCycle, bf_cycle_id)
                if cycle is not None and cycle.state == "EXPECTED_BEHAVIOR":
                    return True
            await drain_workers_factory(factory, correlation_prefix=f"bf-repro-{i}", rounds=3)
            async with factory() as session:
                cycle = await session.get(DeliveryCycle, bf_cycle_id)
                return cycle is not None and cycle.state == "EXPECTED_BEHAVIOR"

        await wait_for(_expected_behavior_ready, timeout=480.0, interval=4.0)

        for i in range(50):
            await drain_workers_factory(factory, correlation_prefix=f"bf-eb-{i}", rounds=12)
            async with factory() as session, session.begin():
                actor = await ensure_system_actor(session)
                ctx = CommandContext(actor=actor, correlation_id=f"bf-eb-fb-{i}")
                if i >= 2:
                    await maybe_complete_expected_behavior_and_root_cause(session, bf_cycle_id, ctx)
                    await maybe_apply_repair_implementation_spec_fallback(session, bf_cycle_id, ctx)
                else:
                    await maybe_apply_root_cause_fallback(session, bf_cycle_id, ctx)
            async with factory() as session:
                cycle = await session.get(DeliveryCycle, bf_cycle_id)
                if cycle is not None and cycle.state == "ROOT_CAUSE":
                    repair = list(
                        (
                            await session.execute(
                                select(ImplementationSpec).where(
                                    ImplementationSpec.project_id == project_id,
                                    ImplementationSpec.kind == "REPAIR",
                                )
                            )
                        ).scalars()
                    )
                    if any(r.status in (SpecStatus.PROPOSED, SpecStatus.APPROVED) for r in repair):
                        break

        await drain_workers_factory(factory, correlation_prefix="bf-repair-spec", rounds=80)
        async with factory() as session, session.begin():
            actor = await ensure_system_actor(session)
            ctx = CommandContext(actor=actor, correlation_id="bf-repair-spec-fb")
            await maybe_complete_expected_behavior_and_root_cause(session, bf_cycle_id, ctx)
            await maybe_apply_repair_implementation_spec_fallback(session, bf_cycle_id, ctx)
        async with factory() as session:
            cycle = await session.get(DeliveryCycle, bf_cycle_id)
            repair_impl = list(
                (
                    await session.execute(
                        select(ImplementationSpec).where(
                            ImplementationSpec.project_id == project_id,
                            ImplementationSpec.kind == "REPAIR",
                        )
                    )
                ).scalars()
            )
            assert any(
                i.status in (SpecStatus.PROPOSED, SpecStatus.APPROVED) for i in repair_impl
            ), (
                "expected REPAIR ImplementationSpec after live root-cause / planning; "
                f"cycle_state={cycle.state if cycle else None} "
                f"repair_specs={[(i.status.value) for i in repair_impl]}"
            )

        async with factory() as session, session.begin():
            _human, human_ctx = await ensure_human_approver(session)
            await approve_repair_implementation_specs(session, bf_cycle_id, human_ctx)

        await drain_workers_factory(factory, correlation_prefix="bf-task-plan", rounds=40)
        await wait_for_task_plan_proposed(factory, bf_cycle_id)
        await drain_workers_factory(factory, correlation_prefix="bf-task-plan")
        async with factory() as session, session.begin():
            _human, human_ctx = await ensure_human_approver(session)
            await accept_task_plan_if_proposed(session, bf_cycle_id, human_ctx)
        await wait_for_task_plan_accepted(factory, bf_cycle_id)

        async with factory() as session, session.begin():
            actor = await ensure_system_actor(session)
            ctx = CommandContext(actor=actor, correlation_id="bf-dev")
            await run_cycle_command(session, bf_cycle_id, "start_development", "ROOT_CAUSE", ctx)

        terminal = {TaskStatus.COMPLETED, TaskStatus.FAILED, TaskStatus.CANCELLED}
        for _ in range(60):
            await drain_workers_factory(factory, correlation_prefix="bf-forge", rounds=15)
            async with factory() as session:
                pending = list(
                    (
                        await session.execute(
                            select(Task).where(
                                Task.delivery_cycle_id == bf_cycle_id,
                                Task.work_type == WorkType.CODE_CHANGE,
                                Task.status.not_in(tuple(terminal)),
                            )
                        )
                    ).scalars()
                )
                if not pending:
                    break

        async with factory() as session:
            dev_tasks = list(
                (
                    await session.execute(
                        select(Task).where(
                            Task.delivery_cycle_id == bf_cycle_id,
                            Task.work_type == WorkType.CODE_CHANGE,
                        )
                    )
                ).scalars()
            )
        assert dev_tasks, "expected CODE_CHANGE tasks after start_development"
        async with factory() as session, session.begin():
            actor = await ensure_system_actor(session)
            ctx = CommandContext(actor=actor, correlation_id="bf-dev-fallback")
            cycle_row = await session.get(DeliveryCycle, bf_cycle_id)
            repo_row = (
                await session.get(Repository, cycle_row.repository_id)
                if cycle_row and cycle_row.repository_id
                else None
            )
            assert cycle_row is not None and repo_row is not None and cycle_row.base_sha
            await complete_bug_fix_repair_tasks(
                session,
                ctx,
                repository=repo_row,
                cycle=cycle_row,
                base_sha=cycle_row.base_sha,
            )

        await wait_for_development_tasks_complete(factory, bf_cycle_id, timeout=600.0)

        async with factory() as session, session.begin():
            await complete_stale_code_change_tasks(session, bf_cycle_id)

        async with factory() as session, session.begin():
            actor = await ensure_system_actor(session)
            reg_ctx = CommandContext(actor=actor, correlation_id="bf-regression")
            await run_bug_fix_regression_until_assurance(factory, bf_cycle_id, reg_ctx)

        async with factory() as session, session.begin():
            actor = await ensure_system_actor(session)
            system_ctx = CommandContext(actor=actor, correlation_id="bf-assurance")
            human = Actor(
                kind=ActorKind.HUMAN,
                name="bf-journey-approver",
                roles=[ActorRole.APPROVER.value, ActorRole.OPERATOR.value],
            )
            session.add(human)
            await session.flush()
            human_ctx = CommandContext(actor=human, correlation_id="bf-assurance-human")
            ic, release = await finish_assurance_and_release_for_cycle(
                session,
                system_ctx,
                human_ctx,
                bf_cycle_id,
                live_assurance=False,
            )
        await drain_workers_factory(factory, correlation_prefix="bf-release", rounds=40)

    async with factory() as session:
        cycle = await session.get(DeliveryCycle, bf_cycle_id)
        project = await session.get(Project, project_id)
        defect = (
            await session.execute(select(Defect).where(Defect.delivery_cycle_id == bf_cycle_id))
        ).scalar_one()
        assert cycle is not None and cycle.state == "COMPLETE"
        assert project is not None
        assert project.readiness_state == ProjectReadiness.READY_FOR_CHANGE
        assert defect.status == "RELEASED"
        assert release.status == ReleaseStatus.RELEASED
        assert ic.integrated_sha is not None

        repo = await session.get(Repository, cycle.repository_id) if cycle.repository_id else None
        if repo and repo.canonical_commit:
            assert repo.canonical_commit == ic.integrated_sha

        await assert_bug_fix_live_llm_proof(session, bf_cycle_id)
        await assert_bug_fix_phase15_acceptance(
            session,
            project_id=project_id,
            cycle_id=bf_cycle_id,
            ic=ic,
            release=release,
        )
