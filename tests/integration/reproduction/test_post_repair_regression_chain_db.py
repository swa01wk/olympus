"""DB integration: repair commit → IC → POST_REPAIR + regression chain (no LLM)."""

from __future__ import annotations

from pathlib import Path

import pytest
from agents.kira.schemas import ImplementationSpecDraft
from core.assurance.enums import EvidenceResult, EvidenceType, GateStatus, GateType
from core.assurance.models import Evidence, Gate
from core.commands.context import CommandContext
from core.domain.delivery_cycles.models import DeliveryCycle
from core.domain.enums import SpecStatus
from core.domain.repositories.models import Repository
from core.integration.enums import ICStatus
from core.planning.implementation_specs.service import ImplementationSpecService
from core.planning.models import ImplementationSpec
from core.planning.schemas import AcCoverageEntry, TaskDraft, TaskPlan, TestRequirement
from core.planning.task_plans.service import TaskPlanService
from core.product_model.defects.service import DefectService
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
    _prepare_regression_verifications,
    approve_repair_implementation_specs,
    bootstrap_bug_fix_to_root_cause,
    run_cycle_command,
)
from tests.journey.seed import seed_trusted_project

DEFECT_REPO = (
    Path(__file__).resolve().parents[2] / "fixtures" / "repos" / "supportdesk_defect_closed_update"
)
TRUSTED_SEED_DEFECT = (
    Path(__file__).resolve().parents[2] / "fixtures" / "supportdesk" / "trusted_seed_defect.yaml"
)


@pytest.mark.integration
@pytest.mark.asyncio
async def test_post_repair_regression_chain_after_deterministic_repair(
    db_session,
    system_ctx: CommandContext,
) -> None:
    trusted = await seed_trusted_project(db_session, DEFECT_REPO, TRUSTED_SEED_DEFECT, system_ctx)
    defect = await DefectService().intake(
        db_session,
        project_id=trusted.project_id,
        title="CLOSED ticket 500",
        description="PATCH on CLOSED ticket returns 500 not 409",
        source_type="test",
        external_ref="post-repair-chain-1",
        inbound_event_id=None,
        ctx=system_ctx,
    )
    assert defect.delivery_cycle_id is not None
    cycle_id = defect.delivery_cycle_id
    await bootstrap_bug_fix_to_root_cause(db_session, cycle_id, system_ctx)
    cycle = await db_session.get(DeliveryCycle, cycle_id)
    assert cycle is not None

    base_impl = await db_session.get(ImplementationSpec, trusted.implementation_spec_id)
    assert base_impl is not None
    base_body = ImplementationSpecService().parse_body(base_impl)
    body = base_body.model_copy(
        update={
            "required_tests": [
                *base_body.required_tests,
                TestRequirement(
                    kind="api",
                    ac_keys=["AC-TICKET-CLOSED-UPDATE-409"],
                    description="tests/test_closed_ticket_update.py regression for 409",
                ),
            ],
            "ac_coverage": [
                *base_body.ac_coverage,
                AcCoverageEntry(
                    ac_key="AC-TICKET-CLOSED-UPDATE-409",
                    locations=["tests/test_closed_ticket_update.py"],
                ),
            ],
        }
    )
    draft = ImplementationSpecDraft(body=body)
    await ImplementationSpecService().persist_repair_draft(
        db_session,
        feature_spec_id=trusted.feature_spec_id,
        draft=draft,
        execution_id=None,
        ctx=system_ctx,
    )
    _human, human_ctx = await ensure_human_approver(db_session)
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
    plan_row = await TaskPlanService().persist_proposed(
        db_session,
        delivery_cycle_id=cycle_id,
        plan=TaskPlan(
            tasks=[
                TaskDraft(
                    ref="repair-1",
                    title="Apply ticket service repair",
                    objective="Fix CLOSED ticket update to return 409",
                    implementation_spec_ref=repair_impl.lineage_key,
                    ac_refs=["AC-TICKET-CREATE", "AC-TICKET-CLOSED-UPDATE-409"],
                    allowed_scope=body.file_scope,
                    required_outputs=[
                        "candidate_commit",
                        "changed_files",
                        "test_results",
                        "file:tests/test_closed_ticket_update.py",
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
    plan = plan_row
    await approve_task_plan(db_session, plan.id)
    await run_cycle_command(db_session, cycle_id, "start_development", "ROOT_CAUSE", system_ctx)
    await db_session.refresh(cycle)
    repo = await db_session.get(Repository, trusted.repository_id)
    assert cycle.base_sha and repo is not None
    await complete_bug_fix_repair_tasks(
        db_session,
        system_ctx,
        repository=repo,
        cycle=cycle,
        base_sha=cycle.base_sha,
    )
    await complete_stale_code_change_tasks(db_session, cycle_id)
    ic = await integration_ic_after_start_integration(db_session, system_ctx, cycle_id)
    assert ic.status == ICStatus.READY and ic.integrated_sha
    await run_cycle_command(db_session, cycle_id, "start_regression", "INTEGRATION", system_ctx)
    await _prepare_regression_verifications(db_session, cycle_id, system_ctx)
    await _drive_regression_stage(db_session, cycle_id, system_ctx)

    post_ev = (
        await db_session.execute(
            select(Evidence).where(
                Evidence.integration_candidate_id == ic.id,
                Evidence.evidence_type == EvidenceType.REPRODUCTION,
                Evidence.result == EvidenceResult.PASS,
            )
        )
    ).scalar_one_or_none()
    assert post_ev is not None, "expected POST_REPAIR PASS reproduction evidence"
    reg_ev = (
        await db_session.execute(
            select(Evidence)
            .where(
                Evidence.integration_candidate_id == ic.id,
                Evidence.evidence_type == EvidenceType.REGRESSION_TEST,
                Evidence.result == EvidenceResult.PASS,
            )
            .order_by(Evidence.created_at.desc())
            .limit(1)
        )
    ).scalar_one_or_none()
    assert reg_ev is not None, "expected regression test evidence"
    gate = (
        await db_session.execute(
            select(Gate).where(
                Gate.integration_candidate_id == ic.id,
                Gate.gate_type == GateType.REPRODUCTION,
            )
        )
    ).scalar_one_or_none()
    assert gate is not None and gate.status == GateStatus.PASS, gate
