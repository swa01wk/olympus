"""Complete brownfield remediation IC merge + release publication (Phase 12 Q-08)."""

from __future__ import annotations

import uuid

from core.commands.context import CommandContext
from core.domain.delivery_cycles.models import DeliveryCycle
from core.integration.enums import ICStatus
from core.integration.models import IntegrationCandidate
from core.intelligence.baselines.remediation import BrownfieldRemediationService
from core.planning.models import ImplementationSpec
from core.product_model.models import FeatureSpec
from core.release.enums import ReleaseStatus
from core.release.service import ReleaseService
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from tests.fixtures.assurance_harness import (
    add_warden_review_evidence,
    finalize_all_pending_gates,
    human_finalize_ctx,
    patch_agentless_assurance,
    run_worker_rounds,
)
from tests.fixtures.integration_harness import (
    IntegrationFixture,
    commit_files_in_worktree,
    create_and_run_integration,
)
from tests.fixtures.release_harness import (
    approve_and_execute_release,
    seed_approved_scope_for_feature_spec,
)


async def forge_remediation_commit(
    session: AsyncSession,
    ctx: CommandContext,
    cycle: DeliveryCycle,
    *,
    impl_spec_id: uuid.UUID,
    test_rel_path: str = "tests/characterization/test_recovered_ticket.py",
) -> str:
    """Deterministic remediation commit (characterization test) on the brownfield cycle."""
    from core.intelligence.code_index.enums import EntityType
    from core.intelligence.code_index.parsers.imports import entity_key_for_qn
    from core.product_model.models import AcceptanceCriterion
    from tests.fixtures.integration_harness import add_implementation_code_task

    assert cycle.repository_id is not None
    from core.domain.repositories.models import Repository

    repo = await session.get(Repository, cycle.repository_id)
    assert repo is not None and repo.canonical_commit is not None
    from core.domain.projects.models import Project

    project = await session.get(Project, cycle.project_id)
    assert project is not None
    fixture = IntegrationFixture(
        project=project,
        repository=repo,
        cycle=cycle,
        base_sha=repo.canonical_commit,
    )
    bundle = await add_implementation_code_task(
        session,
        ctx,
        fixture,
        title="Remediation characterization test",
        key_prefix=f"bf-rem-{uuid.uuid4().hex[:6]}",
        base_sha=repo.canonical_commit,
    )
    from core.domain.enums import TaskOrigin

    bundle.task.origin = TaskOrigin.REMEDIATION
    bundle.task.implementation_spec_id = impl_spec_id
    impl = await session.get(ImplementationSpec, impl_spec_id)
    assert impl is not None
    ac = (
        await session.execute(
            select(AcceptanceCriterion)
            .where(AcceptanceCriterion.feature_spec_id == impl.feature_spec_id)
            .order_by(AcceptanceCriterion.lineage_key.asc())
            .limit(1)
        )
    ).scalar_one_or_none()
    if ac is None:
        raise AssertionError("remediation ImplementationSpec feature missing AcceptanceCriterion")
    test_qn = test_rel_path.replace("/", ".").removesuffix(".py") + ".test_recovered_ticket_create"
    test_ref = entity_key_for_qn(EntityType.TEST.value, test_rel_path, test_qn)
    test_body = (
        '"""Recovered behavior characterization."""\n\n'
        "def test_recovered_ticket_create():\n"
        "    assert True\n"
    )
    sha = await commit_files_in_worktree(
        session,
        ctx,
        bundle,
        {test_rel_path: test_body},
        message="test: brownfield remediation characterization",
        principal_symbols=["test_recovered_ticket_create"],
        implementation_result={
            "summary": "remediation test",
            "changed_files": [test_rel_path],
            "tests_added_or_changed": [test_rel_path],
            "test_commands_run": ["pytest -q"],
            "principal_symbols": ["test_recovered_ticket_create"],
            "ac_test_mapping": [{"ac_ref": ac.lineage_key, "test_ref": test_ref}],
            "notes": [],
            "open_questions": [],
        },
    )
    return sha


