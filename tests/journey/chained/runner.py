"""Orchestrate DC-001 → DC-004 on one Project (Phase 19 §4.2)."""

from __future__ import annotations

import os
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING
from unittest.mock import patch

from core.commands.context import CommandContext
from core.domain.delivery_cycles.models import DeliveryCycle
from core.domain.delivery_cycles.service import DeliveryCycleService
from core.domain.enums import (
    ActorKind,
    ActorRole,
    DeliveryCycleType,
    ProjectReadiness,
    RepositoryStatus,
)
from core.domain.projects.models import Project
from core.domain.repositories.models import Repository
from core.product_model.changes.models import ChangeRequest
from core.release.enums import ReleaseStatus
from core.release.models import Release
from core.repositories.materialization_loop import MaterializationLoop
from core.runtime.model_router import build_providers
from core.runtime.providers.fake_provider import FakeProvider
from core.state.transition_service import TransitionService
from httpx import AsyncClient
from scripts.demo.chained.chaos import enable_chaos_for_stage
from scripts.demo.chained.external_push import (
    apply_defect_and_push_to_gitea,
    sync_repository_via_api,
)
from scripts.demo.chained.restart import restart_boundary
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker
from tests.fixtures.brownfield_phase12_harness import (
    advance_to_ready_for_change,
    ensure_human_approver,
    live_drain_spec_recovery,
    run_baseline_stage_workers,
    transition_validated_recovery_to_baseline,
)
from tests.fixtures.planning_workflow_harness import (
    approve_scope_and_enter_architecture,
    build_task_plan_for_cycle,
    ensure_system_actor,
    run_supportdesk_decompose_worker,
    seed_approved_architecture,
    seed_approved_implementation_specs_for_cycle,
)
from tests.fixtures.release_harness import (
    complete_release_after_optional_ui_approval,
    finish_assurance_and_release_for_cycle,
    finish_assurance_through_eligible_release,
)
from tests.journey.bug_fix_helpers import (
    accept_task_plan_if_proposed,
    approve_repair_implementation_specs,
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
from tests.journey.chained.clarifications import answer_open_clarifications
from tests.journey.chained.greenfield_live import run_live_greenfield_after_decompose
from tests.journey.chained.worker_drain import bugfix_drain_with_chaos
from tests.journey.feature_change_helpers import drain_workers_factory as gf_drain
from tests.journey.feature_change_live_pipeline import run_feature_change_live_journey
from tests.journey.gitea_integration_helpers import (
    attach_repository_to_gitea,
    create_gitea_issue,
    create_gitea_repo,
    deliver_issue_webhook,
    ensure_integration_sources,
    ensure_journey_secret_key,
    gitea_api_token,
    gitea_base_url,
    gitea_owner_login,
    gitea_reachable,
)
from tests.journey.greenfield_dev import complete_implementation_tasks_with_supportdesk_r1

if TYPE_CHECKING:
    from scripts.demo.chained.driver import ChainedDriver

PRD = Path(__file__).resolve().parents[2] / "fixtures" / "supportdesk" / "PRD.md"
CHANGE_ISSUE = (
    Path(__file__).resolve().parents[2] / "fixtures" / "supportdesk" / "chained" / "change_issue.md"
)
DEFECT_ISSUE = (
    Path(__file__).resolve().parents[2] / "fixtures" / "supportdesk" / "chained" / "defect_issue.md"
)


@dataclass
class ChainedRunContext:
    async_engine: AsyncEngine
    client: AsyncClient
    operator_token: str
    human_token: str
    fingerprints: dict[str, tuple[str, str]] = field(default_factory=dict)
    chaos: bool = False
    project_id: uuid.UUID | None = None
    repository_id: uuid.UUID | None = None
    releases: dict[str, str] = field(default_factory=dict)
    cycles: dict[str, str] = field(default_factory=dict)


def _factory(engine: AsyncEngine) -> async_sessionmaker[AsyncSession]:
    return async_sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False)


async def _ready_ok() -> bool:
    return True


