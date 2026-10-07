from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from core.domain.projects.models import ProjectSequence


async def next_project_key(
    session: AsyncSession,
    project_id: uuid.UUID,
    sequence_name: str,
    *,
    prefix: str,
) -> str:
    for _ in range(8):
        result = await session.execute(
            select(ProjectSequence)
            .where(
                ProjectSequence.project_id == project_id,
                ProjectSequence.sequence_name == sequence_name,
            )
            .with_for_update()
        )
        row = result.scalar_one_or_none()
        if row is None:
            try:
                async with session.begin_nested():
                    session.add(
                        ProjectSequence(
                            project_id=project_id,
                            sequence_name=sequence_name,
                            next_value=1,
                        )
                    )
                    await session.flush()
            except IntegrityError:
                continue
            result = await session.execute(
                select(ProjectSequence)
                .where(
                    ProjectSequence.project_id == project_id,
                    ProjectSequence.sequence_name == sequence_name,
                )
                .with_for_update()
            )
            row = result.scalar_one()
        value = row.next_value
        row.next_value = value + 1
        return f"{prefix}-{value:04d}"
    raise RuntimeError("failed to allocate project sequence key")
