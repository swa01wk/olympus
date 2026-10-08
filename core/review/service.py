"""Schedule producing-agent re-runs after CHANGES_REQUESTED."""

from __future__ import annotations

import json
import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.commands.context import CommandContext
from core.domain.approvals.models import Approval
from core.domain.delivery_cycles.models import DeliveryCycle
from core.domain.enums import ApprovalStatus, ApprovalType
from core.domain.events.append import append_domain_event
from core.domain.task_contracts.models import TaskContract
from core.domain.tasks.models import Task
from core.intelligence.impact.models import SpecDelta
from core.planning.models import Architecture, ImplementationSpec
from core.planning.orchestrator import PlanningOrchestrator
from core.product_model.changes.orchestrator import FeatureChangeOrchestrator
from core.product_model.decomposition import DecompositionOrchestrator
from core.product_model.defects.orchestrator import BugFixOrchestrator
from core.product_model.models import ProductSource
from core.review.context import RevisionContext


class RevisionService:
    async def find_revision_task_id(
        self,
        session: AsyncSession,
        approval_id: uuid.UUID,
        delivery_cycle_id: uuid.UUID | None,
    ) -> uuid.UUID | None:
        if delivery_cycle_id is None:
            return None
        aid = str(approval_id)
        rows = await session.execute(
            select(Task.id, TaskContract.body)
            .join(TaskContract, TaskContract.task_id == Task.id)
            .where(Task.delivery_cycle_id == delivery_cycle_id)
            .order_by(Task.created_at.desc())
        )
        for task_id, body in rows.all():
            if not isinstance(body, dict):
                continue
            snap = body.get("_snapshot")
            if isinstance(snap, dict) and snap.get("revision_of_approval_id") == aid:
                return uuid.UUID(str(task_id))
        return None

    async def request_revision(
        self,
        session: AsyncSession,
        approval: Approval,
        ctx: CommandContext,
    ) -> uuid.UUID | None:
        if approval.status != ApprovalStatus.CHANGES_REQUESTED:
            return None
        existing = await self.find_revision_task_id(
            session, approval.id, approval.delivery_cycle_id
        )
        if existing is not None:
            return existing
        if approval.delivery_cycle_id is None:
            return None

        previous_json = await self._previous_output_json(session, approval)
        revision = RevisionContext(
            approval_id=approval.id,
            feedback=approval.decision_note or "",
            previous_output_json=previous_json,
            subject_type=approval.subject_type,
            subject_id=approval.subject_id,
        )
        task_id = await self._schedule(session, approval, revision, ctx)
        if task_id is None:
            return None
        await append_domain_event(
            session,
            aggregate_type="revision",
            aggregate_id=approval.id,
            event_type="revision.requested",
            payload={
                "approval_id": str(approval.id),
                "subject_type": approval.subject_type,
                "subject_id": str(approval.subject_id),
                "task_id": str(task_id),
            },
            actor_id=ctx.actor.id,
            correlation_id=ctx.correlation_id,
            project_id=approval.project_id,
            delivery_cycle_id=approval.delivery_cycle_id,
        )
        return task_id

    async def _previous_output_json(
        self,
        session: AsyncSession,
        approval: Approval,
    ) -> str:
        subject_type = approval.subject_type
        if subject_type == "architecture":
            arch = await session.get(Architecture, approval.subject_id)
            if arch is not None:
                return json.dumps(arch.body, sort_keys=True)
        if subject_type == "implementation_spec":
            impl = await session.get(ImplementationSpec, approval.subject_id)
            if impl is not None:
                return json.dumps(impl.body, sort_keys=True)
        if subject_type == "SPEC_DELTA":
            delta = await session.get(SpecDelta, approval.subject_id)
            if delta is not None:
                return json.dumps(delta.changes, sort_keys=True)
        if subject_type == "scope_set":
            return json.dumps({"scope_set_id": str(approval.subject_id)}, sort_keys=True)
        return "{}"

    async def _schedule(
        self,
        session: AsyncSession,
        approval: Approval,
        revision: RevisionContext,
        ctx: CommandContext,
    ) -> uuid.UUID | None:
        cycle_id = approval.delivery_cycle_id
        assert cycle_id is not None

        if approval.approval_type in {
            ApprovalType.RELEASE,
            ApprovalType.FINDING_WAIVER,
            ApprovalType.ACTION,
            ApprovalType.PROMOTION,
            ApprovalType.UNREPRODUCED_REPAIR,
        }:
            return None

        if approval.approval_type == ApprovalType.SCOPE and approval.subject_type == "scope_set":
            cycle = await session.get(DeliveryCycle, cycle_id)
            if cycle is None or cycle.state not in {"DISCOVERY", "PRODUCT_MODEL"}:
                return None
            source = (
                await session.execute(
                    select(ProductSource)
                    .where(ProductSource.delivery_cycle_id == cycle_id)
                    .order_by(ProductSource.version.desc())
                    .limit(1)
                )
            ).scalar_one_or_none()
            if source is None:
                return None
            started = await DecompositionOrchestrator().start_decomposition(
                session,
                source=source,
                delivery_cycle_id=cycle_id,
                ctx=ctx,
                revision=revision,
            )
            return uuid.UUID(started["task_id"])

        if (
            approval.approval_type == ApprovalType.ARCHITECTURE
            and approval.subject_type == "architecture"
        ):
            arch = await session.get(Architecture, approval.subject_id)
            if arch is not None and arch.kind == "DELTA":
                return None
            started = await PlanningOrchestrator().start_architecture_proposal(
                session, cycle_id, ctx, revision=revision
            )
            return uuid.UUID(started["task_id"])

        if (
            approval.approval_type == ApprovalType.ARCHITECTURE_DELTA
            and approval.subject_type == "architecture"
        ):
            arch = await session.get(Architecture, approval.subject_id)
            if arch is None or arch.kind != "DELTA":
                return None
            started = await FeatureChangeOrchestrator().schedule_architecture_delta(
                session, cycle_id, ctx, revision=revision
            )
            return uuid.UUID(started["architecture_delta_task_id"])

        if (
            approval.approval_type == ApprovalType.IMPLEMENTATION_SPEC
            and approval.subject_type == "implementation_spec"
        ):
            impl = await session.get(ImplementationSpec, approval.subject_id)
            if impl is None:
                return None
            if impl.kind == "REMEDIATION":
                return None
            if impl.kind == "DELTA":
                started = await FeatureChangeOrchestrator().schedule_implementation_spec_delta(
                    session, cycle_id, ctx, revision=revision
                )
                return uuid.UUID(started["implementation_spec_task_id"])
            if impl.kind == "REPAIR":
                started = await BugFixOrchestrator().schedule_repair_implementation_spec(
                    session, cycle_id, ctx, revision=revision
                )
                return uuid.UUID(started["repair_implementation_spec_task_id"])
            tasks = await PlanningOrchestrator().start_implementation_spec_generation(
                session,
                cycle_id,
                ctx,
                feature_spec_id=impl.feature_spec_id,
                revision=revision,
            )
            if not tasks:
                return None
            return uuid.UUID(tasks[0]["task_id"])

        if approval.approval_type == ApprovalType.SPEC_DELTA:
            started = await FeatureChangeOrchestrator().schedule_change_interpret(
                session, cycle_id, ctx, revision=revision
            )
            return uuid.UUID(started["interpret_task_id"])

        return None
