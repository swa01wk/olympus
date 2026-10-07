"""Release lifecycle, approval wiring, and execution scheduling."""

from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.commands.context import CommandContext
from core.domain.approvals.models import Approval
from core.domain.approvals.service import ApprovalService
from core.domain.delivery_cycles.models import DeliveryCycle
from core.domain.delivery_cycles.service import DeliveryCycleService
from core.domain.enums import ApprovalStatus, ApprovalType, DeliveryCycleType, TaskOrigin, WorkType
from core.domain.events.append import append_domain_event
from core.domain.exceptions import DomainError
from core.domain.projects.models import ProjectSequence
from core.domain.task_contracts.schemas import TaskContractBody, VersionedRef
from core.domain.task_contracts.service import ContractService
from core.domain.tasks.service import TaskService
from core.integration.enums import ICStatus
from core.integration.models import IntegrationCandidate
from core.policy.policy_service import PolicyService
from core.release.eligibility import ReleaseEligibilityService
from core.release.enums import ReleaseStatus
from core.release.manifest import ManifestBuilder
from core.release.models import Release
from core.scheduler.admission import AdmissionService
from core.state.transition_service import TransitionService


async def next_release_key(session: AsyncSession, project_id: uuid.UUID) -> str:
    for _ in range(8):
        result = await session.execute(
            select(ProjectSequence)
            .where(
                ProjectSequence.project_id == project_id,
                ProjectSequence.sequence_name == "release",
            )
            .with_for_update()
        )
        row = result.scalar_one_or_none()
        if row is None:
            from sqlalchemy.exc import IntegrityError

            try:
                async with session.begin_nested():
                    session.add(
                        ProjectSequence(
                            project_id=project_id,
                            sequence_name="release",
                            next_value=1,
                        )
                    )
                    await session.flush()
            except IntegrityError:
                continue
            result = await session.execute(
                select(ProjectSequence)
                .where(
                    ProjectSequence.project_id == project_id,
                    ProjectSequence.sequence_name == "release",
                )
                .with_for_update()
            )
            row = result.scalar_one()
        value = row.next_value
        row.next_value = value + 1
        return f"R{value}"
    raise RuntimeError("failed to allocate release key")


