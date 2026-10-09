"""Prompt context for ``sentinel.characterize``: ACs, observed behaviour, index, code."""

from __future__ import annotations

from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.domain.delivery_cycles.models import DeliveryCycle
from core.domain.repositories.models import Repository, RepositoryWorkspace
from core.intelligence.brownfield.models import ObservedBehavior
from core.intelligence.code_index.enums import EntityType
from core.intelligence.code_index.models import CodeEntity
from core.intelligence.repository.git_source import GitSourceReader
from core.product_model.models import AcceptanceCriterion, FeatureSpec
from core.repositories.workspace_locator import WorkspaceLocator
from core.traceability.models import RepositoryIndexPointer, SpecCodeLink

_MAX_BEHAVIORS = 40
_MAX_INDEX_LINES = 60
_MAX_FILE_CHARS = 4_000
_MAX_EXCERPT_CHARS = 16_000
_SUMMARY_TYPES = (EntityType.ROUTE, EntityType.ORM_MODEL, EntityType.SCHEMA)


async def build_characterization_snapshot(
    session: AsyncSession,
    cycle: DeliveryCycle,
    spec: FeatureSpec,
    acs: list[AcceptanceCriterion],
) -> dict[str, Any]:
    behaviors = (
        (
            await session.execute(
                select(ObservedBehavior)
                .where(ObservedBehavior.delivery_cycle_id == cycle.id)
                .order_by(ObservedBehavior.key)
            )
        )
        .scalars()
        .all()
    )
    links = (
        (await session.execute(select(SpecCodeLink).where(SpecCodeLink.spec_id == spec.id)))
        .scalars()
        .all()
    )
    linked_keys = {link.code_stable_key for link in links}
    entities = await index_entities(session, cycle)
    linked_files = sorted(
        {e.file_path for e in entities if e.stable_key in linked_keys and e.file_path}
    )
    return {
        "acs": [
            {
                "recovered_ac_key": ac.lineage_key,
                "statement": ac.statement,
                "given": ac.given,
                "when": ac.when,
                "then": ac.then,
            }
            for ac in acs
        ],
        "behaviors": [
            {
                "key": b.key,
                "kind": b.kind.value,
                "description": b.description,
                "passed": b.passed,
            }
            for b in behaviors[:_MAX_BEHAVIORS]
        ],
        "index_summary": index_summary(entities, linked_keys),
        "code_excerpt": await code_excerpt(session, cycle, linked_files),
    }


async def index_entities(session: AsyncSession, cycle: DeliveryCycle) -> list[CodeEntity]:
    if cycle.repository_id is None:
        return []
    pointer = await session.get(RepositoryIndexPointer, cycle.repository_id)
    if pointer is None or pointer.canonical_index_version_id is None:
        return []
    return list(
        (
            await session.execute(
                select(CodeEntity).where(
                    CodeEntity.index_version_id == pointer.canonical_index_version_id
                )
            )
        )
        .scalars()
        .all()
    )


def index_summary(entities: list[CodeEntity], linked_keys: set[str]) -> str:
    lines: list[tuple[int, str]] = []
    for ent in entities:
        if ent.type not in _SUMMARY_TYPES:
            continue
        meta = ent.entity_metadata or {}
        if ent.type == EntityType.ROUTE:
            method = str(meta.get("method") or "GET").upper()
            label = f"ROUTE {method} {meta.get('path') or ent.qualified_name}"
        else:
            label = f"{ent.type.value} {ent.qualified_name}"
        rank = 0 if ent.stable_key in linked_keys else 1
        lines.append((rank, f"{label} ({ent.file_path or '?'})"))
    lines.sort()
    return "\n".join(text for _, text in lines[:_MAX_INDEX_LINES])


async def code_excerpt(session: AsyncSession, cycle: DeliveryCycle, linked_files: list[str]) -> str:
    if cycle.repository_id is None or cycle.base_sha is None:
        return ""
    repo = await session.get(Repository, cycle.repository_id)
    if repo is None or repo.workspace_id is None:
        return ""
    ws = await session.get(RepositoryWorkspace, repo.workspace_id)
    if ws is None:
        return ""
    git_dir = WorkspaceLocator().resolve(ws.storage_backend, ws.logical_location)
    files = GitSourceReader(str(git_dir)).read_text_files_at_commit(cycle.base_sha)
    tests = sorted(p for p in files if _is_test_file(p))
    # One existing test shows import style, client and fixture conventions.
    example_test = next((p for p in tests if "TestClient" in files[p]), tests[0] if tests else None)
    entry = [p for p in files if p.endswith("main.py") and not _is_test_file(p)]
    ordered: list[str] = []
    for path in [*linked_files, *sorted(entry), *([example_test] if example_test else [])]:
        if path in files and path not in ordered:
            ordered.append(path)
    chunks: list[str] = []
    total = 0
    for path in ordered:
        body = files[path][:_MAX_FILE_CHARS]
        chunk = f"# --- {path} ---\n{body}"
        if total + len(chunk) > _MAX_EXCERPT_CHARS:
            break
        chunks.append(chunk)
        total += len(chunk)
    return "\n\n".join(chunks)


def _is_test_file(path: str) -> bool:
    name = path.rsplit("/", 1)[-1]
    return (path.startswith("tests/") or "/tests/" in path) and name.startswith("test_")
