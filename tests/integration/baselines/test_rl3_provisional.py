"""RL3.6 — provisional baselines for accepted known gaps."""

from __future__ import annotations

import uuid
from collections.abc import AsyncIterator

import pytest
from apps.control_api.deps import get_db
from apps.control_api.main import create_app
from core.assurance.coverage import CoverageService
from core.assurance.enums import (
    EvidenceProducer,
    EvidenceResult,
    EvidenceType,
    GateStatus,
    GateType,
    ObligationReason,
    ObligationStatus,
)
from core.assurance.evidence import EvidenceService
from core.assurance.models import Finding, Gate, VerificationObligation
from core.commands.context import CommandContext
from core.domain.delivery_cycles.models import DeliveryCycle
from core.domain.enums import (
    DeliveryCycleType,
    EntityStatus,
    KnowledgeClass,
    KnowledgeItemStatus,
    ModelOrigin,
    SpecKind,
    SpecStatus,
)
from core.domain.projects.models import Project
from core.integration.enums import FindingSeverity
from core.integration.models import IntegrationCandidate
from core.intelligence.baselines.enums import (
    BaselineActivation,
    BaselineCheckKind,
    BaselineStatus,
)
from core.intelligence.baselines.models import BehavioralBaseline
from core.intelligence.baselines.proposals import BaselineProposalService
from core.intelligence.baselines.provisional import known_gaps_for_baseline
from core.intelligence.baselines.service import BaselineService
from core.intelligence.recovered_specs.promotion import PromotionService
from core.product_model.models import Capability, Feature, FeatureSpec, KnowledgeItem
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from tests.fixtures.assurance_harness import (
    finalize_all_pending_gates,
    gate_by_type,
    human_finalize_ctx,
    ready_ic_with_sentinel_evidence,
)
from tests.fixtures.brownfield_phase12_harness import ensure_human_approver

pytestmark = [pytest.mark.integration, pytest.mark.asyncio]

GAP_KEY = "PY_FUNCTION:src/tickets.py::close_ticket"
OTHER_KEY = "PY_FUNCTION:src/tickets.py::list_tickets"
GAP_STATEMENT = "Behaviour of closing an already CLOSED ticket is unverified"


async def _seed_onboarding(
    session: AsyncSession, ctx: CommandContext, key: str
) -> tuple[DeliveryCycle, FeatureSpec]:
    project = Project(key=key, name=key)
    session.add(project)
    await session.flush()
    cycle = DeliveryCycle(
        project_id=project.id,
        key=f"C-{key}",
        type=DeliveryCycleType.BROWNFIELD_ONBOARDING,
        objective="onboard",
        state="BASELINE",
        state_version=0,
        opened_by_actor_id=ctx.actor.id,
        base_sha="a" * 40,
    )
    session.add(cycle)
    await session.flush()
    spec = await _recovered_spec(session, project.id)
    return cycle, spec


async def _recovered_spec(session: AsyncSession, project_id: uuid.UUID) -> FeatureSpec:
    cap = Capability(
        project_id=project_id,
        key=f"CAP-{uuid.uuid4().hex[:6]}",
        name="Tickets",
        description="Ticket handling",
        status=EntityStatus.APPROVED,
        origin=ModelOrigin.RECOVERED,
        source_refs=[],
    )
    session.add(cap)
    await session.flush()
    feat = Feature(
        project_id=project_id,
        capability_id=cap.id,
        key=f"FEAT-{uuid.uuid4().hex[:6]}",
        name="Close ticket",
        description="Close tickets",
        status=EntityStatus.APPROVED,
        origin=ModelOrigin.RECOVERED,
        source_refs=[],
    )
    session.add(feat)
    await session.flush()
    spec = FeatureSpec(
        project_id=project_id,
        feature_id=feat.id,
        lineage_key=f"REC-{uuid.uuid4().hex[:6]}",
        version=1,
        status=SpecStatus.PROMOTED,
        spec_kind=SpecKind.RECOVERED,
        body={"behavior": "Close", "summary": "Close", "inputs": [], "outputs": [], "rules": []},
        content_hash=uuid.uuid4().hex,
        confidence="HIGH",
    )
    session.add(spec)
    await session.flush()
    return spec


async def _scout_uncertainty(
    session: AsyncSession, cycle: DeliveryCycle, stable_key: str, statement: str = GAP_STATEMENT
) -> KnowledgeItem:
    item = KnowledgeItem(
        project_id=cycle.project_id,
        delivery_cycle_id=cycle.id,
        knowledge_class=KnowledgeClass.UNCERTAINTY,
        statement=statement,
        provenance={
            "origin": "SCOUT",
            "why": "no test exercises this branch",
            "citations": [{"ref_type": "CODE_ENTITY", "ref": stable_key}],
        },
        status=KnowledgeItemStatus.ACTIVE,
    )
    session.add(item)
    await session.flush()
    return item


