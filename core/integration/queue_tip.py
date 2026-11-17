"""Merge-queue base resolution (QUEUE_TIP).

A task with this policy starts from all the code finished so far in its cycle: the cycle base
plus the latest candidate commit of every completed code task. The tip is resolved when the
task's execution starts (the snapshot is built then), so tasks that run one after another each
build on the previous ones. Their commits then form a chain, and merging the chain at
integration time is conflict-free: the integration merge skips any commit a later one already
contains.
"""

from __future__ import annotations

import hashlib
import uuid
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.domain.candidate_commits.models import CandidateCommit
from core.domain.delivery_cycles.models import DeliveryCycle
from core.domain.enums import TaskOrigin, TaskStatus, WorkType
from core.domain.tasks.models import Task
from core.execution.snapshots.base_commit import BaseResolution
from core.execution.worktrees.git import GitCli
from core.integrations.connectors.base import ConnectorAction
from core.integrations.connectors.git_local import GitLocalConnector
from core.repositories.workspace_locator import WorkspaceLocator

QUEUE_ORIGINS = (TaskOrigin.IMPLEMENTATION_PLAN, TaskOrigin.REMEDIATION, TaskOrigin.REPAIR)


class QueueTipResolver:
    def __init__(
        self,
        *,
        git: GitCli | None = None,
        connector: GitLocalConnector | None = None,
        workspace_locator: WorkspaceLocator | None = None,
    ) -> None:
        self._git = git or GitCli()
        self._connector = connector or GitLocalConnector()
        self._locator = workspace_locator or WorkspaceLocator()

    async def resolve(
        self, session: AsyncSession, task: Task, repository_id: uuid.UUID
    ) -> BaseResolution:
        from core.domain.repositories.models import Repository, RepositoryWorkspace

        cycle = await session.get(DeliveryCycle, task.delivery_cycle_id)
        if cycle is None:
            raise ValueError("cycle missing")
        repo = await session.get(Repository, repository_id)
        ws = await session.get(RepositoryWorkspace, repo.workspace_id) if repo else None
        if cycle.base_sha is None or ws is None:
            # Like CYCLE_BASE: no base yet is "not available" (the scheduler waits), not an error.
            return BaseResolution(
                policy="QUEUE_TIP",
                base_commit=cycle.base_sha,
                commit_available=False,
                inputs={"policy": "QUEUE_TIP", "cycle_base": cycle.base_sha, "heads": []},
                repository={"repository_id": str(repository_id)},
            )
        git_dir = self._locator.resolve(ws.storage_backend, ws.logical_location)
        base = cycle.base_sha
        repo_block: dict[str, object] = {"repository_id": str(repository_id)}

        finished = await self._finished_commits(session, cycle.id, exclude_task_id=task.id)
        heads = self._independent_heads(git_dir, base, finished)
        if not heads:
            return self._resolution(base, base, [], [], repo_block)
        if len(heads) == 1:
            return self._resolution(base, heads[0], heads, [], repo_block)

        # Several lines of work that do not contain each other (e.g. tasks that ran before the
        # queue existed): merge them. The branch name is derived from the inputs, so a resolved
        # tip is reused instead of merged again on every scheduler tick.
        digest = hashlib.sha256(" ".join([base, *heads]).encode()).hexdigest()[:16]
        branch = f"olympus/queue/{digest}"
        cached = self._git.run(
            ["rev-parse", "--verify", "--quiet", branch], git_dir=git_dir, check=False
        )
        if cached.returncode == 0 and cached.stdout.strip():
            skipped = self._skipped_from_cache(git_dir, cached.stdout.strip(), heads)
            return self._resolution(base, cached.stdout.strip(), heads, skipped, repo_block)
        tip, skipped = self._merge_greedily(ws.logical_location, heads, branch)
        return self._resolution(base, tip, heads, skipped, repo_block)

    async def _finished_commits(
        self, session: AsyncSession, cycle_id: uuid.UUID, *, exclude_task_id: uuid.UUID
    ) -> list[str]:
        """Latest candidate commit of each completed code task, oldest first."""
        tasks = (
            await session.execute(
                select(Task.id).where(
                    Task.delivery_cycle_id == cycle_id,
                    Task.work_type == WorkType.CODE_CHANGE,
                    Task.origin.in_(QUEUE_ORIGINS),
                    Task.status == TaskStatus.COMPLETED,
                    Task.id != exclude_task_id,
                )
            )
        ).scalars()
        latest: list[tuple[object, str]] = []
        for task_id in tasks:
            commit = (
                await session.execute(
                    select(CandidateCommit)
                    .where(CandidateCommit.task_id == task_id)
                    .order_by(CandidateCommit.created_at.desc())
                    .limit(1)
                )
            ).scalar_one_or_none()
            if commit is not None:
                latest.append((commit.created_at, commit.sha))
        latest.sort(key=lambda pair: pair[0])  # type: ignore[arg-type,return-value]
        return [sha for _, sha in latest]

    def _independent_heads(self, git_dir: Path, base: str, shas: list[str]) -> list[str]:
        """The commits no other commit (or the base) contains, in completion order."""
        unique = list(dict.fromkeys(shas))
        if not unique:
            return []
        result = self._git.run(
            ["merge-base", "--independent", base, *unique], git_dir=git_dir, check=False
        )
        if result.returncode != 0:
            raise ValueError("BASE_COMMIT_UNAVAILABLE")
        independent = set(result.stdout.split())
        return [sha for sha in unique if sha in independent]

    def _merge_greedily(
        self, logical_location: str, heads: list[str], branch: str
    ) -> tuple[str, list[str]]:
        """Merge the heads one by one, skipping any that conflicts. A skipped head is still
        merged at integration time, where a conflict gets its own fix task."""
        tip = heads[0]
        skipped: list[str] = []
        for sha in heads[1:]:
            result = self._connector._action_merge_candidates(
                ConnectorAction(
                    connector="git_local",
                    action="merge_candidates",
                    target_resource=logical_location,
                    inputs={
                        "logical_location": logical_location,
                        "base_sha": tip,
                        "candidate_shas": [sha],
                        "branch": branch,
                    },
                    idempotency_key=f"{branch}-{sha}",
                    correlation_id=branch,
                    expected_result_schema="MergeCandidatesResult",
                )
            )
            if result.status == "SUCCEEDED" and result.normalized_result:
                tip = str(result.normalized_result["integrated_sha"])
            else:
                skipped.append(sha)
        if skipped:
            # Leave the branch on the best tip so the cache lookup returns it.
            git_dir = self._connector._git_dir(logical_location)
            self._git.run(["branch", "-f", branch, tip], git_dir=git_dir, check=True)
        return tip, skipped

    def _skipped_from_cache(self, git_dir: Path, tip: str, heads: list[str]) -> list[str]:
        return [
            sha
            for sha in heads
            if self._git.run(
                ["merge-base", "--is-ancestor", sha, tip], git_dir=git_dir, check=False
            ).returncode
            != 0
        ]

    @staticmethod
    def _resolution(
        base: str,
        tip: str,
        heads: list[str],
        skipped: list[str],
        repo_block: dict[str, object],
    ) -> BaseResolution:
        inputs: dict[str, object] = {"policy": "QUEUE_TIP", "cycle_base": base, "heads": heads}
        if skipped:
            inputs["skipped"] = skipped
        return BaseResolution(
            policy="QUEUE_TIP",
            base_commit=tip,
            commit_available=True,
            inputs=inputs,
            repository=repo_block,
        )
