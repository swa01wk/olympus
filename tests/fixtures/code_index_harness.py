from __future__ import annotations

import uuid
from pathlib import Path

from core.commands.context import CommandContext
from core.domain.projects.models import Project
from sqlalchemy.ext.asyncio import AsyncSession
from tests.fixtures.repositories import materialize_fixture_repository

SUPPORTDESK_R1 = Path(__file__).resolve().parent / "repos" / "supportdesk_r1"


async def materialize_supportdesk_r1(
    session: AsyncSession,
    ctx: CommandContext,
) -> tuple:
    from core.domain.repositories.models import Repository

    project = Project(key=f"sd-r1-{uuid.uuid4().hex[:10]}", name="SupportDesk R1")
    session.add(project)
    await session.flush()
    repo, sha = await materialize_fixture_repository(session, project, SUPPORTDESK_R1, ctx)
    refreshed = await session.get(Repository, repo.id)
    assert refreshed is not None
    return refreshed, sha
