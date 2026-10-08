"""RL2.5 — persist architecture delta and resolve impact guard."""

from __future__ import annotations

import pytest
from agents.atlas.schemas import ArchitectureDeltaProposal
from core.commands.handlers import handle_approval_decide
from core.domain.approvals.models import Approval
from core.domain.delivery_cycles.models import DeliveryCycle
from core.domain.enums import (
    ApprovalStatus,
    ApprovalType,
    ExecutionStatus,
    SpecStatus,
    TaskOrigin,
    WorkType,
)
from core.domain.executions.models import Execution
from core.domain.tasks.service import TaskService
from core.intelligence.impact.enums import ImpactAssessmentStatus
from core.intelligence.impact.guards import architecture_delta_resolved
from core.intelligence.impact.models import ImpactAssessment
from core.planning.models import Architecture
from core.planning.schemas import ComponentDef, DecisionDef
from core.product_model.changes.completion import FeatureChangeCompletionService
from sqlalchemy import func, select
from tests.fixtures.impact_harness import seed_supportdesk_ticket_priority_impact

pytestmark = pytest.mark.integration


def _sample_delta_proposal() -> ArchitectureDeltaProposal:
    return ArchitectureDeltaProposal(
        rationale="Validate ticket priority in the service layer.",
        added_components=[
            ComponentDef(
                name="priority_rules",
                layer="service",
                responsibility="Priority validation",
                directory="app/service/priority",
            )
        ],
        decisions=[
            DecisionDef(
                id="D-PRI",
                title="Priority guard",
                decision="Single PriorityGuard used by TicketService",
                rationale="Impact analysis",
            )
        ],
    )


@pytest.mark.asyncio
async def test_architecture_delta_persist_approve_resolves_guard(
    db_session, system_ctx, operator_ctx
) -> None:
    fx = await seed_supportdesk_ticket_priority_impact(db_session, system_ctx)
    db_session.add(
        ImpactAssessment(
            key="IA-DELTA",
            delivery_cycle_id=fx.cycle_id,
            index_version_id=fx.index_version.id,
            commit_sha=fx.commit_sha,
            seed_kind="MANUAL",
            seed_refs=[],
            status=ImpactAssessmentStatus.COMPLETE.value,
            architecture_delta_suggested=True,
            summary={},
            content_hash="delta-suggested",
        )
    )
    await db_session.flush()

    cycle = await db_session.get(DeliveryCycle, fx.cycle_id)
    assert cycle is not None
    assert not (await architecture_delta_resolved(db_session, cycle, None)).ok

    task = await TaskService().create_task(
        db_session,
        fx.cycle_id,
        "Propose architecture delta",
        WorkType.ANALYSIS,
        TaskOrigin.CONTROL_PLANE,
        system_ctx,
    )
    from core.domain.enums import TaskContractStatus
    from core.domain.task_contracts.models import TaskContract

    contract = TaskContract(
        task_id=task.id,
        key="v1",
        version=1,
        status=TaskContractStatus.ISSUED,
        body={"agent_profile": "atlas.architecture_delta"},
        content_hash="arch-delta-test",
        compiled_by="test",
    )
    db_session.add(contract)
    await db_session.flush()

    execution = Execution(
        key="arch-delta-ex",
        task_id=task.id,
        delivery_cycle_id=fx.cycle_id,
        task_contract_id=contract.id,
        attempt_number=1,
        status=ExecutionStatus.COMPLETED,
        executor_kind="AGENT_RUNTIME",
        agent_profile="atlas.architecture_delta",
    )
    db_session.add(execution)
    await db_session.flush()

    await FeatureChangeCompletionService().persist_from_execution(
        db_session,
        execution,
        "atlas.architecture_delta",
        _sample_delta_proposal().model_dump(mode="json"),
        system_ctx,
    )

    arch = (
        await db_session.execute(
            select(Architecture).where(
                Architecture.project_id == fx.project_id,
                Architecture.kind == "DELTA",
            )
        )
    ).scalar_one()
    assert arch.status == SpecStatus.PROPOSED

    pending = (
        await db_session.execute(
            select(func.count())
            .select_from(Approval)
            .where(
                Approval.approval_type == ApprovalType.ARCHITECTURE_DELTA,
                Approval.subject_type == "architecture",
                Approval.subject_id == arch.id,
                Approval.status == ApprovalStatus.PENDING,
            )
        )
    ).scalar_one()
    assert pending == 1

    approval_id = (
        await db_session.execute(
            select(Approval.id).where(
                Approval.approval_type == ApprovalType.ARCHITECTURE_DELTA,
                Approval.subject_id == arch.id,
            )
        )
    ).scalar_one()

    await handle_approval_decide(
        db_session,
        operator_ctx,
        {
            "approval_id": str(approval_id),
            "decision": ApprovalStatus.APPROVED.value,
            "note": "approve delta",
        },
    )

    refreshed = await db_session.get(Architecture, arch.id)
    assert refreshed is not None
    assert refreshed.status == SpecStatus.APPROVED
    assert (await architecture_delta_resolved(db_session, cycle, None)).ok
