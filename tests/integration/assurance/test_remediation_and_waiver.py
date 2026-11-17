"""Remediation task creation and finding waiver (Phase 09 §14)."""

from __future__ import annotations

import pytest
from core.assurance.findings import FindingService
from core.assurance.remediation import RemediationService
from core.commands.context import CommandContext
from core.domain.actors.models import Actor
from core.domain.delivery_cycles.service import DeliveryCycleService
from core.domain.enums import (
    ActorKind,
    ActorRole,
    ApprovalStatus,
    DeliveryCycleType,
    TaskOrigin,
    WorkType,
)
from core.domain.tasks.models import Task
from core.integration.enums import FindingSeverity, FindingSource, FindingStatus

pytestmark = pytest.mark.integration


@pytest.mark.asyncio
async def test_remediation_creates_task_and_marks_in_remediation(
    db_session,
    sample_project,
    operator_ctx,
) -> None:
    cycle = await DeliveryCycleService().create(
        db_session,
        sample_project.id,
        DeliveryCycleType.GREENFIELD_BUILD,
        "remediation",
        operator_ctx,
    )
    finding = await FindingService().create(
        db_session,
        project_id=sample_project.id,
        delivery_cycle_id=cycle.id,
        source=FindingSource.SENTINEL,
        category="CORRECTNESS",
        severity=FindingSeverity.BLOCKER,
        title="Test failure",
        detail={"detail": "assert failed"},
        ctx=operator_ctx,
        code_refs=[{"file_path": "src/a.py"}],
    )
    task_id = await RemediationService().remediate_finding(db_session, finding.id, operator_ctx)
    await db_session.refresh(finding)
    assert finding.status == FindingStatus.IN_REMEDIATION
    assert finding.remediation_task_id == task_id
    task = await db_session.get(Task, task_id)
    assert task is not None
    assert task.origin == TaskOrigin.REMEDIATION
    assert task.work_type == WorkType.CODE_CHANGE


@pytest.mark.asyncio
async def test_finding_waiver_on_approval(
    db_session,
    sample_project,
    operator_ctx,
) -> None:
    approver = Actor(
        kind=ActorKind.HUMAN,
        name="approver",
        roles=[ActorRole.APPROVER.value],
    )
    db_session.add(approver)
    await db_session.flush()
    approver_ctx = CommandContext(actor=approver, correlation_id="approver")
    cycle = await DeliveryCycleService().create(
        db_session,
        sample_project.id,
        DeliveryCycleType.GREENFIELD_BUILD,
        "waiver",
        operator_ctx,
    )
    finding = await FindingService().create(
        db_session,
        project_id=sample_project.id,
        delivery_cycle_id=cycle.id,
        source=FindingSource.WARDEN,
        category="SECURITY",
        severity=FindingSeverity.MAJOR,
        title="Concern",
        detail={},
        ctx=operator_ctx,
    )
    assert finding.blocking is True
    approval_id = await FindingService().request_waiver(
        db_session, finding.id, sample_project.id, operator_ctx
    )
    from core.commands.handlers import handle_approval_decide

    await handle_approval_decide(
        db_session,
        approver_ctx,
        {
            "approval_id": str(approval_id),
            "decision": ApprovalStatus.APPROVED.value,
            "note": "accepted risk",
        },
    )
    await db_session.refresh(finding)
    assert finding.status == FindingStatus.WAIVED
    assert finding.blocking is False
    assert finding.waiver_approval_id == approval_id


@pytest.mark.asyncio
async def test_fix_task_gets_explanation_spec_scope_and_builds_on_previous_fix(
    db_session,
    sample_project,
    operator_ctx,
) -> None:
    from core.domain.enums import SpecStatus
    from core.domain.task_contracts.models import TaskContract
    from core.domain.tasks.models import TaskDependency
    from core.planning.models import ImplementationSpec
    from sqlalchemy import select

    cycle = await DeliveryCycleService().create(
        db_session,
        sample_project.id,
        DeliveryCycleType.GREENFIELD_BUILD,
        "fix scope",
        operator_ctx,
    )
    spec = (
        await db_session.execute(
            select(ImplementationSpec).where(ImplementationSpec.project_id == sample_project.id)
        )
    ).scalar_one_or_none()
    spec_refs: list[str] = []
    if spec is not None:
        spec.status = SpecStatus.APPROVED
        spec.body = {**(spec.body or {}), "file_scope": ["app/models/**", "app/services/**"]}
        spec_refs = [spec.lineage_key]
    await db_session.flush()

    async def finding(title: str):  # type: ignore[no-untyped-def]
        return await FindingService().create(
            db_session,
            project_id=sample_project.id,
            delivery_cycle_id=cycle.id,
            source=FindingSource.WARDEN,
            category="CORRECTNESS",
            severity=FindingSeverity.MAJOR,
            title=title,
            detail={"detail": "reset tokens are never persisted", "spec_refs": spec_refs},
            ctx=operator_ctx,
            code_refs=[{"file_path": "app/services/auth_service.py", "line_start": 38}],
            spec_refs=spec_refs,
        )

    first = await finding("Password reset cannot succeed")
    first_task = await RemediationService().remediate_finding(db_session, first.id, operator_ctx)
    task = await db_session.get(Task, first_task)
    assert task is not None
    contract = await db_session.get(TaskContract, task.current_contract_id)
    assert contract is not None
    assert "reset tokens are never persisted" in contract.body["objective"]
    assert "app/services/auth_service.py" in contract.body["allowed_scope"]
    assert "tests/**" in contract.body["allowed_scope"]
    if spec_refs:
        assert "app/models/**" in contract.body["allowed_scope"]

    second = await finding("Another fix")
    second_task = await RemediationService().remediate_finding(db_session, second.id, operator_ctx)
    deps = (
        await db_session.execute(
            select(TaskDependency.depends_on_task_id).where(TaskDependency.task_id == second_task)
        )
    ).scalars()
    assert list(deps) == [first_task]
    task2 = await db_session.get(Task, second_task)
    assert task2 is not None
    contract2 = await db_session.get(TaskContract, task2.current_contract_id)
    assert contract2 is not None
    assert contract2.body["base_policy"] == "DEPENDENCY_INTEGRATION"

    # Requested in the same transaction (one shared timestamp), the third still chains on the
    # second, not the first.
    third = await finding("Third fix")
    third_task = await RemediationService().remediate_finding(db_session, third.id, operator_ctx)
    deps3 = (
        await db_session.execute(
            select(TaskDependency.depends_on_task_id).where(TaskDependency.task_id == third_task)
        )
    ).scalars()
    assert list(deps3) == [second_task]
