from __future__ import annotations

import uuid
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.domain.delivery_cycles.models import DeliveryCycle
from core.domain.enums import RepositoryStatus
from core.domain.repositories.models import Repository, RepositoryRevision, RepositoryWorkspace
from core.domain.task_contracts.schemas import TaskContractBody
from core.domain.tasks.models import Task
from core.repositories.git_inspect import GitInspector
from core.repositories.workspace_locator import WorkspaceLocator


@dataclass(frozen=True)
class BaseResolution:
    policy: str
    base_commit: str | None
    commit_available: bool
    inputs: dict[str, object]
    repository: dict[str, object] | None


class BaseCommitResolver:
    def __init__(
        self,
        *,
        git: GitInspector | None = None,
        workspace_locator: WorkspaceLocator | None = None,
    ) -> None:
        self._git = git or GitInspector()
        self._locator = workspace_locator or WorkspaceLocator()

    async def resolve(
        self,
        session: AsyncSession,
        contract: TaskContractBody,
        task: Task,
    ) -> BaseResolution:
        policy = contract.base_policy
        if policy == "DEPENDENCY_INTEGRATION":
            from core.integration.dependency_base import DependencyBaseResolver

            if contract.repository_id is None:
                raise ValueError("BASE_RESOLVER_UNAVAILABLE")
            return await DependencyBaseResolver().resolve(
                session, task, contract.repository_id, ctx=None
            )

        repository_id = contract.repository_id
        repo_block: dict[str, object] | None = None
        base_commit: str | None = None
        commit_available = True

        if policy == "NONE":
            return BaseResolution(
                policy=policy,
                base_commit=None,
                commit_available=True,
                inputs={"policy": policy},
                repository=None,
            )

        if policy == "EXPLICIT_SHA":
            base_commit = contract.base_commit
            if repository_id is None:
                commit_available = base_commit is not None
            else:
                commit_available = await self._commit_exists(session, repository_id, base_commit)
            repo_block = await self._repository_block(session, repository_id)
            return BaseResolution(
                policy=policy,
                base_commit=base_commit,
                commit_available=commit_available,
                inputs={"policy": policy, "base_commit": base_commit},
                repository=repo_block,
            )

        if policy == "CYCLE_BASE":
            cycle = await session.get(DeliveryCycle, task.delivery_cycle_id)
            if cycle is None:
                raise ValueError("cycle missing")
            base_commit = cycle.base_sha
            if repository_id is None:
                repository_id = cycle.repository_id
            if base_commit is None or repository_id is None:
                commit_available = False
            else:
                repo = await session.get(Repository, repository_id)
                if repo is None or repo.status != RepositoryStatus.READY:
                    commit_available = False
                else:
                    commit_available = await self._commit_exists(
                        session, repository_id, base_commit
                    )
            repo_block = await self._repository_block(session, repository_id)
            return BaseResolution(
                policy=policy,
                base_commit=base_commit,
                commit_available=commit_available,
                inputs={"policy": policy, "delivery_cycle_id": str(task.delivery_cycle_id)},
                repository=repo_block,
            )

        raise ValueError(f"unsupported base policy: {policy}")

    async def _repository_block(
        self, session: AsyncSession, repository_id: uuid.UUID | None
    ) -> dict[str, object] | None:
        if repository_id is None:
            return None
        repo = await session.get(Repository, repository_id)
        if repo is None:
            return None
        workspace_id = repo.workspace_id
        revision_sequence: int | None = None
        if repo.canonical_commit:
            rev = await session.execute(
                select(RepositoryRevision)
                .where(
                    RepositoryRevision.repository_id == repository_id,
                    RepositoryRevision.commit_sha == repo.canonical_commit,
                )
                .order_by(RepositoryRevision.sequence.desc())
                .limit(1)
            )
            row = rev.scalar_one_or_none()
            if row:
                revision_sequence = row.sequence
        return {
            "repository_id": str(repository_id),
            "workspace_id": str(workspace_id) if workspace_id else None,
            "canonical_commit": repo.canonical_commit,
            "revision_sequence": revision_sequence,
        }

    async def _commit_exists(
        self,
        session: AsyncSession,
        repository_id: uuid.UUID,
        sha: str | None,
    ) -> bool:
        if sha is None:
            return False
        repo = await session.get(Repository, repository_id)
        if repo is None or repo.workspace_id is None:
            return False
        workspace = await session.get(RepositoryWorkspace, repo.workspace_id)
        if workspace is None or workspace.state.value != "READY":
            return False
        path = self._locator.resolve(workspace.storage_backend, workspace.logical_location)
        return self._git.commit_exists(path, sha)
