"""RL3 acceptance: a characterization baseline pins a bug; the approved fix retires it.

Mirrors the Kanban Lite run: the brownfield baseline recorded the buggy 500, the bug fix
proposes 409 as UNDERSPECIFIED, a human approves it, and release supersedes the old
baseline while activating a REPAIR regression baseline for the new AC.
"""

from __future__ import annotations

import uuid
from pathlib import Path

import pytest
from agents.kira.schemas import ImplementationSpecDraft
from core.assurance.enums import EvidenceResult, GateStatus, GateType
from core.assurance.models import Evidence, Gate, VerificationObligation
from core.commands.context import CommandContext
from core.commands.handlers import handle_approval_decide
from core.domain.approvals.models import Approval
from core.domain.delivery_cycles.models import DeliveryCycle
from core.domain.enums import ApprovalStatus, SpecStatus
from core.domain.executions.models import Execution
from core.domain.repositories.models import Repository
from core.integration.enums import ICStatus
from core.intelligence.baselines.authored import authored_test_path, store_authored_test
from core.intelligence.baselines.enums import (
    BaselineActivation,
    BaselineCheckKind,
    BaselineSource,
    BaselineStatus,
)
from core.intelligence.baselines.models import BaselineSet, BaselineSetItem, BehavioralBaseline
from core.intelligence.code_index.models import CodeEntity
from core.intelligence.impact.engine import ImpactEngine
from core.intelligence.impact.enums import ImpactAssessmentStatus
from core.intelligence.impact.models import ImpactAssessment
from core.planning.implementation_specs.service import ImplementationSpecService
from core.planning.models import ImplementationSpec
from core.planning.schemas import AcCoverageEntry, TaskDraft, TaskPlan, TestRequirement
from core.planning.task_plans.service import TaskPlanService
from core.product_model.defects.completion import BugFixCompletionService
from core.product_model.defects.models import Defect, ExpectedBehaviorResolution
from core.product_model.defects.service import DefectService
from core.product_model.models import AcceptanceCriterion, FeatureSpec
from core.release.enums import ReleaseStatus
from core.traceability.models import RepositoryIndexPointer
from sqlalchemy import select
from tests.fixtures.approvals import approve_task_plan
from tests.fixtures.brownfield_phase12_harness import ensure_human_approver
from tests.fixtures.release_harness import integration_ic_after_start_integration
from tests.journey.bug_fix_dev import (
    complete_bug_fix_repair_tasks,
    complete_stale_code_change_tasks,
)
from tests.journey.bug_fix_helpers import (
    _drive_regression_stage,
    _ensure_stub_execution_for_control_plane_task,
    _latest_execution_id_for_profile,
    _maybe_start_assurance_after_regression,
    _prepare_regression_verifications,
    approve_repair_implementation_specs,
    finish_bug_fix_assurance_and_release_for_cycle,
    maybe_advance_to_expected_behavior,
    maybe_apply_triage_fallback,
    maybe_complete_expected_behavior_and_root_cause,
    maybe_complete_pre_repair_reproduction,
    run_cycle_command,
)
from tests.journey.seed import seed_trusted_project

pytestmark = [pytest.mark.integration, pytest.mark.asyncio]

FIXTURES = Path(__file__).resolve().parents[2] / "fixtures"
DEFECT_REPO = FIXTURES / "repos" / "supportdesk_defect_closed_update"
TRUSTED_SEED_DEFECT = FIXTURES / "supportdesk" / "trusted_seed_defect.yaml"
CHAR_KEY = "BL-TICKET-CLOSED-UPDATE-500"
REGRESSION_TEST = "tests/test_closed_ticket_update.py"
CHAR_TEST_SOURCE = """import app.models.ticket  # noqa: F401
from app.db import Base, engine
from app.main import app
from fastapi.testclient import TestClient


def test_closed_ticket_update_returns_500():
    Base.metadata.create_all(bind=engine)
    client = TestClient(app, raise_server_exceptions=False)
    tid = client.post("/tickets", json={"title": "x"}).json()["id"]
    client.patch(f"/tickets/{tid}", json={"status": "CLOSED"})
    resp = client.patch(f"/tickets/{tid}", json={"status": "OPEN"})
    assert resp.status_code == 500
"""


