"""Phase 09 §12 — supportdesk_r1 IC with three mandatory ACs mapped to repo tests."""

from __future__ import annotations

import uuid
from dataclasses import dataclass

from core.commands.context import CommandContext
from core.domain.delivery_cycles.models import DeliveryCycle
from core.domain.enums import DeliveryCycleType
from core.domain.projects.models import Project
from core.integration.enums import ICStatus
from core.integration.models import IntegrationCandidate
from core.intelligence.code_index.canonical_service import CanonicalIndexService
from core.intelligence.code_index.enums import EntityType
from core.intelligence.code_index.parsers.imports import entity_key_for_qn
from core.product_model.models import AcceptanceCriterion, FeatureSpec
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from tests.fixtures.assurance_harness import (
    _refresh_sentinel_plan_and_execute,
    add_warden_review_evidence,
    patch_agentless_assurance,
)
from tests.fixtures.code_index_harness import SUPPORTDESK_R1, materialize_supportdesk_r1
from tests.fixtures.integration_harness import (
    IntegrationFixture,
    add_implementation_code_task,
    commit_files_in_worktree,
    create_and_run_integration,
)
from tests.fixtures.planning_workflow_harness import (
    seed_approved_architecture,
    seed_approved_implementation_specs_for_cycle,
)
from tests.fixtures.product_model_harness import supportdesk_three_ac_decomposition


@dataclass(frozen=True)
class SupportdeskAssuranceFixture:
    integration: IntegrationFixture
    ac_lineage_keys: tuple[str, ...]


TEST_CREATE_REF = entity_key_for_qn(
    EntityType.TEST.value,
    "tests/test_tickets_api.py",
    "tests.test_tickets_api.test_create_ticket",
)
TEST_UPDATE_REF = entity_key_for_qn(
    EntityType.TEST.value,
    "tests/test_ticket_service.py",
    "tests.test_ticket_service.test_update_status",
)


async def _approver_ctx(session: AsyncSession) -> CommandContext:
    from core.domain.actors.models import Actor
    from core.domain.enums import ActorKind, ActorRole

    actor = Actor(
        kind=ActorKind.HUMAN,
        name="supportdesk-assurance-approver",
        roles=[ActorRole.APPROVER.value, ActorRole.OPERATOR.value],
    )
    session.add(actor)
    await session.flush()
    return CommandContext(actor=actor, correlation_id="sd-assurance-approve")


async def _seed_supportdesk_product_three_ac(
    session: AsyncSession,
    project_id: uuid.UUID,
    cycle_id: uuid.UUID,
    ctx: CommandContext,
) -> None:
    from core.domain.approvals.service import ApprovalService
    from core.domain.enums import ApprovalStatus
    from core.product_model.models import ProductSource
    from core.product_model.service import ProductModelService
    from core.product_model.sources.service import ProductSourceService
    from core.product_model.specifications.scope import ScopeService

    ingest = await ProductSourceService().ingest(
        session,
        project_id=project_id,
        lineage_key="assurance-sd-seed",
        source_type="PRD",
        title="Assurance seed",
        mime_type="text/markdown",
        content_hash=f"assurance-sd-{cycle_id}",
        raw_storage_ref=f"inbound/assurance-sd/{cycle_id}",
        text="supportdesk assurance seed",
        ctx=ctx,
        delivery_cycle_id=cycle_id,
    )
    source = await session.get(ProductSource, ingest["product_source_id"])
    assert source is not None
    await ProductModelService().persist_proposal(
        session,
        project_id=project_id,
        delivery_cycle_id=cycle_id,
        product_source_version_id=source.id,
        execution_id=None,
        proposal=supportdesk_three_ac_decomposition(),
        ctx=ctx,
    )
    specs = await session.execute(select(FeatureSpec).where(FeatureSpec.project_id == project_id))
    spec_ids = [s.id for s in specs.scalars()]
    _scope_set, approval_id = await ScopeService().request_scope_approval(
        session,
        cycle_id,
        spec_ids,
        project_id,
        ctx,
    )
    approve_ctx = await _approver_ctx(session)
    await ApprovalService().decide(
        session,
        approval_id,
        ApprovalStatus.APPROVED,
        "assurance-supportdesk",
        approve_ctx,
    )