async def stage_dc001_greenfield(
    ctx: ChainedRunContext,
    driver: ChainedDriver | None = None,
) -> str:
    """Greenfield → Release R1; returns integrated_sha."""
    suffix = uuid.uuid4().hex[:6]
    project_key = os.environ.get("MVP_PROJECT_KEY", f"SUPPORTDESK-{suffix}")
    resp = await ctx.client.post(
        "/projects",
        json={"key": project_key, "name": "SupportDesk Chained MVP"},
    )
    resp.raise_for_status()
    project_id = resp.json()["id"]
    ctx.project_id = uuid.UUID(project_id)
    cycle_resp = await ctx.client.post(
        f"/projects/{project_id}/delivery-cycles",
        json={"type": "GREENFIELD_BUILD", "objective": "DC-001 chained MVP"},
    )
    cycle_resp.raise_for_status()
    cycle_id = cycle_resp.json()["id"]
    repo_id = cycle_resp.json()["repository_id"]
    ctx.repository_id = uuid.UUID(repo_id)
    ctx.cycles["DC-001"] = "IN_PROGRESS"

    factory = _factory(ctx.async_engine)
    async with factory() as session, session.begin():
        actor = await ensure_system_actor(session)
        mat_ctx = CommandContext(actor=actor, correlation_id="mvp-mat")
        for _ in range(12):
            await MaterializationLoop().run_once(session, mat_ctx)
            repo = await session.get(Repository, uuid.UUID(repo_id))
            if repo and repo.status == RepositoryStatus.READY and repo.canonical_commit:
                break

    up = await ctx.client.post(
        f"/projects/{project_id}/sources",
        params={"delivery_cycle_id": cycle_id},
        files={"file": ("PRD.md", PRD.read_bytes(), "text/markdown")},
        headers={"Idempotency-Key": f"mvp-prd-{suffix}"},
    )
    up.raise_for_status()
    source_id = up.json()["result"]["product_source_id"]
    decompose = await ctx.client.post(
        f"/sources/{source_id}/decompose",
        json={"delivery_cycle_id": cycle_id},
    )
    decompose.raise_for_status()
    decompose_task_id = decompose.json()["task_id"]
    await ctx.client.post(
        f"/delivery-cycles/{cycle_id}/commands/start_product_modeling",
        json={"expected_state": "DISCOVERY"},
    )

    live = os.environ.get("LLM_LIVE_TESTS") == "1"
    await run_supportdesk_decompose_worker(
        ctx.async_engine,
        decompose_task_id,
        correlation_id="mvp-decompose",
        worker_id="mvp-decompose",
        deterministic=not live,
    )

    from core.domain.enums import ClarificationStatus
    from core.domain.executions.models import Clarification

    async with factory() as session:
        _pending_cl = (
            (
                await session.execute(
                    select(Clarification).where(
                        Clarification.delivery_cycle_id == uuid.UUID(cycle_id),
                        Clarification.status == ClarificationStatus.OPEN,
                    )
                )
            )
            .scalars()
            .first()
        )
    _ = _pending_cl
    if live and _pending_cl is not None:
        async with factory() as session, session.begin():
            answered = await answer_open_clarifications(ctx.client, session, uuid.UUID(cycle_id))
        if answered:
            await gf_drain(factory, correlation_prefix="mvp-pre-rb-a-clarify", rounds=80)
            async with factory() as session:
                from core.domain.enums import SpecStatus
                from core.product_model.models import FeatureSpec

                proposed = (
                    (
                        await session.execute(
                            select(FeatureSpec).where(
                                FeatureSpec.project_id == uuid.UUID(project_id),
                                FeatureSpec.status == SpecStatus.PROPOSED,
                            )
                        )
                    )
                    .scalars()
                    .first()
                )
                if proposed is None:
                    decompose_resp = await ctx.client.post(
                        f"/sources/{source_id}/decompose",
                        json={"delivery_cycle_id": cycle_id},
                    )
                    if decompose_resp.status_code == 200:
                        await run_supportdesk_decompose_worker(
                            ctx.async_engine,
                            decompose_resp.json()["task_id"],
                            correlation_id="mvp-redecompose",
                            worker_id="mvp-redecompose",
                            deterministic=False,
                        )

    await restart_boundary(
        "RB-A",
        factory=factory,
        project_id=ctx.project_id,
        fingerprints=ctx.fingerprints,
        ready_probe=_ready_ok,
    )

    if driver:
        driver.maybe_pause("clarification:DC-001")

    await approve_scope_and_enter_architecture(
        ctx.client, project_id, cycle_id, async_engine=ctx.async_engine
    )

    use_live_greenfield = live and os.environ.get("MVP_PLANNING_SEEDS", "0") != "1"
    if use_live_greenfield:
        with patch("core.runtime.model_router.build_providers", side_effect=build_providers):
            await gf_drain(factory, correlation_prefix="mvp-post-clarify")
            await run_live_greenfield_after_decompose(
                client=ctx.client,
                async_engine=ctx.async_engine,
                project_id=project_id,
                cycle_id=cycle_id,
            )
    else:
        async with factory() as session, session.begin():
            actor = await ensure_system_actor(session)
            await seed_approved_architecture(
                session,
                uuid.UUID(project_id),
                CommandContext(actor=actor, correlation_id="mvp-arch"),
            )
        planning = await ctx.client.post(
            f"/delivery-cycles/{cycle_id}/commands/start_planning",
            json={"expected_state": "ARCHITECTURE"},
        )
        planning.raise_for_status()
        async with factory() as session, session.begin():
            from core.planning.task_plans.service import TaskPlanService

            actor = await ensure_system_actor(session)
            plan_ctx = CommandContext(actor=actor, correlation_id="mvp-plan")
            impl_specs = await seed_approved_implementation_specs_for_cycle(
                session, uuid.UUID(cycle_id), plan_ctx
            )
            plan = await build_task_plan_for_cycle(session, uuid.UUID(cycle_id), impl_specs)
            plan_row = await TaskPlanService().persist_proposed(
                session,
                delivery_cycle_id=uuid.UUID(cycle_id),
                plan=plan,
                implementation_spec_ids=[s.id for s in impl_specs],
                execution_id=None,
                ctx=plan_ctx,
            )
            from tests.fixtures.approvals import approve_task_plan

            await approve_task_plan(session, plan_row.id)
        await ctx.client.post(
            f"/delivery-cycles/{cycle_id}/commands/start_development",
            json={"expected_state": "PLANNING"},
        )
        async with factory() as session, session.begin():
            actor = await ensure_system_actor(session)
            dev_ctx = CommandContext(actor=actor, correlation_id="mvp-dev")
            cycle_row = await session.get(DeliveryCycle, uuid.UUID(cycle_id))
            repo = await session.get(Repository, uuid.UUID(repo_id))
            project_row = await session.get(Project, uuid.UUID(project_id))
            assert cycle_row and repo and project_row and cycle_row.base_sha
            await complete_implementation_tasks_with_supportdesk_r1(
                session,
                dev_ctx,
                project=project_row,
                repository=repo,
                cycle=cycle_row,
                base_sha=cycle_row.base_sha,
            )

    async with factory() as session, session.begin():
        from core.domain.actors.models import Actor

        system = await ensure_system_actor(session)
        human = Actor(
            kind=ActorKind.HUMAN,
            name="mvp-lead",
            roles=[ActorRole.APPROVER.value, ActorRole.OPERATOR.value],
        )
        session.add(human)
        await session.flush()
        ic, release = await finish_assurance_and_release_for_cycle(
            session,
            CommandContext(actor=system, correlation_id="mvp-rel"),
            CommandContext(actor=human, correlation_id="mvp-rel-appr"),
            uuid.UUID(cycle_id),
        )

    assert ic.integrated_sha
    ctx.releases["R1"] = ic.integrated_sha
    ctx.cycles["DC-001"] = "COMPLETE"
    return ic.integrated_sha


