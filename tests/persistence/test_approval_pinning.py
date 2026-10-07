from __future__ import annotations

import uuid

import pytest
from core.commands.context import CommandContext
from core.domain.approvals.service import ApprovalService
from core.domain.delivery_cycles.service import DeliveryCycleService
from core.domain.enums import ApprovalStatus, ApprovalType, DeliveryCycleType
from core.policy.policy_service import ensure_policy_version

pytestmark = pytest.mark.persistence


@pytest.mark.asyncio
async def test_is_satisfied_requires_matching_subject_hash(
    db_session, sample_project, operator_actor
) -> None:
    ctx = CommandContext(actor=operator_actor, correlation_id="ap")
    policy = await ensure_policy_version(db_session)
    cycle = await DeliveryCycleService().create(
        db_session,
        sample_project.id,
        DeliveryCycleType.GREENFIELD_BUILD,
        "obj",
        ctx,
    )
    subject_id = uuid.uuid4()
    approval = await ApprovalService(policy=policy).request(
        db_session,
        sample_project.id,
        cycle.id,
        ApprovalType.SCOPE,
        "task_contract",
        subject_id,
        1,
        "hash-a",
        ctx,
        policy=policy,
    )
    await ApprovalService(policy=policy).decide(
        db_session,
        approval.id,
        ApprovalStatus.APPROVED,
        None,
        ctx,
    )
    svc = ApprovalService()
    assert await svc.is_satisfied(
        db_session, ApprovalType.SCOPE, "task_contract", subject_id, "hash-a"
    )
    assert not await svc.is_satisfied(
        db_session, ApprovalType.SCOPE, "task_contract", subject_id, "hash-b"
    )
