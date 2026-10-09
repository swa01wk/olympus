"""RL2.5 — persist architecture delta and resolve impact guard."""

from __future__ import annotations

import json

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
from core.planning.architecture.service import ArchitectureService
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

    assert await ArchitectureService().get_approved(db_session, fx.project_id) is None


def _base_body() -> dict[str, object]:
    return {
        "summary": "SupportDesk layered service",
        "technology_stack": {
            "language": "python",
            "web": "fastapi",
            "orm": "sqlalchemy",
            "tests": "pytest",
        },
        "components": [
            {
                "name": "API layer",
                "layer": "api",
                "responsibility": "HTTP routes",
                "directory": "app/api",
            }
        ],
        "layers": ["api"],
        "dependency_rules": [],
        "directory_conventions": [],
        "decisions": [],
        "constraints": [],
        "risks": [],
    }


@pytest.mark.asyncio
async def test_planning_context_uses_base_architecture_with_approved_deltas(
    db_session, system_ctx
) -> None:
    from core.execution.snapshots.planning_context import planning_prompt_fields_for_task

    fx = await seed_supportdesk_ticket_priority_impact(db_session, system_ctx)
    delta_body = _sample_delta_proposal().model_dump(mode="json")
    for version, kind, body in ((1, "BASELINE", _base_body()), (2, "DELTA", delta_body)):
        db_session.add(
            Architecture(
                project_id=fx.project_id,
                version=version,
                status=SpecStatus.APPROVED,
                kind=kind,
                body=body,
                content_hash=f"arch-{version}",
            )
        )
    await db_session.flush()

    effective = await ArchitectureService().effective(db_session, fx.project_id)
    assert effective is not None
    base, body, _contracts = effective
    assert base.version == 1
    assert [c.name for c in body.components] == ["API layer", "priority_rules"]
    assert [d.id for d in body.decisions] == ["D-PRI"]

    task = await TaskService().create_task(
        db_session,
        fx.cycle_id,
        "Draft implementation spec delta",
        WorkType.ANALYSIS,
        TaskOrigin.CONTROL_PLANE,
        system_ctx,
    )
    task.governing_ref_id = fx.spec_v2_id
    await db_session.flush()
    fields = await planning_prompt_fields_for_task(
        db_session, task, agent_profile="kira.implementation_spec"
    )
    summary = json.loads(str(fields["architecture_summary"]))
    assert summary["valid_component_names"] == ["API layer", "priority_rules"]

    atlas = await planning_prompt_fields_for_task(
        db_session, task, agent_profile="atlas.architecture_delta"
    )
    assert [c["name"] for c in json.loads(str(atlas["architecture_summary"]))["components"]] == [
        "API layer",
        "priority_rules",
    ]
    impact = json.loads(str(atlas["impact_summary"]))
    assert "change_request" in impact and "impact_items" in impact