async def stage_dc002_brownfield(ctx: ChainedRunContext, s_r1: str) -> None:
    assert ctx.project_id and ctx.repository_id
    factory = _factory(ctx.async_engine)
    await restart_boundary(
        "RB-B",
        factory=factory,
        project_id=ctx.project_id,
        fingerprints=ctx.fingerprints,
        ready_probe=_ready_ok,
    )

    async with factory() as session, session.begin():
        actor = await ensure_system_actor(session)
        setup_ctx = CommandContext(actor=actor, correlation_id="mvp-bf-setup")
        cycle = await DeliveryCycleService().create(
            session,
            ctx.project_id,
            DeliveryCycleType.BROWNFIELD_ONBOARDING,
            "DC-002 brownfield onboarding",
            setup_ctx,
            repository_id=ctx.repository_id,
        )
        cycle.base_sha = s_r1
        await session.flush()
        await TransitionService().transition(
            session,
            "delivery_cycle",
            cycle.id,
            cycle.state,
            "start_code_index",
            setup_ctx,
        )
        cycle_id = cycle.id

    ctx.cycles["DC-002"] = "CODE_INDEX"

    with patch("core.runtime.model_router.build_providers", side_effect=build_providers):
        async with factory() as session, session.begin():
            actor = await ensure_system_actor(session)
            setup_ctx = CommandContext(actor=actor, correlation_id="mvp-bf-recovery")
            await TransitionService().transition(
                session,
                "delivery_cycle",
                cycle_id,
                "CODE_INDEX",
                "start_spec_recovery",
                setup_ctx,
            )
        await live_drain_spec_recovery(factory, cycle_id)

        async with factory() as session, session.begin():
            actor = await ensure_system_actor(session)
            system_ctx = CommandContext(actor=actor, correlation_id="mvp-bf-baseline")
            cycle = await transition_validated_recovery_to_baseline(session, cycle_id, system_ctx)
            characterize_fake = FakeProvider()
            await run_baseline_stage_workers(session, system_ctx, cycle.id, fake=characterize_fake)
            _human, human_ctx = await ensure_human_approver(session)
            bf_rules = (
                Path(__file__).resolve().parents[2]
                / "fixtures"
                / "supportdesk"
                / "chained"
                / "brownfield_review.yaml"
            )
            await advance_to_ready_for_change(
                session, cycle.id, system_ctx, human_ctx, review_rules_path=bf_rules
            )

    async with factory() as session:
        project = await session.get(Project, ctx.project_id)
        assert project is not None
        assert project.readiness_state == ProjectReadiness.READY_FOR_CHANGE
    ctx.cycles["DC-002"] = "READY"


