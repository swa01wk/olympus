"""RL3.2 expected behaviour human gate."""

from __future__ import annotations

import uuid
from pathlib import Path
from typing import Any

import pytest
from core.commands.context import CommandContext
from core.commands.handlers import handle_approval_decide
from core.domain.approvals.models import Approval
from core.domain.delivery_cycles.models import DeliveryCycle
from core.domain.enums import ApprovalStatus, ApprovalType, KnowledgeClass, SpecStatus
from core.domain.task_contracts.models import TaskContract
from core.domain.tasks.models import Task
from core.product_model.defects.completion import BugFixCompletionService
from core.product_model.defects.models import Defect, ExpectedBehaviorResolution
from core.product_model.defects.orchestrator import BugFixOrchestrator
from core.product_model.defects.service import DefectService
from core.product_model.models import AcceptanceCriterion, FeatureSpec, KnowledgeItem
from core.scheduler.admission import AdmissionService
from core.state.guards import guard_registry
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from tests.fixtures.brownfield_phase12_harness import ensure_human_approver
from tests.journey.bug_fix_helpers import maybe_apply_triage_fallback
from tests.journey.seed import TrustedProjectSeed, seed_trusted_project

pytestmark = [pytest.mark.integration, pytest.mark.asyncio]

FIXTURES = Path(__file__).resolve().parents[2] / "fixtures"
DEFECT_REPO = FIXTURES / "repos" / "supportdesk_defect_closed_update"
TRUSTED_SEED_DEFECT = FIXTURES / "supportdesk" / "trusted_seed_defect.yaml"

PROPOSED_AC = {
    "statement": "Updating a CLOSED ticket is rejected with 409 Conflict",
    "given": "a ticket in CLOSED status",
    "when": "a client PATCHes the ticket",
    "then": "the API responds 409 Conflict and the ticket is unchanged",
}
UNDERSPECIFIED = {
    "classification": "UNDERSPECIFIED",
    "cited_ac_lineage_keys": [],
    "proposed_ac": PROPOSED_AC,
    "expected_behavior_statement": "PATCH on a CLOSED ticket must return 409",
    "questions": ["Should reopening a CLOSED ticket ever be allowed?"],
}
SPECIFIED = {
    "classification": "SPECIFIED",
    "cited_ac_lineage_keys": ["SPEC-FEAT-TICKETS/AC-TICKET-CLOSED-UPDATE-409"],
    "expected_behavior_statement": "PATCH on a CLOSED ticket must return 409",
}


async def _cycle_at_expected_behavior(
    session: AsyncSession,
    ctx: CommandContext,
    ref: str,
    *,
    suspected_baseline_keys: list[str] | None = None,
) -> tuple[TrustedProjectSeed, Defect, DeliveryCycle]:
    trusted = await seed_trusted_project(session, DEFECT_REPO, TRUSTED_SEED_DEFECT, ctx)
    defect = await DefectService().intake(
        session,
        project_id=trusted.project_id,
        title="CLOSED ticket update",
        description="PATCH on CLOSED ticket returns 500 not 409",
        source_type="test",
        external_ref=ref,
        inbound_event_id=None,
        ctx=ctx,
    )
    assert defect.delivery_cycle_id is not None
    await maybe_apply_triage_fallback(session, defect.delivery_cycle_id, ctx)
    if suspected_baseline_keys is not None:
        triage = dict(defect.triage or {})
        triage["suspected_baseline_keys"] = suspected_baseline_keys
        defect.triage = triage
    cycle = await session.get(DeliveryCycle, defect.delivery_cycle_id)
    assert cycle is not None
    cycle.state = "EXPECTED_BEHAVIOR"
    await session.flush()
    return trusted, defect, cycle


async def _resolve(
    session: AsyncSession,
    cycle: DeliveryCycle,
    output: dict[str, Any],
    ctx: CommandContext,
) -> ExpectedBehaviorResolution:
    started = await BugFixOrchestrator().schedule_expected_behavior(session, cycle.id, ctx)
    execution = await AdmissionService().admit_task(
        session, uuid.UUID(started["expected_behavior_task_id"]), ctx
    )
    await BugFixCompletionService().persist_from_execution(
        session, execution, "kira.expected_behavior", output, ctx
    )
    row = (
        await session.execute(
            select(ExpectedBehaviorResolution).where(
                ExpectedBehaviorResolution.execution_id == execution.id
            )
        )
    ).scalar_one()
    await session.refresh(cycle)
    return row


