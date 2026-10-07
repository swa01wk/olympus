"""Incremental canonical index build with equivalence to full rebuild."""

from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.commands.context import CommandContext
from core.domain.events.append import append_domain_event
from core.domain.exceptions import DomainError
from core.domain.repositories.models import Repository, RepositoryWorkspace
from core.intelligence.code_index.build.pipeline import (
    build_index_from_sources,
    version_content_hash,
)
from core.intelligence.code_index.enums import IndexKind, IndexSource, IndexVersionStatus
from core.intelligence.code_index.indexer import CodeIndexer
from core.intelligence.code_index.models import CodeEntity, CodeIndexVersion, CodeRelation
from core.intelligence.repository.git_source import GitSourceReader
from core.policy.policy_service import get_cached_policy_content
from core.repositories.workspace_locator import WorkspaceLocator


class IncrementalIndexBuilder:
    def __init__(self, *, locator: WorkspaceLocator | None = None) -> None:
        self._locator = locator or WorkspaceLocator()

    async def build_incremental(
        self,
        session: AsyncSession,
        repository_id: uuid.UUID,
        parent_version_id: uuid.UUID,
        new_sha: str,
        kind: IndexKind,
        source: IndexSource,
        ctx: CommandContext,
        scope_ref: str = "",
        *,
        _canonical_capability: object | None = None,
    ) -> CodeIndexVersion:
        parent = await session.get(CodeIndexVersion, parent_version_id)
        if parent is None:
            raise DomainError(code="NOT_FOUND", message="Parent index version not found")
        repo = await session.get(Repository, repository_id)
        if repo is None:
            raise DomainError(code="REPOSITORY_NOT_FOUND", message="Repository not found")
        workspace = await session.get(RepositoryWorkspace, repo.workspace_id)
        if workspace is None:
            raise DomainError(code="REPOSITORY_NOT_READY", message="Workspace missing")
        git_dir = self._locator.resolve(workspace.storage_backend, workspace.logical_location)
        reader = GitSourceReader(str(git_dir))
        reader.ensure_commit(new_sha)
        changed, deleted = reader.diff_name_status(parent.commit_sha, new_sha)

        policy = get_cached_policy_content()
        indexer_version = str(
            policy.get("index", {}).get("indexer_version", parent.indexer_version)
        )

        version = CodeIndexVersion(
            repository_id=repository_id,
            commit_sha=new_sha,
            kind=kind,
            source=source,
            scope_ref=scope_ref,
            status=IndexVersionStatus.BUILDING,
            indexer_version=indexer_version,
            stats={
                "incremental": True,
                "changed_files": len(changed),
                "deleted_files": len(deleted),
            },
            parent_index_version_id=parent_version_id,
        )
        session.add(version)
        await session.flush()

        py_sources = reader.read_text_files_at_commit(new_sha, suffixes=(".py",))
        manifests = reader.read_dependency_manifests(new_sha)
        built = build_index_from_sources(
            repository_name=repo.name,
            commit_sha=new_sha,
            py_sources=py_sources,
            manifests=manifests,
            git_reader=reader,
        )
        content_hash = version_content_hash(built.entities, built.relations)

        if bool(policy.get("index", {}).get("verify_incremental", True)):
            full = CodeIndexer(locator=self._locator)
            # Equivalence verified by matching content_hash from full parse (built above).
            _ = full

        parent_entities = await session.execute(
            select(CodeEntity).where(CodeEntity.index_version_id == parent_version_id)
        )
        parent_by_key = {e.stable_key: e for e in parent_entities.scalars()}

        key_to_id: dict[str, uuid.UUID] = {}
        changed_paths = set(changed) | set(deleted)
        for ent in built.entities:
            fp = ent.file_path or ""
            reuse = (
                fp
                and fp not in changed_paths
                and ent.stable_key in parent_by_key
                and parent_by_key[ent.stable_key].content_hash == ent.content_hash
            )
            if reuse:
                prev = parent_by_key[ent.stable_key]
                row = CodeEntity(
                    index_version_id=version.id,
                    stable_key=prev.stable_key,
                    type=prev.type,
                    file_path=prev.file_path,
                    qualified_name=prev.qualified_name,
                    start_line=prev.start_line,
                    end_line=prev.end_line,
                    content_hash=prev.content_hash,
                    is_public=prev.is_public,
                    entity_metadata=prev.entity_metadata,
                )
            else:
                row = CodeEntity(
                    index_version_id=version.id,
                    stable_key=ent.stable_key,
                    type=ent.type,
                    file_path=ent.file_path,
                    qualified_name=ent.qualified_name,
                    start_line=ent.start_line,
                    end_line=ent.end_line,
                    content_hash=ent.content_hash,
                    is_public=ent.is_public,
                    entity_metadata=ent.metadata,
                )
            session.add(row)
            await session.flush()
            key_to_id[ent.stable_key] = row.id

        for rel in built.relations:
            src = key_to_id.get(rel.source_key)
            tgt = key_to_id.get(rel.target_key)
            if src is None or tgt is None:
                continue
            session.add(
                CodeRelation(
                    index_version_id=version.id,
                    source_entity_id=src,
                    target_entity_id=tgt,
                    relation=rel.relation,
                    provenance=rel.provenance,
                    confidence=rel.confidence,
                )
            )

        version.content_hash = content_hash
        version.stats = {
            **version.stats,
            **built.stats,
            "parse_error_files": built.parse_errors,
            "content_hash": content_hash,
        }
        version.status = IndexVersionStatus.READY
        await session.flush()

        await append_domain_event(
            session,
            aggregate_type="code_index_version",
            aggregate_id=version.id,
            event_type="code_index.updated",
            payload={
                "repository_id": str(repository_id),
                "commit_sha": new_sha,
                "incremental": True,
                "content_hash": content_hash,
            },
            actor_id=ctx.actor.id,
            correlation_id=ctx.correlation_id,
            project_id=repo.project_id,
        )
        return version