async def stage_dc003_feature_change(ctx: ChainedRunContext) -> str:
    assert ctx.project_id
    factory = _factory(ctx.async_engine)
    await restart_boundary(
        "RB-C",
        factory=factory,
        project_id=ctx.project_id,
        fingerprints=ctx.fingerprints,
        ready_probe=_ready_ok,
    )

    fc_cycle_id: uuid.UUID
    mvp_gitea_repo: str | None = None
    if gitea_reachable() and os.environ.get("GITEA_API_TOKEN"):
        ensure_journey_secret_key()
        token = gitea_api_token()
        owner = gitea_owner_login(token)
        repo_name = f"supportdesk-mvp-{uuid.uuid4().hex[:8]}"
        mvp_gitea_repo = repo_name
        os.environ["MVP_GITEA_REPO"] = repo_name
        create_gitea_repo(owner, repo_name, token)
        body = CHANGE_ISSUE.read_text(encoding="utf-8")
        title = "Add ticket priority: LOW, MEDIUM, HIGH"
        issue_number, _external_ref = create_gitea_issue(
            owner,
            repo_name,
            token,
            title=title,
            body=body,
        )
        webhook_secret = f"mvp-wh-{uuid.uuid4().hex[:8]}"
        async with factory() as session, session.begin():
            actor = await ensure_system_actor(session)
            setup_ctx = CommandContext(actor=actor, correlation_id="mvp-fc-intake")
            await ensure_integration_sources(session, ctx.project_id, webhook_secret=webhook_secret)
            inbound = await deliver_issue_webhook(
                session,
                setup_ctx,
                project_id=ctx.project_id,
                owner=owner,
                repo_name=repo_name,
                issue_number=issue_number,
                title=title,
                body=body,
                webhook_secret=webhook_secret,
                event_id=f"mvp-fc-{issue_number}",
            )
            assert inbound["status"] == "ACCEPTED"
            cr = (
                await session.execute(
                    select(ChangeRequest).where(ChangeRequest.project_id == ctx.project_id)
                )
            ).scalar_one()
            fc_cycle_id = cr.delivery_cycle_id
            dup = await deliver_issue_webhook(
                session,
                setup_ctx,
                project_id=ctx.project_id,
                owner=owner,
                repo_name=repo_name,
                issue_number=issue_number,
                title=title,
                body=body,
                webhook_secret=webhook_secret,
                event_id=f"mvp-fc-{issue_number}",
            )
            assert dup["status"] == "DUPLICATE"
            if mvp_gitea_repo:
                remote_url = f"{gitea_base_url()}/{owner}/{mvp_gitea_repo}.git"
                repo_row = await session.get(Repository, ctx.repository_id)
                assert repo_row is not None
                await attach_repository_to_gitea(session, setup_ctx, repo_row, remote_url)
    else:
        async with factory() as session, session.begin():
            actor = await ensure_system_actor(session)
            setup_ctx = CommandContext(actor=actor, correlation_id="mvp-fc-local")
            cycle = await DeliveryCycleService().create(
                session,
                ctx.project_id,
                DeliveryCycleType.FEATURE_CHANGE,
                "DC-003 feature change",
                setup_ctx,
            )
            fc_cycle_id = cycle.id

    ctx.cycles["DC-003"] = "IN_DELIVERY"
    os.environ["MVP_CHAOS_CYCLE_ID"] = str(fc_cycle_id)
    ic, release = await run_feature_change_live_journey(
        factory,
        project_id=ctx.project_id,
        fc_cycle_id=fc_cycle_id,
        correlation_prefix="mvp-fc",
    )
    assert ic.integrated_sha and release.status == ReleaseStatus.RELEASED
    ctx.releases["R2"] = ic.integrated_sha
    ctx.cycles["DC-003"] = "COMPLETE"
    return ic.integrated_sha