async def test_approved_expected_behavior_supersedes_characterization_baseline(
    db_session,
    system_ctx: CommandContext,
) -> None:
    trusted = await seed_trusted_project(db_session, DEFECT_REPO, TRUSTED_SEED_DEFECT, system_ctx)
    update_path_keys = [
        e.stable_key
        for e in (
            await db_session.execute(
                select(CodeEntity).where(CodeEntity.index_version_id == trusted.index_version_id)
            )
        ).scalars()
        if e.qualified_name.endswith(("update_status", "update_ticket"))
    ]
    assert update_path_keys
    bset = await db_session.get(BaselineSet, trusted.baseline_set_id)
    assert bset is not None and bset.delivery_cycle_id is not None
    char_path = authored_test_path(CHAR_KEY, "test_closed_ticket_update")
    char_test = await store_authored_test(
        db_session,
        project_id=trusted.project_id,
        delivery_cycle_id=bset.delivery_cycle_id,
        execution_id=None,
        test_path=char_path,
        test_code=CHAR_TEST_SOURCE,
    )
    char = BehavioralBaseline(
        project_id=trusted.project_id,
        lineage_key=CHAR_KEY,
        version=1,
        status=BaselineStatus.ACTIVE,
        source=BaselineSource.BROWNFIELD_CHARACTERIZATION,
        given="a ticket in CLOSED status",
        when="a client PATCHes the ticket to OPEN",
        then="HTTP 500",
        check_kind=BaselineCheckKind.AUTHORED_TEST,
        check_ref=char_path,
        check_artifact_id=char_test.id,
        feature_spec_id=trusted.feature_spec_id,
        ac_lineage_key=None,
        observed_behavior_ids=[],
        exercised_stable_keys=update_path_keys,
        established_sha=trusted.commit_sha,
        established_evidence_id=None,
        activation=BaselineActivation.HUMAN,
    )
    db_session.add(char)
    await db_session.flush()
    db_session.add(BaselineSetItem(baseline_set_id=trusted.baseline_set_id, baseline_id=char.id))
    await db_session.flush()

    defect = await DefectService().intake(
        db_session,
        project_id=trusted.project_id,
        title="CLOSED ticket update",
        description="PATCH on CLOSED ticket returns 500 not 409",
        source_type="test",
        external_ref="rl3-acceptance",
        inbound_event_id=None,
        ctx=system_ctx,
    )
    assert defect.delivery_cycle_id is not None
    cycle_id = defect.delivery_cycle_id

    # Triage suspects the characterization baseline and cites no existing AC.
    await maybe_apply_triage_fallback(db_session, cycle_id, system_ctx)
    triage = dict(defect.triage or {})
    triage["suspected_baseline_keys"] = [CHAR_KEY]
    triage["suspected_ac_lineage_keys"] = []
    defect.triage = triage
    await db_session.flush()
    cycle = await db_session.get(DeliveryCycle, cycle_id)
    assert cycle is not None
    if cycle.state == "TRIAGE":
        await run_cycle_command(db_session, cycle_id, "start_reproduction", "TRIAGE", system_ctx)
    await maybe_complete_pre_repair_reproduction(
        db_session,
        cycle_id,
        system_ctx,
        apply_reproduce_fallback=True,
        run_deterministic_if_missing=True,
    )
    await maybe_advance_to_expected_behavior(db_session, cycle_id, system_ctx)
    await db_session.refresh(cycle)
    assert cycle.state == "EXPECTED_BEHAVIOR"

    await _ensure_stub_execution_for_control_plane_task(
        db_session,
        cycle_id,
        task_title="Resolve expected behavior",
        agent_profile="kira.expected_behavior",
    )
    execution_id = await _latest_execution_id_for_profile(
        db_session, cycle_id, "kira.expected_behavior"
    )
    assert execution_id is not None
    execution = await db_session.get(Execution, execution_id)
    assert execution is not None
    await BugFixCompletionService().persist_from_execution(
        db_session,
        execution,
        "kira.expected_behavior",
        {
            "classification": "UNDERSPECIFIED",
            "cited_ac_lineage_keys": [],
            "proposed_ac": {
                "statement": "Updating a CLOSED ticket is rejected with 409 Conflict",
                "given": "a ticket in CLOSED status",
                "when": "a client PATCHes the ticket to OPEN",
                "then": "HTTP 409 Conflict and the ticket stays CLOSED",
            },
            "expected_behavior_statement": "PATCH on a CLOSED ticket must return 409",
            "questions": [],
        },
        system_ctx,
    )
    await db_session.refresh(cycle)
    assert cycle.state == "EXPECTED_BEHAVIOR", "UNDERSPECIFIED must wait for a human"
    resolution = (
        await db_session.execute(
            select(ExpectedBehaviorResolution).where(
                ExpectedBehaviorResolution.defect_id == defect.id
            )
        )
    ).scalar_one()
    assert resolution.contradicted_baseline_ids == [str(char.id)]
    assert resolution.approval_id is not None
    review = await DefectService().resolution_review_payload(db_session, resolution)
    assert [b["lineage_key"] for b in review["contradicted_baselines"]] == [CHAR_KEY]

    _human, human_ctx = await ensure_human_approver(db_session)
    await handle_approval_decide(
        db_session,
        human_ctx,
        {
            "approval_id": str(resolution.approval_id),
            "decision": ApprovalStatus.APPROVED.value,
            "note": "The 500 was a bug; closed tickets reject updates with 409",
        },
    )
    approval = await db_session.get(Approval, resolution.approval_id)
    assert approval is not None and approval.status == ApprovalStatus.APPROVED
    await db_session.refresh(cycle)
    assert cycle.state == "ROOT_CAUSE"
    await maybe_complete_expected_behavior_and_root_cause(db_session, cycle_id, system_ctx)
    # Root cause names the indexed faulty method, so impact reaches the update path.
    faulty_key = next(k for k in update_path_keys if k.startswith("METHOD:"))
    pointer = await db_session.get(RepositoryIndexPointer, trusted.repository_id)
    assert pointer is not None and pointer.canonical_index_version_id is not None
    for stale in (
        await db_session.execute(
            select(ImpactAssessment).where(ImpactAssessment.delivery_cycle_id == cycle_id)
        )
    ).scalars():
        stale.status = ImpactAssessmentStatus.SUPERSEDED.value
    await ImpactEngine().assess(
        db_session,
        cycle_id,
        seed_stable_keys=[faulty_key],
        index_version_id=pointer.canonical_index_version_id,
        ctx=system_ctx,
    )

    new_spec = (
        await db_session.execute(
            select(FeatureSpec).where(
                FeatureSpec.feature_id == trusted.feature_id,
                FeatureSpec.status == SpecStatus.APPROVED,
            )
        )
    ).scalar_one()
    await db_session.refresh(defect)
    new_ac = await db_session.get(AcceptanceCriterion, uuid.UUID(str(defect.expected_ac_ids[0])))
    assert new_ac is not None and new_ac.feature_spec_id == new_spec.id

    base_impl = await db_session.get(ImplementationSpec, trusted.implementation_spec_id)
    assert base_impl is not None
    base_body = ImplementationSpecService().parse_body(base_impl)
    body = base_body.model_copy(
        update={
            "required_tests": [
                *base_body.required_tests,
                TestRequirement(
                    kind="api",
                    ac_keys=[new_ac.lineage_key],
                    description=f"{REGRESSION_TEST} regression for 409",
                ),
            ],
            "ac_coverage": [
                *base_body.ac_coverage,
                AcCoverageEntry(ac_key=new_ac.lineage_key, locations=[REGRESSION_TEST]),
            ],
        }
    )
    await ImplementationSpecService().persist_repair_draft(
        db_session,
        feature_spec_id=new_spec.id,
        draft=ImplementationSpecDraft(body=body),
        execution_id=None,
        ctx=system_ctx,
    )
    await approve_repair_implementation_specs(db_session, cycle_id, human_ctx)
    repair_impl = (
        await db_session.execute(
            select(ImplementationSpec).where(
                ImplementationSpec.project_id == trusted.project_id,
                ImplementationSpec.kind == "REPAIR",
                ImplementationSpec.status == SpecStatus.APPROVED,
            )
        )
    ).scalar_one()
    plan = await TaskPlanService().persist_proposed(
        db_session,
        delivery_cycle_id=cycle_id,
        plan=TaskPlan(
            tasks=[
                TaskDraft(
                    ref="repair-1",
                    title="Apply ticket service repair",
                    objective="Fix CLOSED ticket update to return 409",
                    implementation_spec_ref=repair_impl.lineage_key,
                    ac_refs=["AC-TICKET-CREATE", new_ac.lineage_key],
                    allowed_scope=body.file_scope,
                    required_outputs=[
                        "candidate_commit",
                        "changed_files",
                        "test_results",
                        f"file:{REGRESSION_TEST}",
                    ],
                    verification_requirements=["pytest"],
                    estimated_size="S",
                )
            ]
        ),
        implementation_spec_ids=[repair_impl.id],
        execution_id=None,
        ctx=system_ctx,
    )
    await approve_task_plan(db_session, plan.id)
    await run_cycle_command(db_session, cycle_id, "start_development", "ROOT_CAUSE", system_ctx)
    await db_session.refresh(cycle)
    repo = await db_session.get(Repository, trusted.repository_id)
    assert cycle.base_sha and repo is not None
    await complete_bug_fix_repair_tasks(
        db_session, system_ctx, repository=repo, cycle=cycle, base_sha=cycle.base_sha
    )
    await complete_stale_code_change_tasks(db_session, cycle_id)
    ic = await integration_ic_after_start_integration(db_session, system_ctx, cycle_id)
    assert ic.status == ICStatus.READY
    await run_cycle_command(db_session, cycle_id, "start_regression", "INTEGRATION", system_ctx)
    await _prepare_regression_verifications(db_session, cycle_id, system_ctx)
    await _drive_regression_stage(db_session, cycle_id, system_ctx)
    await _maybe_start_assurance_after_regression(db_session, cycle_id, system_ctx)
    await db_session.refresh(cycle)
    assert cycle.state == "ASSURANCE"

    ic, release = await finish_bug_fix_assurance_and_release_for_cycle(
        db_session, system_ctx, human_ctx, cycle_id
    )
    assert release.status == ReleaseStatus.RELEASED  # type: ignore[attr-defined]

    baseline_gate = (
        await db_session.execute(
            select(Gate).where(
                Gate.integration_candidate_id == ic.id,
                Gate.gate_type == GateType.BASELINE,
            )
        )
    ).scalar_one()
    assert baseline_gate.status == GateStatus.PASS
    char_obligation = (
        await db_session.execute(
            select(VerificationObligation).where(
                VerificationObligation.integration_candidate_id == ic.id,
                VerificationObligation.subject_id == char.id,
            )
        )
    ).scalar_one()
    assert char_obligation.required is False
    assert char_obligation.source_refs[0]["superseded_by_approved_expected_behavior"] == (
        approval.key
    )
    char_results = {
        ev.result
        for ev in (
            await db_session.execute(
                select(Evidence).where(
                    Evidence.integration_candidate_id == ic.id,
                    Evidence.obligation_id == char_obligation.id,
                )
            )
        ).scalars()
    }
    assert char_results == {EvidenceResult.FAIL}, "the pinned 500 must fail after the repair"

    await db_session.refresh(char)
    assert char.status == BaselineStatus.SUPERSEDED
    repair_baseline = (
        await db_session.execute(
            select(BehavioralBaseline).where(
                BehavioralBaseline.project_id == trusted.project_id,
                BehavioralBaseline.source == BaselineSource.REPAIR,
            )
        )
    ).scalar_one()
    assert repair_baseline.status == BaselineStatus.ACTIVE
    assert repair_baseline.ac_lineage_key == new_ac.lineage_key
    assert repair_baseline.then == new_ac.then
    assert REGRESSION_TEST in (repair_baseline.check_ref or "")
    refreshed = await db_session.get(Defect, defect.id)
    assert refreshed is not None and refreshed.status == "RELEASED"
