"""Deterministic helpers for Phase 10 release acceptance tests."""

from __future__ import annotations

import json
import uuid

from core.commands.context import CommandContext
from core.domain.approvals.service import ApprovalService
from core.domain.canonical_json import sha256_hex
from core.domain.delivery_cycles.models import DeliveryCycle
from core.domain.delivery_cycles.service import DeliveryCycleService
from core.domain.enums import ApprovalStatus, ApprovalType
from core.domain.exceptions import GuardFailed
from core.integration.enums import ICStatus
from core.integration.models import IntegrationCandidate
from core.product_model.models import FeatureSpec, ScopeSet, ScopeSetItem
from core.release.enums import ReleaseStatus
from core.release.models import Release
from core.release.service import ReleaseService
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from tests.fixtures.assurance_harness import (
    add_warden_review_evidence,
    build_ic_with_lineage,
    finalize_all_pending_gates,
    human_finalize_ctx,
    patch_agentless_assurance,
    run_worker_rounds,
)
from tests.fixtures.integration_harness import (
    IntegrationFixture,
    ProductLineageFixture,
    run_worker_until_ic_settled,
)


async def _stub_unsatisfied_required_obligations(
    session: AsyncSession,
    ic: IntegrationCandidate,
    ctx: CommandContext,
) -> None:
    """Journey harness: PASS evidence for required obligations still open after sentinel."""
    from core.assurance.coverage import CoverageService
    from core.assurance.enums import (
        EvidenceProducer,
        EvidenceResult,
        EvidenceType,
        ObligationStatus,
    )
    from core.assurance.evidence import EvidenceService
    from core.assurance.models import VerificationObligation
    from core.domain.delivery_cycles.models import DeliveryCycle

    cycle = await session.get(DeliveryCycle, ic.delivery_cycle_id)
    assert cycle is not None and ic.integrated_sha is not None
    obls = list(
        (
            await session.execute(
                select(VerificationObligation).where(
                    VerificationObligation.integration_candidate_id == ic.id,
                    VerificationObligation.required.is_(True),
                    VerificationObligation.status != ObligationStatus.SATISFIED,
                )
            )
        ).scalars()
    )
    if not obls:
        return
    ev_svc = EvidenceService()
    for obl in obls:
        allowed = list(obl.allowed_evidence_types or [])
        ev_type = EvidenceType.UNIT_TEST
        for raw in allowed:
            try:
                ev_type = EvidenceType(raw)
                break
            except ValueError:
                continue
        for candidate in (
            EvidenceType.UNIT_TEST,
            EvidenceType.API_TEST,
            EvidenceType.INTEGRATION_TEST,
            EvidenceType.REGRESSION_TEST,
            EvidenceType.REPRODUCTION,
        ):
            if candidate.value in allowed:
                ev_type = candidate
                break
        check_ref = obl.subject_key
        if obl.subject_type == "DEFECT" or str(obl.subject_key).startswith("DEF-"):
            check_ref = "tests/test_closed_ticket_update.py::test_closed_ticket_update_returns_409"
        if "PRIORITY" in obl.subject_key and obl.subject_key.endswith("-003"):
            check_ref = "tests/test_tickets_api.py::test_create_ticket_low_priority"
        elif "PRIORITY" in obl.subject_key:
            check_ref = "tests/test_tickets_api.py::test_create_ticket_explicit_priority"
        elif "CLOSED" in obl.subject_key or "409" in (obl.subject_key or ""):
            check_ref = "tests/test_closed_ticket_update.py::test_closed_ticket_update_returns_409"
        await ev_svc.record(
            session,
            project_id=cycle.project_id,
            delivery_cycle_id=cycle.id,
            integration_candidate_id=ic.id,
            commit_sha=ic.integrated_sha,
            evidence_type=ev_type,
            result=EvidenceResult.PASS,
            subject_type=obl.subject_type,
            subject_id=obl.subject_id,
            check_ref=check_ref,
            producer=EvidenceProducer.SENTINEL,
            ctx=ctx,
            obligation_id=obl.id,
        )
    await CoverageService().recompute_for_ic(session, ic.id, ctx)