async def stage_inject_external_defect(ctx: ChainedRunContext, s_r2: str) -> str:
    """Q-05 strategy A: probe 409 → inject → probe 500 → external push → sync."""
    if os.environ.get("MVP_INJECT_DEFECT", "1") != "1":
        return s_r2

    factory = _factory(ctx.async_engine)
    async with factory() as session:
        repo = await session.get(Repository, ctx.repository_id)
        if repo is None:
            return s_r2
        from core.domain.repositories.models import RepositoryWorkspace

        ws = (
            await session.execute(
                select(RepositoryWorkspace).where(RepositoryWorkspace.repository_id == repo.id)
            )
        ).scalar_one_or_none()
        if ws is None:
            return s_r2
        from core.repositories.workspace_locator import WorkspaceLocator

        try:
            repo_root = WorkspaceLocator().resolve(ws.storage_backend, ws.logical_location)
        except Exception:
            return s_r2

    s_d = s_r2
    try:
        if gitea_reachable() and os.environ.get("GITEA_API_TOKEN"):
            token = gitea_api_token()
            owner = gitea_owner_login(token)
            repo_name = os.environ.get("MVP_GITEA_REPO")
            if not repo_name:
                return s_r2
            gitea_url = os.environ.get("OLYMPUS_GITEA_URL", "http://127.0.0.1:3000")
            push = apply_defect_and_push_to_gitea(
                repo_root,
                gitea_url=gitea_url,
                owner=owner,
                repo_name=repo_name,
                token=token,
            )
            s_d = push.after_sha
            api_base = os.environ.get("OLYMPUS_API_BASE", "http://127.0.0.1:8000")
            sync = await sync_repository_via_api(api_base, ctx.human_token, ctx.repository_id)
            ctx.releases["S_D"] = s_d
            os.environ["MVP_LAST_SYNC_CLASSIFICATION"] = str(sync.get("classification"))
        else:
            from scripts.demo.chained.inject_defect import inject_defect_in_tree

            new_source = inject_defect_in_tree(repo_root)
            target = repo_root / "app/services/ticket_service.py"
            target.write_text(new_source, encoding="utf-8")
            s_d = s_r2
    except ValueError as exc:
        if "NO_TARGET" in str(exc) or "AMBIGUOUS" in str(exc) or "AC_ALREADY_VIOLATED" in str(exc):
            os.environ.setdefault("MVP_INJECT_DEFECT_SKIPPED", str(exc))
            return s_r2
        raise
    return s_d


