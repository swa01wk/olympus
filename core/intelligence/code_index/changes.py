"""Diff candidate vs base index into code_entity_changes."""

from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.integration.enums import EntityChangeKind
from core.intelligence.code_index.models import CodeEntity
from core.traceability.models import CodeEntityChange


def diff_stable_keys(
    base_map: dict[str, str | None],
    cand_map: dict[str, str | None],
) -> dict[str, EntityChangeKind]:
    kinds: dict[str, EntityChangeKind] = {}
    for sk, ch in cand_map.items():
        if sk not in base_map:
            kinds[sk] = EntityChangeKind.ADDED
        elif base_map[sk] != ch:
            kinds[sk] = EntityChangeKind.MODIFIED
    for sk in base_map:
        if sk not in cand_map:
            kinds[sk] = EntityChangeKind.DELETED
    return kinds


async def compute_entity_changes(
    session: AsyncSession,
    *,
    repository_id: uuid.UUID,
    base_version_id: uuid.UUID,
    candidate_version_id: uuid.UUID,
    execution_id: uuid.UUID,
    task_id: uuid.UUID,
    candidate_commit_sha: str,
    integration_candidate_id: uuid.UUID,
    integrated_sha: str,
) -> list[CodeEntityChange]:
    base_rows = await session.execute(
        select(CodeEntity.stable_key, CodeEntity.content_hash).where(
            CodeEntity.index_version_id == base_version_id
        )
    )
    base_map = {sk: ch for sk, ch in base_rows.all()}
    cand_rows = await session.execute(
        select(CodeEntity.stable_key, CodeEntity.content_hash).where(
            CodeEntity.index_version_id == candidate_version_id
        )
    )
    cand_map = {sk: ch for sk, ch in cand_rows.all()}
    kinds = diff_stable_keys(base_map, cand_map)
    changes: list[CodeEntityChange] = []
    for sk, kind in kinds.items():
        changes.append(
            CodeEntityChange(
                repository_id=repository_id,
                stable_key=sk,
                change_kind=kind,
                execution_id=execution_id,
                task_id=task_id,
                candidate_commit_sha=candidate_commit_sha,
                integration_candidate_id=integration_candidate_id,
                integrated_sha=integrated_sha,
            )
        )
    for row in changes:
        session.add(row)
    await session.flush()
    return changes


async def load_index_entity_map(
    session: AsyncSession, version_id: uuid.UUID
) -> dict[str, CodeEntity]:
    rows = await session.execute(
        select(CodeEntity).where(CodeEntity.index_version_id == version_id)
    )
    return {e.stable_key: e for e in rows.scalars()}
