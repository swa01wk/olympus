"""Deliver released code back into the folder a project was started from.

A release is pushed into the person's own repository as a new branch,
``olympus/<release-key>``. Only that ref is written: the checked-out branch, the working tree
and uncommitted changes in the person's folder are never touched. Delivery is idempotent:
if the branch already points at the released commit, there is nothing to do.
"""

from __future__ import annotations

import asyncio
import re
from dataclasses import dataclass
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.domain.delivery_cycles.models import DeliveryCycle
from core.domain.projects.models import Project
from core.execution.worktrees.git import GitCli, GitCliError


@dataclass(frozen=True)
class Delivery:
    target: Path
    source: Path
    sha: str
    branch: str


def branch_for(release_key: str) -> str:
    slug = re.sub(r"[^a-z0-9._-]+", "-", release_key.lower()).strip("-.") or "release"
    return f"olympus/{slug}"


async def pending_delivery(session: AsyncSession, cycle: DeliveryCycle) -> Delivery | None:
    """What still has to be delivered for this cycle, or None (nothing to do)."""
    from core.release.enums import ReleaseStatus
    from core.release.models import Release
    from core.repositories.workspace_locator import WorkspaceLocator

    project = await session.get(Project, cycle.project_id)
    if project is None or not project.local_path:
        return None
    release = (
        await session.execute(
            select(Release)
            .where(
                Release.delivery_cycle_id == cycle.id,
                Release.status == ReleaseStatus.RELEASED,
            )
            .order_by(Release.created_at.desc())
            .limit(1)
        )
    ).scalar_one_or_none()
    if release is None or not release.integrated_sha:
        return None
    locator = WorkspaceLocator()
    source = locator.resolve("LOCAL_FILESYSTEM", locator.canonical_location(cycle.project_id))
    delivery = Delivery(
        target=Path(project.local_path),
        source=source,
        sha=release.integrated_sha,
        branch=branch_for(release.key),
    )
    if await asyncio.to_thread(_branch_sha, delivery.target, delivery.branch) == delivery.sha:
        return None
    return delivery


async def deliver(delivery: Delivery) -> None:
    await asyncio.to_thread(_push, delivery)


def _branch_sha(target: Path, branch: str) -> str | None:
    if not (target / ".git").exists():
        return None
    result = GitCli().run(
        ["rev-parse", "--verify", "--quiet", f"refs/heads/{branch}"], cwd=target, check=False
    )
    if result.returncode != 0:
        return None
    return result.stdout.strip() or None


def _push(delivery: Delivery) -> None:
    if not (delivery.target / ".git").exists():
        raise GitCliError(f"{delivery.target} is not a git repository")
    # Push from Olympus's copy into the person's repo. Writing a branch that is not checked
    # out is allowed even for a non-bare repository; we never force-update an existing one.
    GitCli().run(
        [
            "push",
            str(delivery.target),
            f"{delivery.sha}:refs/heads/{delivery.branch}",
        ],
        cwd=delivery.source,
    )
