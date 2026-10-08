"""Idempotent pending approval creation for proposed planning artifacts."""

from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.commands.context import CommandContext
from core.domain.approvals.models import Approval
from core.domain.approvals.service import ApprovalService
from core.domain.enums import ApprovalStatus, ApprovalType
from core.policy.policy_service import ensure_policy_version


async def ensure_pending_approval(
    session: AsyncSession,
    *,
    project_id: uuid.UUID,
    approval_type: ApprovalType,
    subject_type: str,
    subject_id: uuid.UUID,
    subject_version: int,
    subject_hash: str,
    delivery_cycle_id: uuid.UUID,
    ctx: CommandContext,
) -> Approval:
    existing = (
        await session.execute(
            select(Approval).where(
                Approval.approval_type == approval_type,
                Approval.subject_type == subject_type,
                Approval.subject_id == subject_id,
                Approval.subject_hash == subject_hash,
                Approval.status == ApprovalStatus.PENDING,
                Approval.delivery_cycle_id == delivery_cycle_id,
            )
        )
    ).scalar_one_or_none()
    if existing is not None:
        return existing
    policy = await ensure_policy_version(session)
    return await ApprovalService(policy=policy).request(
        session,
        project_id,
        delivery_cycle_id,
        approval_type,
        subject_type,
        subject_id,
        subject_version,
        subject_hash,
        ctx,
        policy=policy,
    )
