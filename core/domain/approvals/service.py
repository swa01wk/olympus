"""Human approval requests and HUMAN+APPROVER decisions pinned to subject hash."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from core.commands.context import CommandContext
from core.domain.approvals.models import Approval
from core.domain.enums import ActorKind, ActorRole, ApprovalStatus, ApprovalType
from core.domain.events.append import append_domain_event
from core.domain.exceptions import DomainError, Unauthorized
from core.domain.sequences import next_project_key
from core.policy.policy_service import PolicyService
from core.state.transition_service import TransitionService
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker


class ApprovalService:
    def __init__(
        self,
        transitions: TransitionService | None = None,
        policy: PolicyService | None = None,
    ) -> None:
        self.transitions = transitions or TransitionService()
        self.policy = policy

    async def request(
        self,
        session: AsyncSession,
        project_id: uuid.UUID,
        delivery_cycle_id: uuid.UUID | None,
        approval_type: ApprovalType,
        subject_type: str,
        subject_id: uuid.UUID,
        subject_version: int,
        subject_hash: str,
        ctx: CommandContext,
        policy: PolicyService | None = None,
    ) -> Approval:
        pol = policy or self.policy
        policy_version_id = pol.version_row.id if pol and pol.version_row else None
        key = await next_project_key(session, project_id, "approval", prefix="APR")
        approval = Approval(
            key=key,
            project_id=project_id,
            delivery_cycle_id=delivery_cycle_id,
            approval_type=approval_type,
            subject_type=subject_type,
            subject_id=subject_id,
            subject_version=subject_version,
            subject_hash=subject_hash,
            status=ApprovalStatus.PENDING,
            requested_by_actor_id=ctx.actor.id,
            policy_version_id=policy_version_id,
        )
        session.add(approval)
        await session.flush()
        await append_domain_event(
            session,
            aggregate_type="approval",
            aggregate_id=approval.id,
            event_type="approval.requested",
            payload={"approval_type": approval_type.value, "subject_type": subject_type},
            actor_id=ctx.actor.id,
            correlation_id=ctx.correlation_id,
            project_id=project_id,
            delivery_cycle_id=delivery_cycle_id,
        )
        return approval

    async def record_decision_denied(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        approval_id: uuid.UUID,
        ctx: CommandContext,
    ) -> None:
        from core.domain.audit.append import append_audit

        async with session_factory() as session, session.begin():
            await append_audit(
                session,
                actor_id=ctx.actor.id,
                actor_kind=ctx.actor.kind,
                action="approval.decision_denied",
                target_type="approval",
                target_id=str(approval_id),
                correlation_id=ctx.correlation_id,
                after={"reason": "APPROVER role required"},
            )

    async def decide(
        self,
        session: AsyncSession,
        approval_id: uuid.UUID,
        decision: ApprovalStatus,
        note: str | None,
        ctx: CommandContext,
    ) -> Approval:
        if ctx.actor.kind != ActorKind.HUMAN or ActorRole.APPROVER not in ctx.actor.roles:
            raise Unauthorized("Only HUMAN approvers may decide approvals")
        command_map = {
            ApprovalStatus.APPROVED: "approve",
            ApprovalStatus.REJECTED: "reject",
            ApprovalStatus.CHANGES_REQUESTED: "request_changes",
        }
        command = command_map.get(decision)
        if command is None:
            raise DomainError(code="INVALID_DECISION", message="Invalid approval decision")
        approval = await session.get(Approval, approval_id)
        if approval is None:
            raise DomainError(code="NOT_FOUND", message="Approval not found")
        await self.transitions.transition(
            session,
            "approval",
            approval_id,
            ApprovalStatus.PENDING.value,
            command,
            ctx,
        )
        approval.decided_by_actor_id = ctx.actor.id
        approval.decision_note = note
        approval.decided_at = datetime.now(UTC)
        await append_domain_event(
            session,
            aggregate_type="approval",
            aggregate_id=approval.id,
            event_type="approval.decided",
            payload={"decision": decision.value},
            actor_id=ctx.actor.id,
            correlation_id=ctx.correlation_id,
            project_id=approval.project_id,
            delivery_cycle_id=approval.delivery_cycle_id,
        )
        if approval.delivery_cycle_id is not None:
            from core.release.service import ReleaseService

            await ReleaseService().on_approval_decided(session, approval, ctx)
            from core.release.triggers import on_eligibility_trigger

            await on_eligibility_trigger(session, approval.delivery_cycle_id, ctx)
        return approval

    async def is_satisfied(
        self,
        session: AsyncSession,
        approval_type: ApprovalType,
        subject_type: str,
        subject_id: uuid.UUID,
        subject_hash: str,
    ) -> bool:
        result = await session.execute(
            select(Approval).where(
                Approval.approval_type == approval_type,
                Approval.subject_type == subject_type,
                Approval.subject_id == subject_id,
                Approval.status == ApprovalStatus.APPROVED,
            )
        )
        row = result.scalar_one_or_none()
        if row is None:
            return False
        return row.subject_hash == subject_hash