async def _decide(
    session: AsyncSession, approval_id: uuid.UUID, decision: ApprovalStatus, note: str
) -> CommandContext:
    _human, human_ctx = await ensure_human_approver(session)
    await handle_approval_decide(
        session,
        human_ctx,
        {"approval_id": str(approval_id), "decision": decision.value, "note": note},
    )
    return human_ctx


async def test_underspecified_raises_approval_and_blocks_root_cause(
    db_session, system_ctx: CommandContext
) -> None:
    _trusted, _defect, cycle = await _cycle_at_expected_behavior(
        db_session, system_ctx, "rl3-eb-under", suspected_baseline_keys=[]
    )
    row = await _resolve(db_session, cycle, UNDERSPECIFIED, system_ctx)

    assert row.approval_id is not None
    approval = await db_session.get(Approval, row.approval_id)
    assert approval is not None
    assert approval.approval_type == ApprovalType.EXPECTED_BEHAVIOR
    assert approval.subject_type == "expected_behavior_resolution"
    assert approval.status == ApprovalStatus.PENDING
    assert cycle.state == "EXPECTED_BEHAVIOR"
    guard = await guard_registry.evaluate("expected_behavior_resolved", db_session, cycle, None)
    assert not guard.ok
    assert "EXPECTED_BEHAVIOR_APPROVAL_PENDING" in guard.reasons

    review = await DefectService().resolution_review_payload(db_session, row)
    assert review["classification"] == "UNDERSPECIFIED"
    assert review["proposed_ac"]["then"] == PROPOSED_AC["then"]
    assert review["questions"] == UNDERSPECIFIED["questions"]


async def test_approve_makes_ac_canonical_and_starts_root_cause(
    db_session, system_ctx: CommandContext
) -> None:
    trusted, defect, cycle = await _cycle_at_expected_behavior(
        db_session, system_ctx, "rl3-eb-approve", suspected_baseline_keys=[]
    )
    row = await _resolve(db_session, cycle, UNDERSPECIFIED, system_ctx)
    assert row.approval_id is not None

    await _decide(db_session, row.approval_id, ApprovalStatus.APPROVED, "409 is correct")

    await db_session.refresh(cycle)
    assert cycle.state == "ROOT_CAUSE"
    old_spec = await db_session.get(FeatureSpec, trusted.feature_spec_id)
    assert old_spec is not None and old_spec.status == SpecStatus.SUPERSEDED
    new_spec = (
        await db_session.execute(
            select(FeatureSpec).where(
                FeatureSpec.feature_id == trusted.feature_id,
                FeatureSpec.status == SpecStatus.APPROVED,
            )
        )
    ).scalar_one()
    assert new_spec.version == old_spec.version + 1
    assert new_spec.approval_id == row.approval_id
    assert new_spec.content_hash != old_spec.content_hash
    acs = {
        ac.statement: ac
        for ac in (
            await db_session.execute(
                select(AcceptanceCriterion).where(
                    AcceptanceCriterion.feature_spec_id == new_spec.id
                )
            )
        ).scalars()
    }
    canonical = acs[PROPOSED_AC["statement"]]
    assert canonical.then == PROPOSED_AC["then"]
    assert canonical.change_kind == "ADDED"
    old_ac_count = (
        await db_session.execute(
            select(AcceptanceCriterion.id).where(AcceptanceCriterion.feature_spec_id == old_spec.id)
        )
    ).all()
    assert len(acs) == len(old_ac_count) + 1
    await db_session.refresh(defect)
    assert defect.expected_ac_ids == [str(canonical.id)]

    decision = (
        await db_session.execute(
            select(KnowledgeItem).where(
                KnowledgeItem.delivery_cycle_id == cycle.id,
                KnowledgeItem.knowledge_class == KnowledgeClass.DECISION,
            )
        )
    ).scalar_one()
    assert decision.statement.startswith("EXPECTED_BEHAVIOR ")
    assert decision.statement.endswith(": 409 is correct")


