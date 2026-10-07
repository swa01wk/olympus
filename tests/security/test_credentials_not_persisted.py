from __future__ import annotations

import json
import os
import subprocess
import uuid
from pathlib import Path

import pytest
from core.commands.context import CommandContext
from core.domain.actors.models import Actor
from core.domain.enums import ActorKind, ActorRole, RepositoryProvider
from core.domain.projects.models import Project
from core.repositories.materialization import RepositoryMaterializationService
from core.repositories.service import RepositoryService
from core.repositories.workspace_locator import WorkspaceLocator
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

pytestmark = pytest.mark.security


@pytest.mark.asyncio
async def test_credential_secret_not_in_db_or_git_config(
    async_engine,
    postgres_url: str,
    tmp_path: Path,
) -> None:
    token = f"test-git-credential-{uuid.uuid4().hex}"
    os.environ["TEST_GIT_TOKEN"] = token
    origin = tmp_path / "origin"
    origin.mkdir()
    (origin / "README.md").write_text("origin\n", encoding="utf-8")
    subprocess.run(["git", "init", "-b", "main"], cwd=origin, check=True, capture_output=True)
    subprocess.run(["git", "add", "-A"], cwd=origin, check=True, capture_output=True)
    subprocess.run(
        ["git", "-c", "user.email=t@t.com", "-c", "user.name=t", "commit", "-m", "init"],
        cwd=origin,
        check=True,
        capture_output=True,
    )

    factory = async_sessionmaker(bind=async_engine, class_=AsyncSession, expire_on_commit=False)
    repo_id: uuid.UUID
    async with factory() as session, session.begin():
        actor = Actor(kind=ActorKind.SYSTEM, name="cred-sys", roles=[ActorRole.SYSTEM.value])
        session.add(actor)
        await session.flush()
        ctx = CommandContext(actor=actor, correlation_id="cred")
        project = Project(key="cred-sec", name="Cred")
        session.add(project)
        await session.flush()
        repo = await RepositoryService().register_external(
            session,
            project.id,
            "cred",
            RepositoryProvider.LOCAL,
            f"file://{origin.resolve()}",
            "main",
            "env:TEST_GIT_TOKEN",
            ctx,
        )
        await RepositoryMaterializationService().materialize_external(session, repo.id, ctx)
        repo_id = repo.id

    sync_url = postgres_url.replace("postgresql+psycopg://", "postgresql://")
    try:
        dump = subprocess.run(
            ["pg_dump", sync_url, "--data-only"],
            check=True,
            capture_output=True,
            text=True,
        ).stdout
        assert token not in dump
    except (FileNotFoundError, subprocess.CalledProcessError):
        async with factory() as session:
            rows = await session.execute(
                text(
                    "SELECT tablename FROM pg_tables "
                    "WHERE schemaname = 'public' AND tablename NOT LIKE 'alembic%'"
                )
            )
            for (table,) in rows:
                content = await session.execute(text(f'SELECT row_to_json(t) FROM "{table}" t'))
                blob = json.dumps([r[0] for r in content.fetchall()], default=str)
                assert token not in blob

    async with factory() as session:
        view = await RepositoryService().get_view(session, repo_id)
    assert view.workspace is not None
    git_dir = WorkspaceLocator().resolve("LOCAL_FILESYSTEM", view.workspace.logical_location)
    config_path = git_dir / "config"
    if config_path.exists():
        assert token not in config_path.read_text(encoding="utf-8")
