from __future__ import annotations

import uuid

import pytest
from core.commands.context import CommandContext
from core.domain.actors.models import Actor
from core.domain.enums import (
    ActorKind,
    ActorRole,
    RepositoryProvider,
    RepositorySourceType,
    RepositoryStatus,
)
from core.domain.projects.models import Project
from core.domain.repositories.models import Repository, RepositoryWorkspace
from core.repositories.service import RepositoryService
from sqlalchemy import text

pytestmark = pytest.mark.persistence


@pytest.mark.asyncio
async def test_canonical_commit_update_without_revision_rejected(db_session) -> None:
    actor = Actor(kind=ActorKind.SYSTEM, name="rev", roles=[ActorRole.SYSTEM.value])
    project = Project(key="rev-p", name="Rev")
    db_session.add(actor)
    db_session.add(project)
    await db_session.flush()
    ctx = CommandContext(actor=actor, correlation_id="r")
    repo = await RepositoryService().register_external(
        db_session,
        project.id,
        "ext",
        RepositoryProvider.LOCAL,
        "file:///tmp/x",
        "main",
        "none:",
        ctx,
    )
    with pytest.raises(Exception, match="revision|canonical"):
        await db_session.execute(
            text(
                "UPDATE repositories SET canonical_commit = 'abc', status = 'READY' WHERE id = :id"
            ),
            {"id": repo.id},
        )
        await db_session.flush()


@pytest.mark.asyncio
async def test_repository_revisions_immutable(db_session, system_actor) -> None:
    project = Project(key="rev2", name="R2")
    db_session.add(project)
    await db_session.flush()
    repo = Repository(
        project_id=project.id,
        name="r",
        source_type=RepositorySourceType.GREENFIELD_MANAGED,
        provider=RepositoryProvider.LOCAL,
        status=RepositoryStatus.PROVISIONING,
    )
    db_session.add(repo)
    await db_session.flush()
    await db_session.execute(
        text(
            """
            INSERT INTO repository_revisions
            (id, repository_id, sequence, commit_sha, cause, actor_id, correlation_id)
            VALUES (:id, :rid, 1, 'sha', 'MATERIALIZED', :aid, 'c')
            """
        ),
        {"id": uuid.uuid4(), "rid": repo.id, "aid": system_actor.id},
    )
    await db_session.flush()
    with pytest.raises(Exception, match="mutation forbidden|forbidden"):
        await db_session.execute(
            text("DELETE FROM repository_revisions WHERE repository_id = :id"),
            {"id": repo.id},
        )
        await db_session.flush()


@pytest.mark.asyncio
async def test_one_repository_per_project(db_session, system_ctx, sample_project) -> None:
    from core.domain.exceptions import DomainError

    await RepositoryService().declare_managed(db_session, sample_project.id, system_ctx)
    with pytest.raises(DomainError):
        await RepositoryService().declare_managed(db_session, sample_project.id, system_ctx)


@pytest.mark.asyncio
async def test_logical_location_check(db_session) -> None:
    project = Project(key="rev3", name="R3")
    db_session.add(project)
    await db_session.flush()
    repo = Repository(
        project_id=project.id,
        name="r",
        source_type=RepositorySourceType.GREENFIELD_MANAGED,
        provider=RepositoryProvider.LOCAL,
        status=RepositoryStatus.PROVISIONING,
    )
    db_session.add(repo)
    await db_session.flush()
    ws = RepositoryWorkspace(
        repository_id=repo.id,
        logical_location="/absolute/path",
    )
    db_session.add(ws)
    with pytest.raises(Exception, match="logical_location|check|violat"):
        await db_session.flush()