async def test_changes_requested_reruns_kira_with_note(
    db_session, system_ctx: CommandContext
) -> None:
    _trusted, _defect, cycle = await _cycle_at_expected_behavior(
        db_session, system_ctx, "rl3-eb-changes", suspected_baseline_keys=[]
    )
    row = await _resolve(db_session, cycle, UNDERSPECIFIED, system_ctx)
    assert row.approval_id is not None

    note = "Reopening must be allowed via an explicit reopen endpoint; say so"
    await _decide(db_session, row.approval_id, ApprovalStatus.CHANGES_REQUESTED, note)

    await db_session.refresh(cycle)
    assert cycle.state == "EXPECTED_BEHAVIOR"
    tasks = list(
        (
            await db_session.execute(
                select(Task)
                .where(
                    Task.delivery_cycle_id == cycle.id,
                    Task.title == "Resolve expected behavior",
                )
                .order_by(Task.created_at)
            )
        ).scalars()
    )
    assert len(tasks) == 2
    contract = await db_session.get(TaskContract, tasks[-1].current_contract_id)
    assert contract is not None
    snap = contract.body["_snapshot"]
    assert snap["revision_feedback"] == note
    assert "UNDERSPECIFIED" in snap["previous_output_json"]
    assert snap["defect_description"], "revision must keep the original task inputs"
    assert snap["triage_json"]


async def test_rejected_keeps_defect_at_expected_behavior(
    db_session, system_ctx: CommandContext
) -> None:
    _trusted, _defect, cycle = await _cycle_at_expected_behavior(
        db_session, system_ctx, "rl3-eb-reject", suspected_baseline_keys=[]
    )
    row = await _resolve(db_session, cycle, UNDERSPECIFIED, system_ctx)
    assert row.approval_id is not None

    await _decide(db_session, row.approval_id, ApprovalStatus.REJECTED, "Not a 409 case")

    await db_session.refresh(cycle)
    assert cycle.state == "EXPECTED_BEHAVIOR"
    approval = await db_session.get(Approval, row.approval_id)
    assert approval is not None and approval.decision_note == "Not a 409 case"
    guard = await guard_registry.evaluate("expected_behavior_resolved", db_session, cycle, None)
    assert not guard.ok


async def test_specified_without_contradictions_needs_no_approval(
    db_session, system_ctx: CommandContext
) -> None:
    _trusted, _defect, cycle = await _cycle_at_expected_behavior(
        db_session, system_ctx, "rl3-eb-specified", suspected_baseline_keys=[]
    )
    row = await _resolve(db_session, cycle, SPECIFIED, system_ctx)

    assert row.contradicted_baseline_ids == []
    assert row.approval_id is None
    assert cycle.state == "ROOT_CAUSE"


async def test_specified_with_contradicted_baseline_raises_approval(
    db_session, system_ctx: CommandContext
) -> None:
    _trusted, _defect, cycle = await _cycle_at_expected_behavior(
        db_session, system_ctx, "rl3-eb-contradicted", suspected_baseline_keys=["BL-TICKET-CREATE"]
    )
    row = await _resolve(db_session, cycle, SPECIFIED, system_ctx)

    assert len(row.contradicted_baseline_ids) == 1
    assert row.approval_id is not None
    assert cycle.state == "EXPECTED_BEHAVIOR"
    review = await DefectService().resolution_review_payload(db_session, row)
    assert [b["lineage_key"] for b in review["contradicted_baselines"]] == ["BL-TICKET-CREATE"]
    assert review["contradicted_baselines"][0]["then"] == "HTTP 201"


async def test_approval_no_longer_counts_when_resolution_changes(
    db_session, system_ctx: CommandContext
) -> None:
    _trusted, _defect, cycle = await _cycle_at_expected_behavior(
        db_session, system_ctx, "rl3-eb-hash", suspected_baseline_keys=["BL-TICKET-CREATE"]
    )
    row = await _resolve(db_session, cycle, SPECIFIED, system_ctx)
    assert row.approval_id is not None
    await _decide(db_session, row.approval_id, ApprovalStatus.APPROVED, "")
    await db_session.refresh(cycle)
    assert cycle.state == "ROOT_CAUSE"

    row.statement = "PATCH on a CLOSED ticket must return 422"
    await db_session.flush()
    guard = await guard_registry.evaluate("expected_behavior_resolved", db_session, cycle, None)
    assert not guard.ok
    assert "EXPECTED_BEHAVIOR_APPROVAL_PENDING" in guard.reasons