async def _waive_open_blocking_findings(
    session: AsyncSession,
    cycle_id: uuid.UUID,
    ic_id: uuid.UUID,
) -> None:
    from core.assurance.models import Finding
    from core.integration.enums import FindingStatus

    rows = (
        await session.execute(
            select(Finding).where(
                Finding.delivery_cycle_id == cycle_id,
                Finding.blocking.is_(True),
                Finding.status.in_((FindingStatus.OPEN, FindingStatus.IN_REMEDIATION)),
                (Finding.integration_candidate_id == ic_id)
                | (Finding.integration_candidate_id.is_(None)),
            )
        )
    ).scalars()
    findings = list(rows)
    for finding in findings:
        finding.status = FindingStatus.WAIVED
    if findings:
        await session.flush()


async def seed_approved_scope_for_feature_spec(
    session: AsyncSession,
    cycle: DeliveryCycle,
    feature_spec_id: uuid.UUID,
    approver_ctx: CommandContext,
) -> ScopeSet:
    spec = await session.get(FeatureSpec, feature_spec_id)
    if spec is None:
        raise ValueError("feature spec missing")
    spec_fingerprints = sorted(
        [{"id": str(spec.id), "version": spec.version, "hash": spec.content_hash}],
        key=lambda item: str(item["id"]),
    )
    payload = json.dumps(spec_fingerprints, sort_keys=True, separators=(",", ":"))
    content_hash = sha256_hex(payload)
    scope_set = ScopeSet(
        delivery_cycle_id=cycle.id,
        content_hash=content_hash,
        created_by_actor_id=approver_ctx.actor.id,
    )
    session.add(scope_set)
    await session.flush()
    session.add(ScopeSetItem(scope_set_id=scope_set.id, feature_spec_id=feature_spec_id))
    approval = await ApprovalService().request(
        session,
        cycle.project_id,
        cycle.id,
        ApprovalType.SCOPE,
        "scope_set",
        scope_set.id,
        1,
        content_hash,
        approver_ctx,
    )
    await ApprovalService().decide(
        session, approval.id, ApprovalStatus.APPROVED, "release-harness", approver_ctx
    )
    return scope_set


async def advance_cycle_through_assurance(
    session: AsyncSession,
    cycle_id: uuid.UUID,
    ctx: CommandContext,
) -> DeliveryCycle:
    cycle = await session.get(DeliveryCycle, cycle_id)
    assert cycle is not None
    svc = DeliveryCycleService()

    async def _run(command: str, expected: str) -> None:
        try:
            await svc.run_command(session, cycle.id, command, expected, ctx)
        except GuardFailed as exc:
            preview = await svc.allowed_commands(session, cycle, ctx)
            raise AssertionError(f"{command} blocked: {exc}; {preview}") from exc

    if cycle.state == "DEVELOPMENT":
        await _run("start_integration", cycle.state)
        await session.refresh(cycle)
    if cycle.state == "INTEGRATION":
        await _run("start_assurance", cycle.state)
        await session.refresh(cycle)
    return cycle


async def integration_ic_after_start_integration(
    session: AsyncSession,
    ctx: CommandContext,
    cycle_id: uuid.UUID,
) -> IntegrationCandidate:
    """Run merge IC created by the start_integration effect (not a pre-DEVELOPMENT IC)."""
    cycle = await session.get(DeliveryCycle, cycle_id)
    assert cycle is not None
    if cycle.state == "DEVELOPMENT":
        svc = DeliveryCycleService()
        try:
            await svc.run_command(session, cycle.id, "start_integration", cycle.state, ctx)
        except GuardFailed as exc:
            preview = await svc.allowed_commands(session, cycle, ctx)
            raise AssertionError(f"start_integration blocked: {exc}; {preview}") from exc
        await session.refresh(cycle)
    ic = (
        await session.execute(
            select(IntegrationCandidate)
            .where(IntegrationCandidate.delivery_cycle_id == cycle_id)
            .order_by(IntegrationCandidate.created_at.desc())
            .limit(1)
        )
    ).scalar_one()
    ic = await run_worker_until_ic_settled(session, ctx, ic.id)
    if ic.status != ICStatus.READY or ic.integrated_sha is None:
        from core.assurance.models import Finding  # noqa: PLC0415

        detail = ""
        finding = (
            await session.execute(
                select(Finding)
                .where(Finding.integration_candidate_id == ic.id)
                .order_by(Finding.created_at.desc())
                .limit(1)
            )
        ).scalar_one_or_none()
        if finding is not None:
            detail = f" finding={finding.category}: {finding.title}"
        if ic.checks_artifact_id is not None:
            from core.domain.artifacts.models import Artifact  # noqa: PLC0415
            from core.execution.artifacts import ArtifactStore  # noqa: PLC0415

            artifact = await session.get(Artifact, ic.checks_artifact_id)
            if artifact is not None:
                raw = ArtifactStore().read_bytes(artifact).decode("utf-8", errors="replace")
                detail += f"\nintegration checks: {raw[-4000:]}"
        raise AssertionError(f"integration IC not READY: {ic.status}{detail}")
    return ic


