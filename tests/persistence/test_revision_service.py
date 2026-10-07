from __future__ import annotations

import asyncio
import uuid

import pytest
from core.commands.context import CommandContext
from core.domain.enums import RevisionCause
from core.domain.exceptions import DomainError, StateConflict
from core.domain.repositories.models import RepositoryRevision
from core.repositories.revision import RepositoryRevisionService, RevisionRefs
from core.repositories.service import RepositoryService
from sqlalchemy import func, select

pytestmark = pytest.mark.persistence


async def _materialized_repo(db_session, sample_project, system_ctx):
    repo = await RepositoryService().declare_managed(db_session, sample_project.id, system_ctx)
    sha = "a" * 40
    await RepositoryService().record_materialization(db_session, repo.id, sha, "main", system_ctx)
    await db_session.refresh(repo)
    return repo, sha


@pytest.mark.asyncio
async def test_advance_stale_expected_current(db_session, sample_project, system_ctx) -> None:
    repo, sha = await _materialized_repo(db_session, sample_project, system_ctx)
    svc = RepositoryRevisionService()
    new_sha = "b" * 40
    with pytest.raises(StateConflict):
        await svc.advance(
            db_session,
            repo.id,
            new_sha,
            RevisionCause.INTEGRATION_READY,
            RevisionRefs(),
            expected_current="wrong",
            ctx=system_ctx,
        )


@pytest.mark.asyncio
async def test_mark_released_requires_canonical(db_session, sample_project, system_ctx) -> None:
    repo, sha = await _materialized_repo(db_session, sample_project, system_ctx)
    svc = RepositoryRevisionService()
    with pytest.raises(DomainError):
        await svc.mark_released(db_session, repo.id, "c" * 40, uuid.uuid4(), system_ctx)


@pytest.mark.asyncio
async def test_sequence_gap_free(db_session, sample_project, system_ctx) -> None:
    repo, sha = await _materialized_repo(db_session, sample_project, system_ctx)
    svc = RepositoryRevisionService()
    await svc.advance(
        db_session,
        repo.id,
        sha,
        RevisionCause.INTEGRATION_READY,
        RevisionRefs(),
        expected_current=sha,
        ctx=system_ctx,
    )
    count = await db_session.scalar(
        select(func.count())
        .select_from(RepositoryRevision)
        .where(RepositoryRevision.repository_id == repo.id)
    )
    assert count == 2


@pytest.mark.asyncio
async def test_concurrent_advance_one_wins(async_engine) -> None:
    from core.domain.actors.models import Actor
    from core.domain.enums import ActorKind, ActorRole
    from core.domain.projects.models import Project
    from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

    factory = async_sessionmaker(bind=async_engine, class_=AsyncSession, expire_on_commit=False)
    async with factory() as setup, setup.begin():
        actor = Actor(kind=ActorKind.SYSTEM, name="adv", roles=[ActorRole.SYSTEM.value])
        setup.add(actor)
        project = Project(key="adv-p", name="Adv")
        setup.add(project)
        await setup.flush()
        ctx = CommandContext(actor=actor, correlation_id="adv-setup")
        repo = await RepositoryService().declare_managed(setup, project.id, ctx)
        sha = "d" * 40
        await RepositoryService().record_materialization(setup, repo.id, sha, "main", ctx)
        repo_id = repo.id
        actor_id = actor.id

    new_a = "e" * 40
    new_b = "f" * 40

    async def attempt(to_sha: str) -> str:
        async with factory() as session, session.begin():
            actor_row = await session.get(Actor, actor_id)
            assert actor_row is not None
            ctx = CommandContext(actor=actor_row, correlation_id="adv")
            svc = RepositoryRevisionService()
            try:
                await svc.advance(
                    session,
                    repo_id,
                    to_sha,
                    RevisionCause.INTEGRATION_READY,
                    RevisionRefs(),
                    expected_current=sha,
                    ctx=ctx,
                )
                return "ok"
            except StateConflict:
                return "conflict"

    results = await asyncio.gather(attempt(new_a), attempt(new_b))
    assert results.count("ok") == 1
    assert results.count("conflict") == 1
