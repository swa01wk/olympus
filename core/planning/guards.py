from __future__ import annotations

from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.domain.delivery_cycles.models import DeliveryCycle
from core.domain.enums import SpecStatus, TaskContractStatus, TaskOrigin, WorkType
from core.domain.task_contracts.models import TaskContract
from core.domain.tasks.models import Task
from core.planning.models import Architecture, ImplementationSpec, TaskPlanRow
from core.product_model.models import AcceptanceCriterion, FeatureSpec, ScopeSet, ScopeSetItem
from core.state.guards import GuardResult


async def architecture_approved(
    session: AsyncSession,
    cycle: DeliveryCycle,
    _ctx: Any,
) -> GuardResult:
    row = await session.execute(
        select(Architecture.id)
        .where(
            Architecture.project_id == cycle.project_id,
            Architecture.status == SpecStatus.APPROVED,
        )
        .limit(1)
    )
    if row.scalar_one_or_none() is None:
        return GuardResult(ok=False, reasons=("ARCHITECTURE_NOT_APPROVED",))
    return GuardResult(ok=True)


async def implementation_specs_approved(
    session: AsyncSession,
    cycle: DeliveryCycle,
    _ctx: Any,
) -> GuardResult:
    scope = await session.execute(
        select(ScopeSet)
        .where(ScopeSet.delivery_cycle_id == cycle.id)
        .order_by(ScopeSet.created_at.desc())
        .limit(1)
    )
    scope_set = scope.scalar_one_or_none()
    if scope_set is None:
        return GuardResult(ok=False, reasons=("SCOPE_NOT_APPROVED",))
    items = await session.execute(
        select(ScopeSetItem).where(ScopeSetItem.scope_set_id == scope_set.id)
    )
    for item in items.scalars():
        spec = await session.get(FeatureSpec, item.feature_spec_id)
        if spec is None:
            return GuardResult(ok=False, reasons=("SCOPE_SPEC_MISSING",))
        impl = await session.execute(
            select(ImplementationSpec.id)
            .where(
                ImplementationSpec.feature_spec_id == spec.id,
                ImplementationSpec.status == SpecStatus.APPROVED,
            )
            .limit(1)
        )
        if impl.scalar_one_or_none() is None:
            reason = f"IMPLEMENTATION_SPEC_MISSING:{spec.lineage_key}"
            return GuardResult(ok=False, reasons=(reason,))
    return GuardResult(ok=True)


async def task_plan_accepted_contracts_issued(
    session: AsyncSession,
    cycle: DeliveryCycle,
    _ctx: Any,
) -> GuardResult:
    plan = await session.execute(
        select(TaskPlanRow)
        .where(TaskPlanRow.delivery_cycle_id == cycle.id, TaskPlanRow.status == "ACCEPTED")
        .order_by(TaskPlanRow.created_at.desc())
        .limit(1)
    )
    plan_row = plan.scalar_one_or_none()
    if plan_row is None:
        return GuardResult(ok=False, reasons=("TASK_PLAN_NOT_ACCEPTED",))

    from core.domain.approvals.service import ApprovalService
    from core.domain.canonical_json import sha256_hex
    from core.domain.enums import ApprovalType

    subject_hash = sha256_hex(plan_row.body or {})
    if not await ApprovalService().is_satisfied(
        session,
        ApprovalType.TASK_PLAN,
        "task_plan",
        plan_row.id,
        subject_hash,
    ):
        return GuardResult(ok=False, reasons=("TASK_PLAN_APPROVAL_PENDING",))

    tasks = await session.execute(
        select(Task).where(
            Task.delivery_cycle_id == cycle.id,
            Task.origin == TaskOrigin.IMPLEMENTATION_PLAN,
            Task.work_type == WorkType.CODE_CHANGE,
        )
    )
    task_rows = list(tasks.scalars())
    if not task_rows:
        return GuardResult(ok=False, reasons=("NO_PLAN_TASKS",))

    for task in task_rows:
        if task.current_contract_id is None:
            return GuardResult(ok=False, reasons=(f"CONTRACT_MISSING:{task.key}",))
        contract = await session.get(TaskContract, task.current_contract_id)
        if contract is None or contract.status != TaskContractStatus.ISSUED:
            return GuardResult(ok=False, reasons=(f"CONTRACT_NOT_ISSUED:{task.key}",))
        if not (contract.compiled_by or "").startswith("compiler:"):
            return GuardResult(ok=False, reasons=(f"CONTRACT_NOT_COMPILED:{task.key}",))

    scope = await session.execute(
        select(ScopeSet)
        .where(ScopeSet.delivery_cycle_id == cycle.id)
        .order_by(ScopeSet.created_at.desc())
        .limit(1)
    )
    scope_set = scope.scalar_one_or_none()
    if scope_set:
        mandatory: set[str] = set()
        items = await session.execute(
            select(ScopeSetItem).where(ScopeSetItem.scope_set_id == scope_set.id)
        )
        for item in items.scalars():
            acs = await session.execute(
                select(AcceptanceCriterion).where(
                    AcceptanceCriterion.feature_spec_id == item.feature_spec_id,
                    AcceptanceCriterion.mandatory.is_(True),
                )
            )
            mandatory.update(a.lineage_key for a in acs.scalars())
        covered: set[str] = set()
        for task in task_rows:
            from core.planning.models import TaskSpecRef

            refs = await session.execute(
                select(TaskSpecRef).where(
                    TaskSpecRef.task_id == task.id,
                    TaskSpecRef.ref_type == "ACCEPTANCE_CRITERION",
                )
            )
            for ref in refs.scalars():
                ac = await session.get(AcceptanceCriterion, ref.ref_id)
                if ac:
                    covered.add(ac.lineage_key)
        missing = mandatory - covered
        if missing:
            return GuardResult(ok=False, reasons=(f"AC_COVERAGE_INCOMPLETE:{sorted(missing)}",))

    return GuardResult(ok=True)
