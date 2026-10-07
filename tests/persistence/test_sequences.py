from __future__ import annotations

import asyncio

import pytest
from core.domain.projects.models import Project
from core.domain.sequences import next_project_key
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

pytestmark = pytest.mark.persistence


@pytest.mark.asyncio
async def test_concurrent_sequence_keys(async_engine) -> None:
    factory = async_sessionmaker(bind=async_engine, class_=AsyncSession, expire_on_commit=False)
    async with factory() as session, session.begin():
        project = Project(key="seq-p", name="Seq")
        session.add(project)
        await session.flush()
        project_id = project.id

    async def one_key() -> str:
        async with factory() as session, session.begin():
            return await next_project_key(session, project_id, "task", prefix="T")

    keys = await asyncio.gather(one_key(), one_key(), one_key())
    assert len(set(keys)) == 3