async def stage_dc004_bug_fix(ctx: ChainedRunContext, driver: ChainedDriver | None = None) -> str:
    assert ctx.project_id and ctx.repository_id
    factory = _factory(ctx.async_engine)
    await restart_boundary(
        "RB-D",
        factory=factory,
        project_id=ctx.project_id,
        fingerprints=ctx.fingerprints,
        ready_probe=_ready_ok,
    )

    s_d = ctx.releases.get("S_D") or ctx.releases.get("R2", "")
    async with factory() as session, session.begin():
        actor = await ensure_system_actor(session)
        setup_ctx = CommandContext(actor=actor, correlation_id="mvp-bf-defect")
        cycle = await DeliveryCycleService().create(
            session,
            ctx.project_id,
            DeliveryCycleType.BUG_FIX,
            "DC-004 bug fix",
            setup_ctx,
            repository_id=ctx.repository_id,
        )
        cycle.base_sha = s_d or cycle.base_sha
        await session.flush()
        bf_cycle_id = cycle.id

    os.environ["MVP_CHAOS_CYCLE_ID"] = str(bf_cycle_id)
    with patch("core.runtime.model_router.build_providers", side_effect=build_providers):
        async with factory() as session, session.begin():
            actor = await ensure_system_actor(session)
            setup_ctx = CommandContext(actor=actor, correlation_id="mvp-bf-triage")
            await run_cycle_command(session, bf_cycle_id, "start_triage", "INTAKE", setup_ctx)
        if os.environ.get("MVP_CHAOS") == "1":
            await bugfix_drain_with_chaos(factory, bf_cycle_id, correlation_prefix="mvp-bf")
        else:
            from tests.journey.bug_fix_helpers import drain_workers_factory as bugfix_drain

            await bugfix_drain(factory, correlation_prefix="mvp-bf")
        await maybe_apply_triage_fallback(factory, bf_cycle_id)
        await ensure_reproduction_started(factory, bf_cycle_id)
        await maybe_complete_pre_repair_reproduction(factory, bf_cycle_id)
        await maybe_advance_to_expected_behavior(factory, bf_cycle_id)
        await maybe_complete_expected_behavior_and_root_cause(factory, bf_cycle_id)
        await maybe_apply_root_cause_fallback(factory, bf_cycle_id)
        await wait_for_task_plan_proposed(factory, bf_cycle_id)
        async with factory() as session, session.begin():
            _human, human_ctx = await ensure_human_approver(session)
            await approve_repair_implementation_specs(session, bf_cycle_id, human_ctx)
            await accept_task_plan_if_proposed(session, bf_cycle_id, human_ctx)
        await wait_for_task_plan_accepted(factory, bf_cycle_id)
        await maybe_apply_repair_implementation_spec_fallback(factory, bf_cycle_id)
        await wait_for_development_tasks_complete(factory, bf_cycle_id)
        await run_bug_fix_regression_until_assurance(factory, bf_cycle_id)

        async with factory() as session, session.begin():
            system = await ensure_system_actor(session)
            human, human_ctx = await ensure_human_approver(session)
            ic, release = await finish_assurance_through_eligible_release(
                session,
                CommandContext(actor=system, correlation_id="mvp-bf-rel"),
                human_ctx,
                bf_cycle_id,
            )
            release_id = release.id
            assert release.approval_id is not None

        if driver:
            driver.maybe_pause(
                "approve_release:DC-004",
                ui={
                    "project_id": str(release.project_id),
                    "cycle_id": str(bf_cycle_id),
                    "release_id": str(release_id),
                    "approval_id": str(release.approval_id),
                },
            )

        async with factory() as session, session.begin():
            system = await ensure_system_actor(session)
            human, human_ctx = await ensure_human_approver(session)
            release_row = await session.get(Release, release_id)
            assert release_row is not None
            release = await complete_release_after_optional_ui_approval(
                session,
                release_row,
                human_ctx,
                CommandContext(actor=system, correlation_id="mvp-bf-rel-exec"),
            )

    assert ic.integrated_sha
    ctx.releases["R3"] = ic.integrated_sha
    ctx.cycles["DC-004"] = "COMPLETE"
    return ic.integrated_sha


async def run_chained_mvp(ctx: ChainedRunContext, *, driver: ChainedDriver | None = None) -> None:
    chaos = ctx.chaos or (driver is not None and driver.config.chaos)
    if chaos:
        os.environ["MVP_CHAOS"] = "1"
        os.environ.setdefault("OLYMPUS_FAULTS", "1")
        enable_chaos_for_stage("dc003_forge")
        enable_chaos_for_stage("dc003_issue_close")
        enable_chaos_for_stage("dc004_sentinel")
        enable_chaos_for_stage("walkthrough_sse")
    s_r1 = await stage_dc001_greenfield(ctx, driver)
    await stage_dc002_brownfield(ctx, s_r1)
    s_r2 = await stage_dc003_feature_change(ctx)
    s_d = await stage_inject_external_defect(ctx, s_r2)
    ctx.releases["S_D"] = s_d
    await stage_dc004_bug_fix(ctx, driver)