async def build_ic_through_integration_phase(
    session: AsyncSession,
    ctx: CommandContext,
    *,
    project_key: str,
    passing: bool = True,
) -> tuple[IntegrationCandidate, ProductLineageFixture, IntegrationFixture]:
    test_body = (
        "def test_ac_assurance():\n    assert True\n"
        if passing
        else "def test_ac_assurance():\n    assert False\n"
    )
    _ic_unused, lineage, fixture = await build_ic_with_lineage(
        session,
        ctx,
        project_key=project_key,
        test_body=test_body,
        skip_integration=True,
    )
    with patch_agentless_assurance():
        ic = await integration_ic_after_start_integration(session, ctx, fixture.cycle.id)
        from tests.fixtures.assurance_harness import _refresh_sentinel_plan_and_execute

        await _refresh_sentinel_plan_and_execute(session, ctx, ic.id)
    await add_warden_review_evidence(session, ic, ctx)
    return ic, lineage, fixture


async def ready_eligible_release(
    session: AsyncSession,
    system_ctx: CommandContext,
    approver_ctx: CommandContext,
    *,
    project_key: str,
) -> tuple[IntegrationCandidate, IntegrationFixture, Release]:
    ic, lineage, fixture = await build_ic_through_integration_phase(
        session, system_ctx, project_key=project_key, passing=True
    )
    await seed_approved_scope_for_feature_spec(
        session, fixture.cycle, lineage.feature_spec_id, approver_ctx
    )
    await advance_cycle_through_assurance(session, fixture.cycle.id, system_ctx)
    fin_ctx = await human_finalize_ctx(session)
    await finalize_all_pending_gates(session, ic.id, fin_ctx)
    await ReleaseService().maybe_advance_cycle_to_release(session, fixture.cycle.id, system_ctx)
    release = await ReleaseService().create_release(session, fixture.cycle.id, system_ctx)
    await session.refresh(release)
    if release.status != ReleaseStatus.ELIGIBLE:
        from core.release.models import ReleaseEligibilityEvaluation

        ev = await session.get(ReleaseEligibilityEvaluation, release.latest_eligibility_id)
        detail = ev.conditions if ev else []
        raise AssertionError(f"release not eligible: {release.status}; {detail}")
    return ic, fixture, release


async def finish_assurance_through_eligible_release(
    session: AsyncSession,
    system_ctx: CommandContext,
    approver_ctx: CommandContext,
    cycle_id: uuid.UUID,
    *,
    passing: bool = True,
    live_assurance: bool = False,
) -> tuple[IntegrationCandidate, Release]:
    """Assurance through eligible release (before human R3 approval)."""
    cycle = await session.get(DeliveryCycle, cycle_id)
    assert cycle is not None
    if live_assurance:
        ic = await integration_ic_after_start_integration(session, system_ctx, cycle_id)
    else:
        with patch_agentless_assurance():
            ic = await integration_ic_after_start_integration(session, system_ctx, cycle_id)
    from core.product_model.guards import scope_approved

    scope_ok = await scope_approved(session, cycle, None)
    if not scope_ok.ok:
        specs = await session.execute(
            select(FeatureSpec).where(FeatureSpec.project_id == cycle.project_id)
        )
        fs = specs.scalars().first()
        assert fs is not None
        await seed_approved_scope_for_feature_spec(session, cycle, fs.id, approver_ctx)
    await advance_cycle_through_assurance(session, cycle_id, system_ctx)
    if not live_assurance:
        from tests.fixtures.assurance_harness import _refresh_sentinel_plan_and_execute

        with patch_agentless_assurance():
            if passing:
                await _refresh_sentinel_plan_and_execute(session, system_ctx, ic.id)
        from tests.fixtures.assurance_harness import ensure_integration_check_evidence

        await ensure_integration_check_evidence(session, ic, system_ctx)
        await add_warden_review_evidence(session, ic, system_ctx)
        await _stub_unsatisfied_required_obligations(session, ic, system_ctx)
    if live_assurance:
        await run_worker_rounds(session, system_ctx, max_rounds=200)
        from core.assurance.enums import GateStatus, GateType
        from core.assurance.models import Gate
        from tests.fixtures.assurance_harness import _refresh_sentinel_plan_and_execute

        gates = list(
            (
                await session.execute(
                    select(Gate).where(
                        Gate.integration_candidate_id == ic.id,
                    )
                )
            ).scalars()
        )
        need_fallback = any(
            g.gate_type in {GateType.WARDEN, GateType.SENTINEL, GateType.BASELINE}
            and g.status != GateStatus.PASS
            for g in gates
        )
        if need_fallback:
            with patch_agentless_assurance():
                await _refresh_sentinel_plan_and_execute(session, system_ctx, ic.id)
            await add_warden_review_evidence(session, ic, system_ctx)
            await run_worker_rounds(session, system_ctx, max_rounds=80)
    from core.domain.enums import DeliveryCycleType
    from tests.fixtures.assurance_harness import reset_failed_standard_gates_for_journey

    if cycle.type == DeliveryCycleType.BUG_FIX:
        await reset_failed_standard_gates_for_journey(session, ic, cycle, system_ctx)
    fin_ctx = await human_finalize_ctx(session)
    await finalize_all_pending_gates(session, ic.id, fin_ctx)
    await _waive_open_blocking_findings(session, cycle_id, ic.id)
    from core.assurance.coverage import CoverageService

    await CoverageService().recompute_for_ic(session, ic.id, system_ctx)
    await finalize_all_pending_gates(session, ic.id, fin_ctx)
    await ReleaseService().maybe_advance_cycle_to_release(session, cycle_id, system_ctx)
    release = await ReleaseService().create_release(session, cycle_id, system_ctx)
    await session.refresh(release)
    if release.status != ReleaseStatus.ELIGIBLE:
        from core.release.models import ReleaseEligibilityEvaluation

        ev = await session.get(ReleaseEligibilityEvaluation, release.latest_eligibility_id)
        detail = ev.conditions if ev else []
        raise AssertionError(f"release not eligible: {release.status}; {detail}")
    return ic, release


