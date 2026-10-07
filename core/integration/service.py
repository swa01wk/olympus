"""IntegrationCandidate lifecycle."""

from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.assurance.findings import FindingService
from core.commands.context import CommandContext
from core.domain.candidate_commits.models import CandidateCommit
from core.domain.delivery_cycles.models import DeliveryCycle
from core.domain.enums import (
    RepositoryStatus,
    TaskOrigin,
    TaskStatus,
    WorkType,
)
from core.domain.events.append import append_domain_event
from core.domain.exceptions import DomainError
from core.domain.sequences import next_project_key
from core.domain.task_contracts.schemas import TaskContractBody, VersionedRef
from core.domain.task_contracts.service import ContractService
from core.domain.tasks.models import Task, TaskDependency
from core.domain.tasks.service import TaskService
from core.integration.canonical_revision import CanonicalRevisionGuardian
from core.integration.enums import FindingSeverity, FindingSource, ICStatus
from core.integration.models import IntegrationCandidate, IntegrationCandidateCommit
from core.integration.ordering import order_candidates
from core.repositories.git_inspect import GitInspector
from core.repositories.workspace_locator import WorkspaceLocator
from core.scheduler.admission import AdmissionService

_TERMINAL_IC = frozenset({ICStatus.READY, ICStatus.FAILED, ICStatus.CONFLICT, ICStatus.SUPERSEDED})


