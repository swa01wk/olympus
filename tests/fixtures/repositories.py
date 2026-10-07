from __future__ import annotations

import subprocess
import uuid
from pathlib import Path

from core.commands.context import CommandContext
from core.domain.actors.models import Actor
from core.domain.enums import ActorKind, ActorRole, RepositoryProvider
from core.domain.projects.models import Project
from core.domain.repositories.models import Repository, RepositoryWorkspace
from core.repositories.service import RepositoryService
from core.repositories.workspace_locator import WorkspaceLocator
from sqlalchemy.ext.asyncio import AsyncSession


async def materialize_existing_repository(
    session: AsyncSession,
    repository_id: uuid.UUID,
    fixture_dir: Path,
    ctx: CommandContext,
) -> str:
    """Clone fixture origin into an already-registered repository workspace."""
    origin = fixture_dir.resolve()
    if not (origin / ".git" / "HEAD").exists() and not (origin / "HEAD").exists():
        (origin / "README.md").write_text("fixture\n", encoding="utf-8")
        subprocess.run(["git", "init"], cwd=origin, check=True, capture_output=True)
        subprocess.run(["git", "add", "-A"], cwd=origin, check=True, capture_output=True)
        subprocess.run(
            ["git", "-c", "user.email=t@t.com", "-c", "user.name=t", "commit", "-m", "init"],
            cwd=origin,
            check=True,
            capture_output=True,
        )
    head = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=origin,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    repo = await session.get(Repository, repository_id)
    if repo is None:
        raise RuntimeError("repository missing")
    workspace = await session.get(RepositoryWorkspace, repo.workspace_id)
    if workspace is None:
        raise RuntimeError("workspace missing")
    locator = WorkspaceLocator()
    dest = locator.resolve(workspace.storage_backend, workspace.logical_location)
    dest.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(
        ["git", "clone", "--bare", f"file://{origin}", str(dest)],
        check=True,
        capture_output=True,
    )
    await RepositoryService().record_materialization(session, repository_id, head, "main", ctx)
    return head


async def materialize_fixture_repository(
    session: AsyncSession,
    project: Project,
    fixture_dir: Path,
    ctx: CommandContext | None = None,
) -> tuple[Repository, str]:
    origin = fixture_dir.resolve()
    if not (origin / ".git" / "HEAD").exists() and not (origin / "HEAD").exists():
        (origin / "README.md").write_text("fixture\n", encoding="utf-8")
        subprocess.run(["git", "init"], cwd=origin, check=True, capture_output=True)
        subprocess.run(["git", "add", "-A"], cwd=origin, check=True, capture_output=True)
        subprocess.run(
            ["git", "-c", "user.email=t@t.com", "-c", "user.name=t", "commit", "-m", "init"],
            cwd=origin,
            check=True,
            capture_output=True,
        )
    else:
        dirty = subprocess.run(
            ["git", "status", "--porcelain"],
            cwd=origin,
            capture_output=True,
            text=True,
            check=True,
        )
        if dirty.stdout.strip():
            subprocess.run(["git", "add", "-A"], cwd=origin, check=True, capture_output=True)
            subprocess.run(
                [
                    "git",
                    "-c",
                    "user.email=t@t.com",
                    "-c",
                    "user.name=t",
                    "commit",
                    "-m",
                    "fixture sync",
                ],
                cwd=origin,
                check=True,
                capture_output=True,
            )
    head = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=origin,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    if ctx is None:
        actor = Actor(kind=ActorKind.SYSTEM, name="test-system", roles=[ActorRole.SYSTEM.value])
        session.add(actor)
        await session.flush()
        ctx = CommandContext(actor=actor, correlation_id="test")
    from core.bootstrap.connectors import ensure_connectors_registered
    from core.repositories.materialization import RepositoryMaterializationService

    ensure_connectors_registered()
    svc = RepositoryService()
    repo = await svc.register_external(
        session,
        project.id,
        "fixture",
        RepositoryProvider.LOCAL,
        f"file://{origin}",
        "main",
        "none:",
        ctx,
    )
    await RepositoryMaterializationService().materialize_external(session, repo.id, ctx)
    refreshed = await session.get(Repository, repo.id)
    assert refreshed is not None
    return refreshed, head