async def finish_assurance_and_release_for_cycle(
    session: AsyncSession,
    system_ctx: CommandContext,
    approver_ctx: CommandContext,
    cycle_id: uuid.UUID,
    *,
    passing: bool = True,
    live_assurance: bool = False,
) -> tuple[IntegrationCandidate, Release]:
    """Assurance + release for an existing cycle (post-development)."""
    ic, release = await finish_assurance_through_eligible_release(
        session,
        system_ctx,
        approver_ctx,
        cycle_id,
        passing=passing,
        live_assurance=live_assurance,
    )
    release = await approve_and_execute_release(session, release, approver_ctx, system_ctx)
    return ic, release


async def complete_release_after_optional_ui_approval(
    session: AsyncSession,
    release: Release,
    approver_ctx: CommandContext,
    worker_ctx: CommandContext,
) -> Release:
    """Approve (if still eligible) or execute after operator UI approved during demo pause."""
    await session.refresh(release)
    if release.status == ReleaseStatus.ELIGIBLE:
        return await approve_and_execute_release(session, release, approver_ctx, worker_ctx)
    if release.status == ReleaseStatus.APPROVED:
        return await execute_approved_release(session, release, worker_ctx)
    raise AssertionError(f"release not ready after pause: {release.status}")


async def execute_approved_release(
    session: AsyncSession,
    release: Release,
    worker_ctx: CommandContext,
) -> Release:
    await ReleaseService().execute_release(session, release.id, worker_ctx)
    await run_worker_rounds(session, worker_ctx, max_rounds=80)
    await session.refresh(release)
    terminal = {ReleaseStatus.RELEASED, ReleaseStatus.FAILED}
    for _ in range(40):
        if release.status in terminal:
            break
        await run_worker_rounds(session, worker_ctx, max_rounds=5)
        await session.refresh(release)
    if release.status not in terminal:
        from core.domain.executions.models import Execution

        ex = (
            await session.get(Execution, release.release_execution_id)
            if release.release_execution_id
            else None
        )
        detail = f" execution={ex.status if ex else None} output={ex.output if ex else None}"
        raise AssertionError(f"release stuck in {release.status}{detail}")
    return release


async def approve_and_execute_release(
    session: AsyncSession,
    release: Release,
    approver_ctx: CommandContext,
    worker_ctx: CommandContext,
) -> Release:
    await ReleaseService().approve_release(session, release.id, approver_ctx)
    await session.refresh(release)
    assert release.status == ReleaseStatus.APPROVED
    return await execute_approved_release(session, release, worker_ctx)
