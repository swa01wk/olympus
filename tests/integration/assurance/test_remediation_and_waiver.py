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