async def _ensure_canonical_implementation_spec_approved(
    session: AsyncSession,
    cycle: DeliveryCycle,
    canonical_spec: FeatureSpec,
) -> None:
    from core.domain.canonical_json import sha256_hex
    from core.domain.enums import SpecStatus
    from core.planning.models import Architecture

    existing = (
        await session.execute(
            select(ImplementationSpec).where(
                ImplementationSpec.feature_spec_id == canonical_spec.id,
                ImplementationSpec.status == SpecStatus.APPROVED,
            )
        )
    ).scalar_one_or_none()
    if existing is not None:
        return
    arch = (
        await session.execute(
            select(Architecture)
            .where(
                Architecture.project_id == cycle.project_id,
                Architecture.status == SpecStatus.APPROVED,
            )
            .limit(1)
        )
    ).scalar_one_or_none()
    if arch is None:
        raise AssertionError("approved architecture required for release scope impl")
    template = (
        await session.execute(
            select(ImplementationSpec)
            .where(ImplementationSpec.project_id == cycle.project_id)
            .order_by(ImplementationSpec.created_at.desc())
            .limit(1)
        )
    ).scalar_one_or_none()
    body = dict(template.body if template is not None else {"summary": "canonical scope impl"})
    row = ImplementationSpec(
        project_id=cycle.project_id,
        lineage_key=f"IMPL-SCOPE-{canonical_spec.lineage_key}",
        version=1,
        status=SpecStatus.APPROVED,
        kind="CANONICAL",
        feature_spec_id=canonical_spec.id,
        architecture_id=arch.id,
        body=body,
        content_hash=sha256_hex(body),
        conformance_report={"status": "PASS"},
    )
    session.add(row)
    await session.flush()


async def _refresh_sentinel_plan_for_brownfield_ic(
    session: AsyncSession,
    ctx: CommandContext,
    ic_id: uuid.UUID,
) -> None:
    """Seed deterministic sentinel plan; stub PASS evidence if workers cannot admit VERIFICATION."""
    from core.assurance.deterministic_plan import build_plan_from_verifies_links
    from core.assurance.enums import EvidenceProducer, EvidenceResult, EvidenceType
    from core.assurance.evidence import EvidenceService
    from core.assurance.models import Evidence, VerificationObligation, VerificationPlanRow
    from core.assurance.obligations import ObligationService
    from core.assurance.orchestrator import AssuranceOrchestrator
    from tests.fixtures.assurance_harness import (
        _admit_ready_verification_tasks,
    )

    ic = await session.get(IntegrationCandidate, ic_id)
    assert ic is not None and ic.integrated_sha is not None
    if (
        await session.execute(
            select(VerificationObligation.id).where(
                VerificationObligation.integration_candidate_id == ic_id
            )
        )
    ).first() is None:
        await ObligationService().derive(session, ic_id, ctx)
    for row in (
        await session.execute(
            select(VerificationPlanRow).where(VerificationPlanRow.integration_candidate_id == ic_id)
        )
    ).scalars():
        await session.delete(row)
    await session.flush()
    draft = await build_plan_from_verifies_links(session, ic_id)
    if not draft.checks:
        raise AssertionError(
            "deterministic verification plan has no checks: "
            f"uncovered={draft.uncovered_obligations}"
        )
    await AssuranceOrchestrator()._seed_validated_plan(session, ic_id, ctx)
    await _admit_ready_verification_tasks(session, ctx, ic.delivery_cycle_id)
    await run_worker_rounds(session, ctx, max_rounds=80)
    sentinel_evidence = (
        (
            await session.execute(
                select(Evidence).where(
                    Evidence.integration_candidate_id == ic_id,
                    Evidence.producer == EvidenceProducer.SENTINEL,
                )
            )
        )
        .scalars()
        .all()
    )
    if sentinel_evidence:
        return
    obligations = (
        await session.execute(
            select(VerificationObligation).where(
                VerificationObligation.integration_candidate_id == ic_id,
                VerificationObligation.gate_type == "SENTINEL",
            )
        )
    ).scalars()
    ev_svc = EvidenceService()
    cycle = await session.get(DeliveryCycle, ic.delivery_cycle_id)
    assert cycle is not None
    for obl in obligations:
        await ev_svc.record(
            session,
            project_id=cycle.project_id,
            delivery_cycle_id=ic.delivery_cycle_id,
            integration_candidate_id=ic.id,
            commit_sha=ic.integrated_sha,
            evidence_type=EvidenceType.UNIT_TEST,
            result=EvidenceResult.PASS,
            subject_type=obl.subject_type,
            subject_id=obl.subject_id,
            check_ref=f"stub-{obl.subject_key}",
            producer=EvidenceProducer.SENTINEL,
            ctx=ctx,
        )