async def _accept_known_gap(
    session: AsyncSession, cycle: DeliveryCycle, human_ctx: CommandContext, stable_key: str
) -> KnowledgeItem:
    item = await _scout_uncertainty(session, cycle, stable_key)
    await PromotionService().decide(
        session, cycle.id, "UNCERTAINTY", item.id, "ACCEPT_KNOWN_GAP", "known gap", human_ctx
    )
    assert item.provenance.get("accepted_known_gap") is True
    return item


async def _characterization_baseline(
    session: AsyncSession,
    cycle: DeliveryCycle,
    spec: FeatureSpec,
    ctx: CommandContext,
    exercised: list[str],
) -> BehavioralBaseline:
    assert cycle.base_sha is not None
    return await BaselineProposalService().create_from_characterization(
        session,
        cycle,
        spec.id,
        f"AC-{uuid.uuid4().hex[:6]}",
        given="a ticket",
        when="it is closed",
        then="its status is CLOSED",
        check_kind=BaselineCheckKind.EXISTING_TEST,
        check_ref=f"tests/test_tickets.py::test_{uuid.uuid4().hex[:6]}",
        exercised=exercised,
        sha=cycle.base_sha,
        ctx=ctx,
    )


async def _establish_pass(
    session: AsyncSession, cycle: DeliveryCycle, bl: BehavioralBaseline, ctx: CommandContext
) -> None:
    ev = await EvidenceService().record(
        session,
        project_id=cycle.project_id,
        delivery_cycle_id=cycle.id,
        integration_candidate_id=None,
        commit_sha=bl.established_sha,
        evidence_type=EvidenceType.UNIT_TEST,
        result=EvidenceResult.PASS,
        subject_type="BASELINE",
        subject_id=bl.id,
        check_ref=bl.check_ref,
        producer=EvidenceProducer.SENTINEL,
        ctx=ctx,
    )
    bl.established_evidence_id = ev.id
    await session.flush()


async def test_baseline_created_on_accepted_known_gap_is_provisional(
    db_session, system_ctx
) -> None:
    cycle, spec = await _seed_onboarding(db_session, system_ctx, "rl3-prov-create")
    _, human_ctx = await ensure_human_approver(db_session)
    await _accept_known_gap(db_session, cycle, human_ctx, GAP_KEY)
    await _scout_uncertainty(db_session, cycle, OTHER_KEY, statement="Not accepted yet")

    on_gap = await _characterization_baseline(
        db_session, cycle, spec, system_ctx, [GAP_KEY, "PY_FUNCTION:src/x.py::y"]
    )
    off_gap = await _characterization_baseline(db_session, cycle, spec, system_ctx, [OTHER_KEY])

    assert on_gap.provisional is True
    assert await known_gaps_for_baseline(db_session, on_gap) == [GAP_STATEMENT]
    assert off_gap.provisional is False
    assert await known_gaps_for_baseline(db_session, off_gap) == []


async def test_auto_activation_marks_known_gap_baseline_provisional(db_session, system_ctx) -> None:
    cycle, spec = await _seed_onboarding(db_session, system_ctx, "rl3-prov-auto")
    _, human_ctx = await ensure_human_approver(db_session)
    on_gap = await _characterization_baseline(db_session, cycle, spec, system_ctx, [GAP_KEY])
    off_gap = await _characterization_baseline(db_session, cycle, spec, system_ctx, [OTHER_KEY])
    assert on_gap.provisional is False
    await _establish_pass(db_session, cycle, on_gap, system_ctx)
    await _establish_pass(db_session, cycle, off_gap, system_ctx)

    await _accept_known_gap(db_session, cycle, human_ctx, GAP_KEY)
    activated = await BaselineService().try_auto_activate_for_spec(db_session, spec.id, system_ctx)

    assert {bl.id for bl in activated} == {on_gap.id, off_gap.id}
    for bl in (on_gap, off_gap):
        assert bl.status == BaselineStatus.ACTIVE
        assert bl.activation == BaselineActivation.AUTO_DETERMINISTIC
    assert on_gap.provisional is True
    assert off_gap.provisional is False


async def test_activate_decision_clears_provisional(db_session, system_ctx) -> None:
    cycle, spec = await _seed_onboarding(db_session, system_ctx, "rl3-prov-human")
    _, human_ctx = await ensure_human_approver(db_session)
    await _accept_known_gap(db_session, cycle, human_ctx, GAP_KEY)
    bl = await _characterization_baseline(db_session, cycle, spec, system_ctx, [GAP_KEY])
    assert bl.provisional is True
    await _establish_pass(db_session, cycle, bl, system_ctx)

    await PromotionService().decide(
        db_session, cycle.id, "BASELINE", bl.id, "ACTIVATE", None, human_ctx
    )

    refreshed = await db_session.get(BehavioralBaseline, bl.id)
    assert refreshed is not None
    assert refreshed.status == BaselineStatus.ACTIVE
    assert refreshed.activation == BaselineActivation.HUMAN
    assert refreshed.provisional is False


