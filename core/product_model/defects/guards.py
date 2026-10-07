from __future__ import annotations

from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.assurance.enums import EvidenceResult, EvidenceType, GateStatus, GateType
from core.assurance.models import Evidence, Gate
from core.domain.approvals.models import Approval
from core.domain.delivery_cycles.models import DeliveryCycle
from core.domain.enums import (
    ApprovalStatus,
    ApprovalType,
    DeliveryCycleType,
    SpecStatus,
    TaskContractStatus,
    TaskOrigin,
    WorkType,
)
from core.domain.task_contracts.models import TaskContract
from core.domain.tasks.models import Task
from core.integration.enums import ICStatus
from core.integration.models import IntegrationCandidate
from core.planning.models import ImplementationSpec, TaskPlanRow
from core.product_model.defects.models import Defect, ExpectedBehaviorResolution
from core.state.guards import GuardResult


async def defect_triaged(session: AsyncSession, cycle: DeliveryCycle, _ctx: Any) -> GuardResult:
    if cycle.type != DeliveryCycleType.BUG_FIX:
        return GuardResult(ok=False, reasons=("NOT_BUG_FIX_CYCLE",))
    defect = (
        await session.execute(select(Defect).where(Defect.delivery_cycle_id == cycle.id))
    ).scalar_one_or_none()
    if defect is None:
        return GuardResult(ok=False, reasons=("DEFECT_NOT_LINKED",))
    if defect.status != "TRIAGED":
        return GuardResult(ok=False, reasons=(f"DEFECT_NOT_TRIAGED:{defect.status}",))
    if not defect.severity:
        return GuardResult(ok=False, reasons=("SEVERITY_MISSING",))
    if not defect.triage:
        return GuardResult(ok=False, reasons=("TRIAGE_MISSING",))
    if not defect.linked_feature_ids and not defect.unlinked_acknowledged:
        return GuardResult(ok=False, reasons=("FEATURE_LINK_OR_UNLINKED_ACK_REQUIRED",))
    return GuardResult(ok=True)


async def reproduction_recorded(
    session: AsyncSession, cycle: DeliveryCycle, _ctx: Any
) -> GuardResult:
    defect = (
        await session.execute(select(Defect).where(Defect.delivery_cycle_id == cycle.id))
    ).scalar_one_or_none()
    if defect is None:
        return GuardResult(ok=False, reasons=("DEFECT_NOT_LINKED",))
    unrepro = (
        await session.execute(
            select(Approval).where(
                Approval.delivery_cycle_id == cycle.id,
                Approval.approval_type == ApprovalType.UNREPRODUCED_REPAIR,
                Approval.status == ApprovalStatus.APPROVED,
            )
        )
    ).scalar_one_or_none()
    if unrepro is not None:
        return GuardResult(ok=True)
    ev = (
        await session.execute(
            select(Evidence)
            .where(
                Evidence.delivery_cycle_id == cycle.id,
                Evidence.subject_type == "DEFECT",
                Evidence.subject_id == defect.id,
                Evidence.evidence_type == EvidenceType.REPRODUCTION,
                Evidence.result == EvidenceResult.FAIL,
            )
            .order_by(Evidence.created_at.desc())
            .limit(1)
        )
    ).scalar_one_or_none()
    if ev is None:
        return GuardResult(ok=False, reasons=("PRE_REPAIR_REPRODUCTION_MISSING",))
    if not ev.details.get("reproduced"):
        return GuardResult(ok=False, reasons=("NOT_REPRODUCED",))
    if ev.details.get("phase") != "PRE_REPAIR":
        return GuardResult(ok=False, reasons=("WRONG_REPRODUCTION_PHASE",))
    return GuardResult(ok=True)


async def expected_behavior_resolved(
    session: AsyncSession, cycle: DeliveryCycle, _ctx: Any
) -> GuardResult:
    defect = (
        await session.execute(select(Defect).where(Defect.delivery_cycle_id == cycle.id))
    ).scalar_one_or_none()
    if defect is None:
        return GuardResult(ok=False, reasons=("DEFECT_NOT_LINKED",))
    row = (
        await session.execute(
            select(ExpectedBehaviorResolution)
            .where(ExpectedBehaviorResolution.defect_id == defect.id)
            .order_by(ExpectedBehaviorResolution.created_at.desc())
            .limit(1)
        )
    ).scalar_one_or_none()
    if row is None:
        return GuardResult(ok=False, reasons=("EXPECTED_BEHAVIOR_NOT_RESOLVED",))
    if row.classification == "NOT_A_DEFECT":
        return GuardResult(ok=False, reasons=("DEFECT_REJECTED",))
    return GuardResult(ok=True)


async def repair_spec_approved_contracts_issued(
    session: AsyncSession, cycle: DeliveryCycle, _ctx: Any
) -> GuardResult:
    impl = (
        await session.execute(
            select(ImplementationSpec.id)
            .where(
                ImplementationSpec.project_id == cycle.project_id,
                ImplementationSpec.kind == "REPAIR",
                ImplementationSpec.status == SpecStatus.APPROVED,
            )
            .order_by(ImplementationSpec.created_at.desc())
            .limit(1)
        )
    ).scalar_one_or_none()
    if impl is None:
        return GuardResult(ok=False, reasons=("REPAIR_SPEC_NOT_APPROVED",))
    plan = (
        await session.execute(
            select(TaskPlanRow)
            .where(TaskPlanRow.delivery_cycle_id == cycle.id, TaskPlanRow.status == "ACCEPTED")
            .limit(1)
        )
    ).scalar_one_or_none()
    if plan is None:
        return GuardResult(ok=False, reasons=("TASK_PLAN_NOT_ACCEPTED",))
    tasks = (
        await session.execute(
            select(Task).where(
                Task.delivery_cycle_id == cycle.id,
                Task.origin == TaskOrigin.REPAIR,
                Task.work_type == WorkType.CODE_CHANGE,
            )
        )
    ).scalars()
    for task in tasks:
        if task.current_contract_id is None:
            return GuardResult(ok=False, reasons=(f"CONTRACT_MISSING:{task.key}",))
        contract = await session.get(TaskContract, task.current_contract_id)
        if contract is None or contract.status != TaskContractStatus.ISSUED:
            return GuardResult(ok=False, reasons=(f"CONTRACT_NOT_ISSUED:{task.key}",))
    return GuardResult(ok=True)


async def reproduction_and_regression_pass(
    session: AsyncSession, cycle: DeliveryCycle, _ctx: Any
) -> GuardResult:
    ic = (
        await session.execute(
            select(IntegrationCandidate)
            .where(
                IntegrationCandidate.delivery_cycle_id == cycle.id,
                IntegrationCandidate.status == ICStatus.READY,
            )
            .order_by(IntegrationCandidate.created_at.desc())
            .limit(1)
        )
    ).scalar_one_or_none()
    if ic is None:
        return GuardResult(ok=False, reasons=("IC_NOT_READY",))
    for gt in (GateType.REPRODUCTION, GateType.REGRESSION):
        gate = (
            await session.execute(
                select(Gate)
                .where(
                    Gate.integration_candidate_id == ic.id,
                    Gate.gate_type == gt,
                    Gate.status != GateStatus.SUPERSEDED,
                )
                .order_by(Gate.created_at.desc())
                .limit(1)
            )
        ).scalar_one_or_none()
        if gate is None or gate.status != GateStatus.PASS:
            return GuardResult(ok=False, reasons=(f"GATE_NOT_PASS:{gt.value}",))
    return GuardResult(ok=True)