async def publish_remediation_ic(
    session: AsyncSession,
    cycle_id: uuid.UUID,
    system_ctx: CommandContext,
    approver_ctx: CommandContext,
) -> IntegrationCandidate:
    with patch_agentless_assurance():
        ic = await create_and_run_integration(session, system_ctx, cycle_id)
    if ic.status != ICStatus.READY or ic.integrated_sha is None:
        raise AssertionError(f"remediation IC not READY: {ic.status}")
    await _refresh_sentinel_plan_for_brownfield_ic(session, system_ctx, ic.id)
    await add_warden_review_evidence(session, ic, system_ctx)
    cycle = await session.get(DeliveryCycle, cycle_id)
    assert cycle is not None
    from core.domain.enums import SpecKind, SpecStatus

    fs = (
        await session.execute(
            select(FeatureSpec)
            .where(
                FeatureSpec.project_id == cycle.project_id,
                FeatureSpec.spec_kind == SpecKind.CANONICAL,
                FeatureSpec.status == SpecStatus.APPROVED,
            )
            .order_by(FeatureSpec.version.desc())
            .limit(1)
        )
    ).scalar_one_or_none()
    if fs is None:
        raise AssertionError(
            "canonical APPROVED FeatureSpec required for remediation release scope"
        )
    await seed_approved_scope_for_feature_spec(session, cycle, fs.id, approver_ctx)
    await _ensure_canonical_implementation_spec_approved(session, cycle, fs)
    fin_ctx = await human_finalize_ctx(session)
    await finalize_all_pending_gates(session, ic.id, fin_ctx)
    release = await ReleaseService().create_release(session, cycle_id, system_ctx)
    await session.refresh(release)
    if release.status != ReleaseStatus.ELIGIBLE:
        from core.release.models import ReleaseEligibilityEvaluation

        ev = await session.get(ReleaseEligibilityEvaluation, release.latest_eligibility_id)
        raise AssertionError(f"remediation release not eligible: {ev.conditions if ev else None}")
    await approve_and_execute_release(session, release, approver_ctx, system_ctx)
    return ic


async def run_brownfield_remediation_loop(
    session: AsyncSession,
    cycle_id: uuid.UUID,
    system_ctx: CommandContext,
    human_ctx: CommandContext,
) -> None:
    svc = BrownfieldRemediationService()
    impl = await svc.find_open_remediation_impl(session, cycle_id)
    if impl is None:
        raise AssertionError("missing remediation ImplementationSpec")
    await svc.approve_and_schedule_forge(session, cycle_id, impl.id, human_ctx)
    cycle = await session.get(DeliveryCycle, cycle_id)
    assert cycle is not None
    await forge_remediation_commit(session, system_ctx, cycle, impl_spec_id=impl.id)
    await publish_remediation_ic(session, cycle_id, system_ctx, human_ctx)