async def test_baseline_api_exposes_provisional_and_known_gaps(db_session, system_ctx) -> None:
    cycle, spec = await _seed_onboarding(db_session, system_ctx, "rl3-prov-api")
    _, human_ctx = await ensure_human_approver(db_session)
    await _accept_known_gap(db_session, cycle, human_ctx, GAP_KEY)
    on_gap = await _characterization_baseline(db_session, cycle, spec, system_ctx, [GAP_KEY])
    off_gap = await _characterization_baseline(db_session, cycle, spec, system_ctx, [OTHER_KEY])

    async def _override_db() -> AsyncIterator[AsyncSession]:
        yield db_session

    app = create_app()
    app.dependency_overrides[get_db] = _override_db
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        listed = await client.get(f"/projects/{cycle.project_id}/baselines")
        single = await client.get(f"/baselines/{on_gap.id}")

    assert listed.status_code == 200, listed.text
    by_id = {row["id"]: row for row in listed.json()}
    assert by_id[str(on_gap.id)]["provisional"] is True
    assert by_id[str(on_gap.id)]["provisional_known_gaps"] == [GAP_STATEMENT]
    assert by_id[str(off_gap.id)]["provisional"] is False
    assert by_id[str(off_gap.id)]["provisional_known_gaps"] == []
    assert single.status_code == 200, single.text
    assert single.json()["provisional"] is True
    assert single.json()["provisional_known_gaps"] == [GAP_STATEMENT]


async def _finalize_with_failing_provisional_baseline(
    session: AsyncSession, ctx: CommandContext, project_key: str
) -> tuple[IntegrationCandidate, BehavioralBaseline, list[Gate]]:
    ic, lineage, fixture = await ready_ic_with_sentinel_evidence(
        session, ctx, project_key=project_key, passing=True
    )
    assert ic.integrated_sha is not None
    cycle = await session.get(DeliveryCycle, fixture.cycle.id)
    assert cycle is not None
    spec = await session.get(FeatureSpec, lineage.feature_spec_id)
    assert spec is not None
    _, human_ctx = await ensure_human_approver(session)
    await _accept_known_gap(session, cycle, human_ctx, GAP_KEY)
    bl = await _characterization_baseline(session, cycle, spec, ctx, [GAP_KEY])
    assert bl.provisional is True

    obligation = VerificationObligation(
        delivery_cycle_id=cycle.id,
        integration_candidate_id=ic.id,
        gate_type=GateType.BASELINE.value,
        subject_type="BASELINE",
        subject_id=bl.id,
        subject_key=bl.lineage_key,
        required=not bl.provisional,
        allowed_evidence_types=["UNIT_TEST", "API_TEST", "INTEGRATION_TEST"],
        reason=ObligationReason.BASELINE_REQUIRED,
        source_refs=[{"type": "BASELINE", "id": str(bl.id)}],
        status=ObligationStatus.OPEN,
    )
    session.add(obligation)
    await session.flush()
    await EvidenceService().record(
        session,
        project_id=cycle.project_id,
        delivery_cycle_id=cycle.id,
        integration_candidate_id=ic.id,
        commit_sha=ic.integrated_sha,
        evidence_type=EvidenceType.UNIT_TEST,
        result=EvidenceResult.FAIL,
        subject_type="BASELINE",
        subject_id=bl.id,
        check_ref=bl.check_ref,
        producer=EvidenceProducer.SENTINEL,
        ctx=ctx,
        obligation_id=obligation.id,
    )
    await CoverageService().recompute_for_ic(session, ic.id, ctx)

    fin_ctx = await human_finalize_ctx(session)
    gates = await finalize_all_pending_gates(session, ic.id, fin_ctx)
    return ic, bl, gates


@pytest.mark.git
async def test_failing_provisional_baseline_does_not_fail_baseline_gate(
    db_session, system_ctx
) -> None:
    ic, bl, gates = await _finalize_with_failing_provisional_baseline(
        db_session, system_ctx, "rl3-prov-gate"
    )

    baseline_gate = gate_by_type(gates, GateType.BASELINE)
    assert baseline_gate.status == GateStatus.PASS, baseline_gate.reasons
    blocking = (
        await db_session.execute(
            select(Finding.id).where(
                Finding.integration_candidate_id == ic.id,
                Finding.blocking.is_(True),
            )
        )
    ).all()
    assert blocking == []


@pytest.mark.git
async def test_failing_provisional_baseline_yields_minor_risk_finding(
    db_session, system_ctx
) -> None:
    ic, bl, _ = await _finalize_with_failing_provisional_baseline(
        db_session, system_ctx, "rl3-prov-find"
    )

    findings = (
        (
            await db_session.execute(
                select(Finding).where(
                    Finding.integration_candidate_id == ic.id,
                    Finding.title == f"Provisional baseline contradicted: {bl.lineage_key}",
                )
            )
        )
        .scalars()
        .all()
    )
    assert len(findings) == 1
    finding = findings[0]
    assert finding.category == "RISK"
    assert finding.severity == FindingSeverity.MINOR
    assert finding.blocking is False
    assert finding.detail["baseline_id"] == str(bl.id)
    assert finding.detail["known_gap"] is True
    assert finding.detail["known_gaps"] == [GAP_STATEMENT]