async def seed_supportdesk_assurance_fixture(
    session: AsyncSession,
    ctx: CommandContext,
    *,
    project_key_suffix: str = "sd-ac",
    service_test_body: str | None = None,
) -> SupportdeskAssuranceFixture:
    repo, sha = await materialize_supportdesk_r1(session, ctx)
    project = await session.get(Project, repo.project_id)
    assert project is not None
    cycle = DeliveryCycle(
        project_id=project.id,
        key=f"C-{project_key_suffix}",
        type=DeliveryCycleType.FEATURE_CHANGE,
        objective="supportdesk assurance",
        state="DEVELOPMENT",
        state_version=0,
        opened_by_actor_id=ctx.actor.id,
        repository_id=repo.id,
        base_sha=sha,
    )
    session.add(cycle)
    await session.flush()
    await CanonicalIndexService().promote_repository_snapshot(session, repo.id, sha, ctx)
    await _seed_supportdesk_product_three_ac(session, project.id, cycle.id, ctx)
    await seed_approved_architecture(session, project.id, ctx)
    impl_specs = await seed_approved_implementation_specs_for_cycle(session, cycle.id, ctx)

    spec_ids = [
        s.id
        for s in (
            await session.execute(select(FeatureSpec).where(FeatureSpec.project_id == project.id))
        ).scalars()
    ]
    ac_rows = (
        await session.execute(
            select(AcceptanceCriterion)
            .where(
                AcceptanceCriterion.feature_spec_id.in_(spec_ids),
                AcceptanceCriterion.mandatory.is_(True),
            )
            .order_by(AcceptanceCriterion.lineage_key)
        )
    ).scalars()
    ac_keys = tuple(a.lineage_key for a in ac_rows)
    assert ac_keys == ("AC-1", "AC-2", "AC-3"), ac_keys

    fixture_tests = SUPPORTDESK_R1 / "tests"
    fixture_app = SUPPORTDESK_R1 / "app"
    service_content = (
        service_test_body
        if service_test_body is not None
        else (fixture_tests / "test_ticket_service.py").read_text(encoding="utf-8")
    )
    api_content = (fixture_tests / "test_tickets_api.py").read_text(encoding="utf-8")
    pyproject_content = (SUPPORTDESK_R1 / "pyproject.toml").read_text(encoding="utf-8")
    main_content = (fixture_app / "main.py").read_text(encoding="utf-8")
    db_content = (fixture_app / "db.py").read_text(encoding="utf-8")
    repo_content = (fixture_app / "repositories" / "ticket_repository.py").read_text(
        encoding="utf-8"
    )

    integration = IntegrationFixture(project=project, repository=repo, cycle=cycle, base_sha=sha)
    bundle = await add_implementation_code_task(
        session,
        ctx,
        integration,
        title="Supportdesk traceability commit",
        key_prefix=project_key_suffix.replace("-", "")[:8],
    )
    from core.planning.models import TaskSpecRef

    for impl in impl_specs:
        bundle.task.implementation_spec_id = impl.id
        session.add(
            TaskSpecRef(
                task_id=bundle.task.id,
                ref_type="IMPLEMENTATION_SPEC",
                ref_id=impl.id,
                ref_version=impl.version,
            )
        )
        session.add(
            TaskSpecRef(
                task_id=bundle.task.id,
                ref_type="FEATURE_SPEC",
                ref_id=impl.feature_spec_id,
                ref_version=1,
            )
        )
    await session.flush()
    ac_test_mapping = [
        {"ac_ref": "AC-1", "test_ref": TEST_CREATE_REF},
        {"ac_ref": "AC-2", "test_ref": TEST_UPDATE_REF},
        {"ac_ref": "AC-3", "test_ref": TEST_UPDATE_REF},
    ]
    impl_output = {
        "summary": "traceability",
        "changed_files": [
            "docs/olympus-assurance.md",
            "pyproject.toml",
            "app/main.py",
            "app/db.py",
            "app/repositories/ticket_repository.py",
            "tests/test_tickets_api.py",
            "tests/test_ticket_service.py",
        ],
        "tests_added_or_changed": [
            "tests/test_tickets_api.py",
            "tests/test_ticket_service.py",
        ],
        "test_commands_run": ["pytest -q"],
        "principal_symbols": ["create_ticket", "update_status"],
        "ac_test_mapping": ac_test_mapping,
        "notes": [],
        "open_questions": [],
    }
    cc_sha = await commit_files_in_worktree(
        session,
        ctx,
        bundle,
        {
            "docs/olympus-assurance.md": "olympus assurance trace\n",
            "pyproject.toml": pyproject_content,
            "app/main.py": main_content,
            "app/db.py": db_content,
            "app/repositories/ticket_repository.py": repo_content,
            "tests/test_tickets_api.py": api_content,
            "tests/test_ticket_service.py": service_content,
        },
        message="chore: assurance traceability",
        principal_symbols=["create_ticket", "update_status"],
        implementation_result=impl_output,
    )
    assert cc_sha != sha, "candidate commit must advance from materialized base"
    return SupportdeskAssuranceFixture(integration=integration, ac_lineage_keys=ac_keys)


