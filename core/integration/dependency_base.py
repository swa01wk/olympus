"""Multi-dependency base resolution (D-14)."""

from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.assurance.findings import FindingService
from core.commands.context import CommandContext
from core.domain.candidate_commits.models import CandidateCommit
from core.domain.delivery_cycles.models import DeliveryCycle
from core.domain.enums import TaskStatus
from core.domain.tasks.models import Task, TaskDependency
from core.execution.snapshots.base_commit import BaseResolution
from core.integration.enums import FindingSeverity, FindingSource
from core.integrations.connectors.base import ConnectorAction
from core.integrations.connectors.git_local import GitLocalConnector


class DependencyBaseResolver:
    async def resolve(
        self,
        session: AsyncSession,
        task: Task,
        repository_id: uuid.UUID,
        ctx: CommandContext | None = None,
    ) -> BaseResolution:
        deps = await session.execute(
            select(TaskDependency).where(TaskDependency.task_id == task.id)
        )
        dep_ids = [d.depends_on_task_id for d in deps.scalars()]
        if len(dep_ids) < 2:
            raise ValueError("BASE_RESOLVER_UNAVAILABLE")
        shas: list[str] = []
        for dep_id in sorted(dep_ids, key=str):
            dep_task = await session.get(Task, dep_id)
            if dep_task is None or dep_task.status != TaskStatus.COMPLETED:
                raise ValueError(f"DEPENDENCY_INCOMPLETE:{dep_id}")
            cc = await session.execute(
                select(CandidateCommit)
                .where(CandidateCommit.task_id == dep_id)
                .order_by(CandidateCommit.created_at.desc())
                .limit(1)
            )
            commit = cc.scalar_one_or_none()
            if commit is None:
                raise ValueError(f"DEPENDENCY_INCOMPLETE:{dep_id}")
            shas.append(commit.sha)
        cycle = await session.get(DeliveryCycle, task.delivery_cycle_id)
        if cycle is None or cycle.repository_id is None:
            raise ValueError("BASE_COMMIT_UNAVAILABLE")
        from core.domain.repositories.models import Repository, RepositoryWorkspace

        repo = await session.get(Repository, cycle.repository_id)
        ws = await session.get(RepositoryWorkspace, repo.workspace_id if repo else None)
        if ws is None:
            raise ValueError("BASE_COMMIT_UNAVAILABLE")
        logical = ws.logical_location
        branch = f"olympus/depbase/{task.key}-{len(shas)}"
        connector = GitLocalConnector()
        result = connector._action_merge_candidates(
            ConnectorAction(
                connector="git_local",
                action="merge_candidates",
                target_resource=logical,
                inputs={
                    "logical_location": logical,
                    "base_sha": cycle.base_sha or shas[0],
                    "candidate_shas": shas,
                    "branch": branch,
                },
                idempotency_key=f"depbase-{task.id}",
                correlation_id=str(task.id),
                expected_result_schema="MergeCandidatesResult",
            )
        )
        if result.status != "SUCCEEDED" or not result.normalized_result:
            if ctx is not None and cycle is not None:
                await FindingService().create(
                    session,
                    project_id=cycle.project_id,
                    delivery_cycle_id=cycle.id,
                    source=FindingSource.INTEGRATION,
                    category="DEPENDENCY_BASE_CONFLICT",
                    severity=FindingSeverity.BLOCKER,
                    title=f"Dependency base conflict for {task.key}",
                    detail={"branch": branch, "shas": shas, "error": result.error_class},
                    ctx=ctx,
                )
            raise ValueError("DEPENDENCY_BASE_CONFLICT")
        merged_sha = str(result.normalized_result["integrated_sha"])
        return BaseResolution(
            policy="DEPENDENCY_INTEGRATION",
            base_commit=merged_sha,
            commit_available=True,
            inputs={"policy": "DEPENDENCY_INTEGRATION", "branch": branch, "shas": shas},
            repository={"repository_id": str(repository_id)},
        )