class IntegrationService:
    async def create(
        self,
        session: AsyncSession,
        cycle_id: uuid.UUID,
        ctx: CommandContext,
    ) -> IntegrationCandidate:
        cycle = await session.get(DeliveryCycle, cycle_id)
        if cycle is None:
            raise DomainError(code="NOT_FOUND", message="Delivery cycle not found")
        if cycle.repository_id is None:
            raise DomainError(code="REPOSITORY_NOT_BOUND", message="Cycle has no repository")
        from core.domain.enums import WorkspaceState
        from core.domain.repositories.models import Repository, RepositoryWorkspace

        repo = await session.get(Repository, cycle.repository_id)
        if repo is None or repo.status != RepositoryStatus.READY or repo.canonical_commit is None:
            raise DomainError(code="REPOSITORY_NOT_READY", message="Repository not ready")
        ws = await session.get(RepositoryWorkspace, repo.workspace_id)
        if ws is None or ws.state != WorkspaceState.READY:
            raise DomainError(code="REPOSITORY_NOT_READY", message="Workspace not ready")

        held = await CanonicalRevisionGuardian().holds_unreleased_revision(
            session, repo.id, exclude_cycle_id=cycle_id
        )
        if held is not None:
            raise DomainError(
                code="CANONICAL_REVISION_HELD",
                message="Another cycle holds an unreleased canonical revision",
                details={
                    "integration_candidate_id": str(held.id),
                    "cycle_id": str(held.delivery_cycle_id),
                },
            )

        base_sha = repo.canonical_commit
        if cycle.base_sha and not GitInspector().is_ancestor(
            WorkspaceLocator().resolve(ws.storage_backend, ws.logical_location),
            cycle.base_sha,
            base_sha,
        ):
            ic_key = await next_project_key(
                session, cycle.project_id, "integration_candidate", prefix="IC"
            )
            failed = IntegrationCandidate(
                key=ic_key,
                delivery_cycle_id=cycle_id,
                repository_id=repo.id,
                base_sha=base_sha,
                integration_branch=f"olympus/integration/{ic_key}",
                status=ICStatus.FAILED,
                ordering=[],
            )
            session.add(failed)
            await session.flush()
            await FindingService().create(
                session,
                project_id=cycle.project_id,
                delivery_cycle_id=cycle_id,
                source=FindingSource.INTEGRATION,
                category="BASE_NOT_ANCESTOR_OF_CANONICAL",
                severity=FindingSeverity.BLOCKER,
                title="Cycle base is not an ancestor of canonical commit",
                detail={"cycle_base_sha": cycle.base_sha, "canonical_commit": base_sha},
                ctx=ctx,
                integration_candidate_id=failed.id,
            )
            return failed

        await self._supersede_open(session, cycle_id)

        entries = await self._collect_candidate_entries(session, cycle_id)
        if not entries:
            raise DomainError(
                code="NO_CANDIDATE_COMMITS",
                message="No eligible candidate commits for integration",
            )

        dep_edges = await self._dependency_edges(session, cycle_id, {e[0] for e in entries})
        git_path = str(WorkspaceLocator().resolve(ws.storage_backend, ws.logical_location))
        ordered = order_candidates(
            git_dir_path=git_path,
            base_sha=base_sha,
            entries=entries,
            dependency_edges=dep_edges,
        )
        prior_ready = (
            await session.execute(
                select(IntegrationCandidate)
                .where(
                    IntegrationCandidate.delivery_cycle_id == cycle_id,
                    IntegrationCandidate.status == ICStatus.READY,
                )
                .order_by(IntegrationCandidate.created_at.desc())
                .limit(1)
            )
        ).scalar_one_or_none()

        ic_key = await next_project_key(
            session, cycle.project_id, "integration_candidate", prefix="IC"
        )
        branch = f"olympus/integration/{ic_key}"
        ic = IntegrationCandidate(
            key=ic_key,
            delivery_cycle_id=cycle_id,
            repository_id=repo.id,
            base_sha=base_sha,
            integration_branch=branch,
            supersedes_id=prior_ready.id if prior_ready is not None else None,
            status=ICStatus.CREATED,
            ordering=[
                {
                    "task_key": o.task_key,
                    "candidate_commit_sha": o.candidate_commit_sha,
                    "position": o.position,
                    "included": o.included,
                    "skip_reason": o.skip_reason,
                }
                for o in ordered
            ],
        )
        session.add(ic)
        if prior_ready is not None:
            prior_ready.status = ICStatus.SUPERSEDED
        await session.flush()
        for o in ordered:
            session.add(
                IntegrationCandidateCommit(
                    integration_candidate_id=ic.id,
                    candidate_commit_id=o.candidate_commit_id,
                    position=o.position,
                    included=o.included,
                    skip_reason=o.skip_reason,
                )
            )
        task = await self._create_integration_task(session, cycle, ic, ctx)
        ic.integration_execution_id = await self._admit_integration_task(session, task.id, ctx)
        await session.flush()
        await append_domain_event(
            session,
            aggregate_type="integration_candidate",
            aggregate_id=ic.id,
            event_type="integration.created",
            payload={"key": ic_key, "delivery_cycle_id": str(cycle_id)},
            actor_id=ctx.actor.id,
            correlation_id=ctx.correlation_id,
            project_id=cycle.project_id,
            delivery_cycle_id=cycle_id,
        )
        return ic

    async def _supersede_open(self, session: AsyncSession, cycle_id: uuid.UUID) -> None:
        result = await session.execute(
            select(IntegrationCandidate).where(
                IntegrationCandidate.delivery_cycle_id == cycle_id,
                IntegrationCandidate.status.notin_(list(_TERMINAL_IC)),
            )
        )
        for row in result.scalars():
            row.status = ICStatus.SUPERSEDED

    async def _collect_candidate_entries(
        self, session: AsyncSession, cycle_id: uuid.UUID
    ) -> list[tuple[uuid.UUID, str, uuid.UUID, str]]:
        origins = (
            TaskOrigin.IMPLEMENTATION_PLAN,
            TaskOrigin.REMEDIATION,
            TaskOrigin.REPAIR,
        )
        tasks = await session.execute(
            select(Task).where(
                Task.delivery_cycle_id == cycle_id,
                Task.work_type == WorkType.CODE_CHANGE,
                Task.origin.in_(origins),
                Task.status == TaskStatus.COMPLETED,
            )
        )
        entries: list[tuple[uuid.UUID, str, uuid.UUID, str]] = []
        for task in tasks.scalars():
            cc = await session.execute(
                select(CandidateCommit)
                .where(CandidateCommit.task_id == task.id)
                .order_by(CandidateCommit.created_at.desc())
                .limit(1)
            )
            commit = cc.scalar_one_or_none()
            if commit is not None:
                entries.append((task.id, task.key, commit.id, commit.sha))
        return entries

    async def _dependency_edges(
        self, session: AsyncSession, cycle_id: uuid.UUID, task_ids: set[uuid.UUID]
    ) -> list[tuple[uuid.UUID, uuid.UUID]]:
        edges: list[tuple[uuid.UUID, uuid.UUID]] = []
        for tid in task_ids:
            deps = await session.execute(
                select(TaskDependency).where(TaskDependency.task_id == tid)
            )
            for dep in deps.scalars():
                if dep.depends_on_task_id in task_ids:
                    edges.append((tid, dep.depends_on_task_id))
        return edges

    async def _create_integration_task(
        self,
        session: AsyncSession,
        cycle: DeliveryCycle,
        ic: IntegrationCandidate,
        ctx: CommandContext,
    ) -> Task:
        task = await TaskService().create_task(
            session,
            cycle.id,
            f"Integrate candidate {ic.key}",
            WorkType.INTEGRATION,
            TaskOrigin.CONTROL_PLANE,
            ctx,
            priority=0,
        )
        body = TaskContractBody(
            objective=f"Merge candidate commits for {ic.key}",
            work_type=WorkType.INTEGRATION,
            inputs=[
                VersionedRef(
                    ref_type="INTEGRATION_CANDIDATE",
                    ref_id=ic.id,
                    version=None,
                    key=ic.key,
                )
            ],
            repository_id=ic.repository_id,
            base_policy="EXPLICIT_SHA",
            base_commit=ic.base_sha,
            allowed_scope=["**"],
            allowed_actions=["test.run", "shell.run"],
            required_outputs=["integration_result"],
            executor_kind="DETERMINISTIC",
            deterministic_executor="integration.merge",
            timeouts={"wall_clock_s": 3600},
        )
        contract = await ContractService().create_draft(
            session, task.id, body, "integration.service", ctx
        )
        await ContractService().issue(session, contract.id, ctx)
        await TaskService().mark_ready(session, task.id, ctx)
        return task

    async def _admit_integration_task(
        self, session: AsyncSession, task_id: uuid.UUID, ctx: CommandContext
    ) -> uuid.UUID:
        execution = await AdmissionService().admit_task(session, task_id, ctx)
        return execution.id

    async def get_latest_ready(
        self, session: AsyncSession, cycle_id: uuid.UUID
    ) -> IntegrationCandidate | None:
        result = await session.execute(
            select(IntegrationCandidate)
            .where(
                IntegrationCandidate.delivery_cycle_id == cycle_id,
                IntegrationCandidate.status == ICStatus.READY,
            )
            .order_by(IntegrationCandidate.created_at.desc())
            .limit(1)
        )
        return result.scalar_one_or_none()