class ReleaseService:
    def __init__(
        self,
        transitions: TransitionService | None = None,
        policy: PolicyService | None = None,
    ) -> None:
        self.transitions = transitions or TransitionService()
        self.policy = policy

    async def create_release(
        self,
        session: AsyncSession,
        cycle_id: uuid.UUID,
        ctx: CommandContext,
    ) -> Release:
        cycle = await session.get(DeliveryCycle, cycle_id)
        if cycle is None:
            raise DomainError(code="NOT_FOUND", message="Delivery cycle not found")
        release_states = {"RELEASE", "ASSURANCE"}
        if cycle.type == DeliveryCycleType.BROWNFIELD_ONBOARDING and cycle.state == "REMEDIATION":
            pass
        elif cycle.state not in release_states:
            raise DomainError(
                code="INVALID_CYCLE_STATE",
                message=f"Cannot create release in state {cycle.state}",
            )
        ic = await self._require_ready_ic(session, cycle_id)
        assert ic.integrated_sha is not None
        existing = await session.execute(
            select(Release).where(
                Release.delivery_cycle_id == cycle_id,
                Release.status.not_in(
                    [ReleaseStatus.SUPERSEDED, ReleaseStatus.RELEASED, ReleaseStatus.FAILED]
                ),
            )
        )
        if existing.scalar_one_or_none() is not None:
            raise DomainError(code="RELEASE_EXISTS", message="Active release already exists")
        key = await next_release_key(session, cycle.project_id)
        release = Release(
            key=key,
            project_id=cycle.project_id,
            delivery_cycle_id=cycle.id,
            integration_candidate_id=ic.id,
            integrated_sha=ic.integrated_sha,
            status=ReleaseStatus.DRAFT,
        )
        session.add(release)
        await session.flush()
        content, content_hash = await ManifestBuilder().build_draft(session, key, cycle, ic, ctx)
        manifest = await ManifestBuilder().persist(session, release.id, content, content_hash)
        release.manifest_id = manifest.id
        await session.flush()
        await append_domain_event(
            session,
            aggregate_type="release",
            aggregate_id=release.id,
            event_type="release.created",
            payload={"key": key, "integrated_sha": ic.integrated_sha},
            actor_id=ctx.actor.id,
            correlation_id=ctx.correlation_id,
            project_id=cycle.project_id,
            delivery_cycle_id=cycle.id,
        )
        await ReleaseEligibilityService().recompute_and_persist(session, cycle.id, ctx)
        return release

    async def mark_eligible(
        self,
        session: AsyncSession,
        release: Release,
        ctx: CommandContext,
    ) -> None:
        if release.status == ReleaseStatus.ELIGIBLE:
            return
        release.status = ReleaseStatus.ELIGIBLE
        await session.flush()
        if release.manifest_id is None:
            raise DomainError(code="MANIFEST_MISSING", message="Release manifest missing")
        manifest = await ManifestBuilder().load_manifest(session, release.manifest_id)
        if manifest is None:
            raise DomainError(code="MANIFEST_MISSING", message="Release manifest missing")
        pol = self.policy
        approval = await ApprovalService(policy=pol).request(
            session,
            release.project_id,
            release.delivery_cycle_id,
            ApprovalType.RELEASE,
            subject_type="release_manifest",
            subject_id=manifest.id,
            subject_version=1,
            subject_hash=manifest.content_hash,
            ctx=ctx,
            policy=pol,
        )
        release.approval_id = approval.id
        await append_domain_event(
            session,
            aggregate_type="release",
            aggregate_id=release.id,
            event_type="release.eligible",
            payload={"approval_id": str(approval.id)},
            actor_id=ctx.actor.id,
            correlation_id=ctx.correlation_id,
            project_id=release.project_id,
            delivery_cycle_id=release.delivery_cycle_id,
        )

    async def mark_not_eligible(
        self,
        session: AsyncSession,
        release: Release,
        ctx: CommandContext,
    ) -> None:
        if release.status == ReleaseStatus.NOT_ELIGIBLE:
            return
        prev = release.status
        release.status = ReleaseStatus.NOT_ELIGIBLE
        await session.flush()
        if prev == ReleaseStatus.ELIGIBLE:
            await append_domain_event(
                session,
                aggregate_type="release",
                aggregate_id=release.id,
                event_type="release.blocked",
                payload={},
                actor_id=ctx.actor.id,
                correlation_id=ctx.correlation_id,
                project_id=release.project_id,
                delivery_cycle_id=release.delivery_cycle_id,
            )

    async def approve_release(
        self,
        session: AsyncSession,
        release_id: uuid.UUID,
        ctx: CommandContext,
    ) -> Release:
        release = await session.get(Release, release_id)
        if release is None:
            raise DomainError(code="NOT_FOUND", message="Release not found")
        if release.status != ReleaseStatus.ELIGIBLE:
            raise DomainError(code="INVALID_STATE", message="Release not eligible")
        if release.approval_id is None:
            raise DomainError(code="APPROVAL_MISSING", message="No approval request")
        if release.manifest_id is None:
            raise DomainError(code="MANIFEST_MISSING", message="Manifest missing")
        manifest = await ManifestBuilder().load_manifest(session, release.manifest_id)
        if manifest is None:
            raise DomainError(code="MANIFEST_MISSING", message="Manifest missing")
        approval = await ApprovalService().decide(
            session, release.approval_id, ApprovalStatus.APPROVED, None, ctx
        )
        if approval.subject_hash != manifest.content_hash:
            raise DomainError(code="MANIFEST_CHANGED", message="Manifest hash mismatch")
        release.status = ReleaseStatus.APPROVED
        await append_domain_event(
            session,
            aggregate_type="release",
            aggregate_id=release.id,
            event_type="release.approved",
            payload={"approval_id": str(approval.id)},
            actor_id=ctx.actor.id,
            correlation_id=ctx.correlation_id,
            project_id=release.project_id,
            delivery_cycle_id=release.delivery_cycle_id,
        )
        return release

    async def execute_release(
        self,
        session: AsyncSession,
        release_id: uuid.UUID,
        ctx: CommandContext,
    ) -> uuid.UUID:
        release = await session.get(Release, release_id)
        if release is None:
            raise DomainError(code="NOT_FOUND", message="Release not found")
        if release.status != ReleaseStatus.APPROVED:
            raise DomainError(code="INVALID_STATE", message="Release must be APPROVED")
        cycle = await session.get(DeliveryCycle, release.delivery_cycle_id)
        if cycle is None:
            raise DomainError(code="NOT_FOUND", message="Cycle not found")
        eligible, _ = await ReleaseEligibilityService().evaluate(session, cycle, release=release)
        if not eligible:
            raise DomainError(code="NOT_ELIGIBLE", message="Release no longer eligible")
        release.status = ReleaseStatus.EXECUTING
        await session.flush()
        task = await TaskService().create_task(
            session,
            cycle.id,
            f"Release {release.key}",
            WorkType.RELEASE,
            TaskOrigin.CONTROL_PLANE,
            ctx,
            priority=0,
        )
        body = TaskContractBody(
            objective=f"Governed release {release.key}",
            work_type=WorkType.RELEASE,
            inputs=[
                VersionedRef(
                    ref_type="RELEASE",
                    ref_id=release.id,
                    version=None,
                    key=release.key,
                )
            ],
            repository_id=cycle.repository_id,
            base_policy="EXPLICIT_SHA",
            base_commit=release.integrated_sha,
            allowed_scope=["**"],
            allowed_actions=[],
            required_outputs=["release_result"],
            executor_kind="DETERMINISTIC",
            deterministic_executor="stratos.release",
            agent_profile="stratos.release",
            timeouts={"wall_clock_s": 3600},
        )
        contract = await ContractService().create_draft(
            session, task.id, body, "release.service", ctx
        )
        await ContractService().issue(session, contract.id, ctx)
        await TaskService().mark_ready(session, task.id, ctx)
        execution = await AdmissionService().admit_task(session, task.id, ctx)
        release.release_execution_id = execution.id
        await append_domain_event(
            session,
            aggregate_type="release",
            aggregate_id=release.id,
            event_type="release.executing",
            payload={"execution_id": str(execution.id)},
            actor_id=ctx.actor.id,
            correlation_id=ctx.correlation_id,
            project_id=release.project_id,
            delivery_cycle_id=release.delivery_cycle_id,
        )
        return execution.id

    async def on_approval_decided(
        self,
        session: AsyncSession,
        approval: Approval,
        ctx: CommandContext,
    ) -> None:
        if approval.approval_type != ApprovalType.RELEASE:
            return
        if approval.status != ApprovalStatus.APPROVED:
            return
        release = await session.execute(select(Release).where(Release.approval_id == approval.id))
        rel = release.scalar_one_or_none()
        if rel is None or rel.status != ReleaseStatus.ELIGIBLE:
            return
        if rel.manifest_id is None:
            return
        manifest = await ManifestBuilder().load_manifest(session, rel.manifest_id)
        if manifest is None or manifest.content_hash != approval.subject_hash:
            return
        rel.status = ReleaseStatus.APPROVED
        await append_domain_event(
            session,
            aggregate_type="release",
            aggregate_id=rel.id,
            event_type="release.approved",
            payload={"approval_id": str(approval.id)},
            actor_id=ctx.actor.id,
            correlation_id=ctx.correlation_id,
            project_id=rel.project_id,
            delivery_cycle_id=rel.delivery_cycle_id,
        )

    async def maybe_advance_cycle_to_release(
        self,
        session: AsyncSession,
        cycle_id: uuid.UUID,
        ctx: CommandContext,
    ) -> None:
        cycle = await session.get(DeliveryCycle, cycle_id)
        if cycle is None or cycle.state != "ASSURANCE":
            return
        svc = DeliveryCycleService()
        allowed = await svc.allowed_commands(session, cycle, ctx)
        cmd = next((c for c in allowed if c.get("command") == "start_release"), None)
        if cmd is None or not cmd.get("allowed"):
            return
        await svc.run_command(session, cycle.id, "start_release", cycle.state, ctx)

    async def _require_ready_ic(
        self, session: AsyncSession, cycle_id: uuid.UUID
    ) -> IntegrationCandidate:
        result = await session.execute(
            select(IntegrationCandidate)
            .where(
                IntegrationCandidate.delivery_cycle_id == cycle_id,
                IntegrationCandidate.status == ICStatus.READY,
            )
            .order_by(IntegrationCandidate.created_at.desc())
            .limit(1)
        )
        ic = result.scalar_one_or_none()
        if ic is None:
            raise DomainError(code="IC_NOT_READY", message="No READY integration candidate")
        return ic
