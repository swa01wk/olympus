"""Event-driven staleness for tasks, executions, baselines, and impact assessments."""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.assurance.findings import FindingService
from core.domain.delivery_cycles.models import DeliveryCycle
from core.domain.enums import ExecutionStatus, TaskStatus
from core.domain.executions.models import Execution, ExecutionSnapshot
from core.domain.repositories.models import Repository, RepositoryWorkspace
from core.domain.tasks.models import Task
from core.integration.enums import FindingSeverity, FindingSource
from core.intelligence.baselines.enums import BaselineStatus
from core.intelligence.baselines.models import BehavioralBaseline
from core.intelligence.code_index.changes import diff_stable_keys, load_index_entity_map
from core.intelligence.code_index.enums import IndexKind, IndexVersionStatus
from core.intelligence.code_index.models import CodeIndexVersion
from core.intelligence.impact.enums import ImpactAssessmentStatus
from core.intelligence.impact.models import ImpactAssessment, StalenessEvent
from core.repositories.git_inspect import GitInspector
from core.repositories.workspace_locator import WorkspaceLocator


@dataclass
class StalenessReport:
    events: list[StalenessEvent] = field(default_factory=list)


class StalenessService:
    async def _record(
        self,
        session: AsyncSession,
        *,
        subject_type: str,
        subject_id: uuid.UUID,
        from_status: str | None,
        to_status: str,
        cause_type: str,
        cause_ref: str | None,
        delivery_cycle_id: uuid.UUID | None,
    ) -> StalenessEvent:
        ev = StalenessEvent(
            subject_type=subject_type,
            subject_id=subject_id,
            from_status=from_status,
            to_status=to_status,
            cause_type=cause_type,
            cause_ref=cause_ref,
            delivery_cycle_id=delivery_cycle_id,
        )
        session.add(ev)
        await session.flush()
        return ev

    async def on_canonical_revision_changed(
        self,
        session: AsyncSession,
        repository_id: uuid.UUID,
        from_sha: str | None,
        to_sha: str,
        cause: str,
        *,
        exclude_cycle_id: uuid.UUID | None = None,
        ctx: Any = None,
    ) -> StalenessReport:
        report = StalenessReport()
        cycles = await session.execute(
            select(DeliveryCycle).where(
                DeliveryCycle.repository_id == repository_id,
                DeliveryCycle.state.notin_(("COMPLETE", "FAILED", "CANCELLED")),
            )
        )
        repo = await session.get(Repository, repository_id)
        git_dir = None
        if repo and repo.workspace_id:
            ws = await session.get(RepositoryWorkspace, repo.workspace_id)
            if ws:
                git_dir = WorkspaceLocator().resolve(ws.storage_backend, ws.logical_location)
        inspector = GitInspector()

        for cycle in cycles.scalars():
            if exclude_cycle_id and cycle.id == exclude_cycle_id:
                continue
            execs = await session.execute(
                select(Execution).where(
                    Execution.delivery_cycle_id == cycle.id,
                    Execution.status.in_((ExecutionStatus.QUEUED, ExecutionStatus.LEASED)),
                )
            )
            for ex in execs.scalars():
                snap = await session.execute(
                    select(ExecutionSnapshot)
                    .where(ExecutionSnapshot.execution_id == ex.id)
                    .order_by(ExecutionSnapshot.created_at.desc())
                    .limit(1)
                )
                row = snap.scalar_one_or_none()
                base = row.base_commit if row else None
                stale = False
                if base and git_dir and not inspector.is_ancestor(git_dir, base, to_sha):
                    stale = True
                if stale:
                    prev = ex.status.value
                    ex.status = ExecutionStatus.STALE
                    report.events.append(
                        await self._record(
                            session,
                            subject_type="EXECUTION",
                            subject_id=ex.id,
                            from_status=prev,
                            to_status=ExecutionStatus.STALE.value,
                            cause_type="CANONICAL_REVISION_CHANGED",
                            cause_ref=to_sha,
                            delivery_cycle_id=cycle.id,
                        )
                    )

            ias = await session.execute(
                select(ImpactAssessment).where(
                    ImpactAssessment.delivery_cycle_id == cycle.id,
                    ImpactAssessment.status == ImpactAssessmentStatus.COMPLETE.value,
                )
            )
            for ia in ias.scalars():
                idx = await session.get(CodeIndexVersion, ia.index_version_id)
                if idx and idx.commit_sha != to_sha:
                    prev = ia.status
                    ia.status = ImpactAssessmentStatus.STALE.value
                    report.events.append(
                        await self._record(
                            session,
                            subject_type="IMPACT_ASSESSMENT",
                            subject_id=ia.id,
                            from_status=prev,
                            to_status=ImpactAssessmentStatus.STALE.value,
                            cause_type="CANONICAL_REVISION_CHANGED",
                            cause_ref=to_sha,
                            delivery_cycle_id=cycle.id,
                        )
                    )
                    completed_tasks = await session.execute(
                        select(Task).where(
                            Task.delivery_cycle_id == cycle.id,
                            Task.status == TaskStatus.COMPLETED,
                        )
                    )
                    for task in completed_tasks.scalars():
                        prev_task = task.status.value
                        task.status = TaskStatus.REVALIDATION_REQUIRED
                        report.events.append(
                            await self._record(
                                session,
                                subject_type="TASK",
                                subject_id=task.id,
                                from_status=prev_task,
                                to_status=TaskStatus.REVALIDATION_REQUIRED.value,
                                cause_type="CANONICAL_REVISION_CHANGED",
                                cause_ref=to_sha,
                                delivery_cycle_id=cycle.id,
                            )
                        )

            if git_dir:
                candidates = await session.execute(
                    select(CodeIndexVersion).where(
                        CodeIndexVersion.repository_id == repository_id,
                        CodeIndexVersion.kind == IndexKind.CANDIDATE,
                        CodeIndexVersion.status == IndexVersionStatus.READY,
                    )
                )
                for ver in candidates.scalars():
                    if not inspector.is_ancestor(git_dir, ver.commit_sha, to_sha):
                        ver.status = IndexVersionStatus.DISCARDED

            if (
                ctx is not None
                and cycle.base_sha
                and git_dir
                and from_sha
                and not inspector.is_ancestor(git_dir, cycle.base_sha, to_sha)
            ):
                await FindingService().create(
                    session,
                    project_id=cycle.project_id,
                    delivery_cycle_id=cycle.id,
                    source=FindingSource.INTEGRATION,
                    category="CYCLE_BASE_DIVERGED",
                    severity=FindingSeverity.BLOCKER,
                    title="Cycle base diverged from canonical revision",
                    detail={"base_sha": cycle.base_sha, "canonical_commit": to_sha},
                    ctx=ctx,
                )

        if from_sha and to_sha:
            await self._baseline_entity_changes(session, repository_id, from_sha, to_sha, report)
        return report

    async def _baseline_entity_changes(
        self,
        session: AsyncSession,
        repository_id: uuid.UUID,
        from_sha: str,
        to_sha: str,
        report: StalenessReport,
    ) -> None:
        old_idx = await session.execute(
            select(CodeIndexVersion)
            .where(
                CodeIndexVersion.repository_id == repository_id,
                CodeIndexVersion.commit_sha == from_sha,
                CodeIndexVersion.status == IndexVersionStatus.READY,
            )
            .limit(1)
        )
        new_idx = await session.execute(
            select(CodeIndexVersion)
            .where(
                CodeIndexVersion.repository_id == repository_id,
                CodeIndexVersion.commit_sha == to_sha,
                CodeIndexVersion.status == IndexVersionStatus.READY,
            )
            .limit(1)
        )
        old_v = old_idx.scalar_one_or_none()
        new_v = new_idx.scalar_one_or_none()
        if old_v is None or new_v is None:
            return
        old_map = {
            k: e.content_hash for k, e in (await load_index_entity_map(session, old_v.id)).items()
        }
        new_map = {
            k: e.content_hash for k, e in (await load_index_entity_map(session, new_v.id)).items()
        }
        changed_keys = {
            k
            for k, kind in diff_stable_keys(old_map, new_map).items()
            if kind.value in {"MODIFIED", "ADDED", "DELETED"}
        }
        if not changed_keys:
            return
        baselines = await session.execute(
            select(BehavioralBaseline).where(
                BehavioralBaseline.status == BaselineStatus.ACTIVE,
            )
        )
        for bl in baselines.scalars():
            if set(bl.exercised_stable_keys or []) & changed_keys:
                prev = bl.status.value
                bl.status = BaselineStatus.REVALIDATION_REQUIRED
                report.events.append(
                    await self._record(
                        session,
                        subject_type="BASELINE",
                        subject_id=bl.id,
                        from_status=prev,
                        to_status=BaselineStatus.REVALIDATION_REQUIRED.value,
                        cause_type="CANONICAL_REVISION_CHANGED",
                        cause_ref=to_sha,
                        delivery_cycle_id=None,
                    )
                )

    async def on_code_index_updated(
        self,
        session: AsyncSession,
        repository_id: uuid.UUID,
        commit_sha: str,
        *,
        exclude_cycle_id: uuid.UUID | None = None,
        ctx: Any = None,
    ) -> StalenessReport:
        repo = await session.get(Repository, repository_id)
        if repo is None:
            return StalenessReport()
        return await self.on_canonical_revision_changed(
            session,
            repository_id,
            repo.canonical_commit,
            commit_sha,
            "code_index.updated",
            exclude_cycle_id=exclude_cycle_id,
            ctx=ctx,
        )

    async def on_implementation_spec_superseded(
        self,
        session: AsyncSession,
        *,
        superseded_spec_id: uuid.UUID,
        delivery_cycle_id: uuid.UUID,
        ctx: Any = None,
    ) -> StalenessReport:
        report = StalenessReport()
        tasks = await session.execute(
            select(Task).where(
                Task.delivery_cycle_id == delivery_cycle_id,
                Task.implementation_spec_id == superseded_spec_id,
            )
        )
        task_ids = [t.id for t in tasks.scalars()]
        if not task_ids:
            return report
        execs = await session.execute(
            select(Execution).where(
                Execution.task_id.in_(task_ids),
                Execution.status.in_((ExecutionStatus.QUEUED, ExecutionStatus.LEASED)),
            )
        )
        for ex in execs.scalars():
            prev = ex.status.value
            ex.status = ExecutionStatus.STALE
            report.events.append(
                await self._record(
                    session,
                    subject_type="EXECUTION",
                    subject_id=ex.id,
                    from_status=prev,
                    to_status=ExecutionStatus.STALE.value,
                    cause_type="IMPLEMENTATION_SPEC_SUPERSEDED",
                    cause_ref=str(superseded_spec_id),
                    delivery_cycle_id=delivery_cycle_id,
                )
            )
        return report

    async def on_spec_delta_approved(
        self,
        session: AsyncSession,
        *,
        project_id: uuid.UUID,
        delivery_cycle_id: uuid.UUID,
        from_spec_id: uuid.UUID | None,
        to_spec_id: uuid.UUID,
        ctx: Any = None,
    ) -> StalenessReport:
        del project_id, from_spec_id, ctx
        report = StalenessReport()
        ias = await session.execute(
            select(ImpactAssessment).where(
                ImpactAssessment.delivery_cycle_id == delivery_cycle_id,
                ImpactAssessment.status != ImpactAssessmentStatus.COMPLETE.value,
            )
        )
        for ia in ias.scalars():
            prev = ia.status
            ia.status = ImpactAssessmentStatus.STALE.value
            report.events.append(
                await self._record(
                    session,
                    subject_type="IMPACT_ASSESSMENT",
                    subject_id=ia.id,
                    from_status=prev,
                    to_status=ImpactAssessmentStatus.STALE.value,
                    cause_type="SPEC_DELTA_APPROVED",
                    cause_ref=str(to_spec_id),
                    delivery_cycle_id=delivery_cycle_id,
                )
            )
        return report