def _integration_checks_detail(artifact) -> str:
    import json

    from core.execution.artifacts import ArtifactStore

    payload: dict | None = None
    if isinstance(artifact.inline, dict):
        payload = artifact.inline
    else:
        payload = json.loads(ArtifactStore().read_bytes(artifact))
    output = str(payload.get("output", ""))[-4000:]
    meta = (
        f"compileall_rc={payload.get('compileall_rc')} "
        f"collect_rc={payload.get('collect_rc')} "
        f"pytest_rc={payload.get('pytest_rc')} ok={payload.get('ok')}"
    )
    return f"{meta}\n{output}"


async def supportdesk_ic_with_real_sentinel(
    session: AsyncSession,
    ctx: CommandContext,
    *,
    project_key_suffix: str,
    passing: bool = True,
) -> tuple[IntegrationCandidate, SupportdeskAssuranceFixture]:
    service_body = None
    if not passing:
        service_body = (
            "from app.db import SessionLocal\n"
            "from app.schemas.ticket import TicketCreate, TicketStatus\n"
            "from app.services.ticket_service import TicketService\n\n\n"
            "def test_update_status() -> None:\n"
            "    assert False, 'intentional failure for assurance gate'\n"
        )
    fixture = await seed_supportdesk_assurance_fixture(
        session,
        ctx,
        project_key_suffix=project_key_suffix,
        service_test_body=service_body,
    )
    with patch_agentless_assurance():
        ic = await create_and_run_integration(session, ctx, fixture.integration.cycle.id)
        if ic.status != ICStatus.READY or ic.integrated_sha is None:
            from core.assurance.models import Finding

            finding = (
                await session.execute(
                    select(Finding)
                    .where(Finding.integration_candidate_id == ic.id)
                    .order_by(Finding.created_at.desc())
                    .limit(1)
                )
            ).scalar_one_or_none()
            hint = finding.title if finding else "no finding"
            detail_snip = ""
            await session.refresh(ic)
            if ic.checks_artifact_id is not None:
                from core.domain.artifacts.models import Artifact

                artifact = await session.get(Artifact, ic.checks_artifact_id)
                if artifact is not None:
                    detail_snip = _integration_checks_detail(artifact)
            raise AssertionError(f"IC not READY: {ic.status} ({hint}){chr(10)}{detail_snip}")
        await add_warden_review_evidence(session, ic, ctx)
        await _refresh_sentinel_plan_and_execute(session, ctx, ic.id)
    return ic, fixture
