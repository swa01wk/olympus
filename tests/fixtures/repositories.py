from __future__ import annotations

import os
import shutil
import subprocess
import tempfile
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

# One git origin per fixture per test process: a copy of the fixture's files, committed with a
# fixed author and date so its SHA is the same on every run. Tests clone, fetch and commit
# against this copy and never touch tests/fixtures/ (writing there once turned the committed
# fixtures into near-empty repos).
_ORIGINS: dict[Path, Path] = {}
_COPY_IGNORE = shutil.ignore_patterns(".git", "__pycache__", ".pytest_cache", "*.pyc")
_FIXED_GIT_ENV = {
    "GIT_AUTHOR_NAME": "t",
    "GIT_AUTHOR_EMAIL": "t@t.com",
    "GIT_COMMITTER_NAME": "t",
    "GIT_COMMITTER_EMAIL": "t@t.com",
    "GIT_AUTHOR_DATE": "2026-01-01T00:00:00+00:00",
    "GIT_COMMITTER_DATE": "2026-01-01T00:00:00+00:00",
}


_FIXTURES_ROOT = Path(__file__).resolve().parent


def fixture_origin(fixture_dir: Path) -> Path:
    """The git origin to clone for ``fixture_dir``.

    A committed fixture (under tests/fixtures/) is copied into a temporary repository once and
    reused. A directory a test made itself (e.g. under tmp_path) is used in place, as before:
    initialised if it is not a repository yet, and its uncommitted changes committed.
    """
    src = fixture_dir.resolve()
    if not src.is_relative_to(_FIXTURES_ROOT):
        _commit_in_place(src)
        return src
    cached = _ORIGINS.get(src)
    if cached is not None and (cached / ".git").is_dir():
        return cached
    if not src.is_dir() or not any(p for p in src.iterdir() if p.name != ".git"):
        raise RuntimeError(f"Test fixture {src} is missing or empty")
    dest = Path(tempfile.mkdtemp(prefix=f"olympus-fixture-{src.name}-"))
    shutil.copytree(src, dest, dirs_exist_ok=True, ignore=_COPY_IGNORE)
    env = {**os.environ, **_FIXED_GIT_ENV}
    for args in (["init", "-q", "-b", "main"], ["add", "-A"], ["commit", "-q", "-m", "fixture"]):
        subprocess.run(["git", *args], cwd=dest, env=env, check=True, capture_output=True)
    _ORIGINS[src] = dest
    return dest


def _commit_in_place(origin: Path) -> None:
    env = {**os.environ, **_FIXED_GIT_ENV}
    if not (origin / ".git" / "HEAD").exists() and not (origin / "HEAD").exists():
        origin.mkdir(parents=True, exist_ok=True)
        (origin / "README.md").write_text("fixture\n", encoding="utf-8")
        for args in (["init", "-q"], ["add", "-A"], ["commit", "-q", "-m", "init"]):
            subprocess.run(["git", *args], cwd=origin, env=env, check=True, capture_output=True)
        return
    if (origin / "HEAD").exists() and not (origin / ".git").exists():
        return  # a bare repository: nothing to commit
    dirty = subprocess.run(
        ["git", "status", "--porcelain"], cwd=origin, capture_output=True, text=True, check=True
    )
    if dirty.stdout.strip():
        for args in (["add", "-A"], ["commit", "-q", "-m", "fixture sync"]):
            subprocess.run(["git", *args], cwd=origin, env=env, check=True, capture_output=True)


async def materialize_existing_repository(
    session: AsyncSession,
    repository_id: uuid.UUID,
    fixture_dir: Path,
    ctx: CommandContext,
) -> str:
    """Clone fixture origin into an already-registered repository workspace."""
    origin = fixture_origin(fixture_dir)
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
    origin = fixture_origin(fixture_dir)
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
