from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.commands.context import CommandContext
from core.domain.enums import RepositoryStatus
from core.domain.events.append import append_domain_event
from core.domain.exceptions import DomainError
from core.domain.repositories.models import Repository, RepositoryWorkspace
from core.intelligence.code_index.build.pipeline import (
    build_index_from_sources,
    version_content_hash,
)
from core.intelligence.code_index.canonical import CANONICAL_INDEX_BUILD_CAPABILITY
from core.intelligence.code_index.enums import IndexKind, IndexSource, IndexVersionStatus
from core.intelligence.code_index.models import (
    INDEXER_VERSION,
    CodeEntity,
    CodeIndexVersion,
    CodeRelation,
)
from core.intelligence.repository.git_source import GitSourceReader
from core.policy.policy_service import get_cached_policy_content
from core.repositories.workspace_locator import WorkspaceLocator


class CodeIndexer:
    def __init__(
        self,
        *,
        locator: WorkspaceLocator | None = None,
    ) -> None:
        self._locator = locator or WorkspaceLocator()

    async def build(
        self,
        session: AsyncSession,
        repository_id: uuid.UUID,
        sha: str,
        kind: IndexKind,
        source: IndexSource,
        ctx: CommandContext,
        scope_ref: str = "",
        *,
        parent_index_version_id: uuid.UUID | None = None,
        _canonical_capability: object | None = None,
    ) -> CodeIndexVersion:
        canonical_reserved = (
            kind == IndexKind.CANONICAL
            and _canonical_capability is not CANONICAL_INDEX_BUILD_CAPABILITY
        )
        if canonical_reserved:
            raise DomainError(
                code="CANONICAL_INDEX_RESERVED",
                message="CANONICAL index versions may only be built by CanonicalIndexService",
            )

        policy = get_cached_policy_content()
        indexer_version = str(policy.get("index", {}).get("indexer_version", INDEXER_VERSION))
        max_error_ratio = float(policy.get("index", {}).get("max_parse_error_ratio", 0.5))

        repo = await session.get(Repository, repository_id)
        if repo is None:
            raise DomainError(code="REPOSITORY_NOT_FOUND", message="Repository not found")
        building_ic_promotion = (
            kind == IndexKind.CANONICAL
            and _canonical_capability is CANONICAL_INDEX_BUILD_CAPABILITY
        )
        if (
            kind == IndexKind.CANONICAL
            and repo.canonical_commit
            and sha != repo.canonical_commit
            and not building_ic_promotion
        ):
            raise DomainError(
                code="CANONICAL_INDEX_RESERVED",
                message="CANONICAL index sha must match repository.canonical_commit",
            )

        existing = await session.execute(
            select(CodeIndexVersion).where(
                CodeIndexVersion.repository_id == repository_id,
                CodeIndexVersion.commit_sha == sha,
                CodeIndexVersion.kind == kind,
                CodeIndexVersion.scope_ref == scope_ref,
                CodeIndexVersion.indexer_version == indexer_version,
                CodeIndexVersion.status == IndexVersionStatus.READY,
            )
        )
        ready = existing.scalar_one_or_none()
        if ready is not None:
            return ready

        workspace = await session.get(RepositoryWorkspace, repo.workspace_id)
        if workspace is None:
            raise DomainError(code="REPOSITORY_NOT_READY", message="Workspace missing")
        if repo.status not in {RepositoryStatus.READY, RepositoryStatus.SYNCING}:
            raise DomainError(
                code="REPOSITORY_NOT_READY",
                message=f"Repository status is {repo.status.value}",
            )

        git_dir = self._locator.resolve(workspace.storage_backend, workspace.logical_location)
        reader = GitSourceReader(str(git_dir))
        reader.ensure_commit(sha)

        version = CodeIndexVersion(
            repository_id=repository_id,
            commit_sha=sha,
            kind=kind,
            source=source,
            scope_ref=scope_ref,
            status=IndexVersionStatus.BUILDING,
            indexer_version=indexer_version,
            stats={},
            parent_index_version_id=parent_index_version_id,
        )
        session.add(version)
        await session.flush()

        await append_domain_event(
            session,
            aggregate_type="code_index_version",
            aggregate_id=version.id,
            event_type="code_index.build_started",
            payload={
                "repository_id": str(repository_id),
                "commit_sha": sha,
                "kind": kind.value,
            },
            actor_id=ctx.actor.id,
            correlation_id=ctx.correlation_id,
            project_id=repo.project_id,
        )

        try:
            py_sources = reader.read_text_files_at_commit(sha, suffixes=(".py",))
            manifests = reader.read_dependency_manifests(sha)
            built = build_index_from_sources(
                repository_name=repo.name,
                commit_sha=sha,
                py_sources=py_sources,
                manifests=manifests,
                git_reader=reader,
            )
            file_count = len(py_sources) or 1
            if len(built.parse_errors) / file_count > max_error_ratio:
                raise DomainError(
                    code="INDEX_PARSE_FAILED",
                    message="Too many parse errors during indexing",
                    details={"parse_errors": built.parse_errors},
                )

            content_hash = version_content_hash(built.entities, built.relations)
            key_to_id: dict[str, uuid.UUID] = {}
            for ent in built.entities:
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
            version.stats = {**built.stats, "parse_error_files": built.parse_errors}
            version.status = IndexVersionStatus.READY
            await session.flush()

            await append_domain_event(
                session,
                aggregate_type="code_index_version",
                aggregate_id=version.id,
                event_type="code_index.ready",
                payload={
                    "repository_id": str(repository_id),
                    "commit_sha": sha,
                    "content_hash": content_hash,
                    "kind": kind.value,
                },
                actor_id=ctx.actor.id,
                correlation_id=ctx.correlation_id,
                project_id=repo.project_id,
            )
            return version
        except DomainError:
            version.status = IndexVersionStatus.FAILED
            await session.flush()
            raise
        except Exception as exc:
            version.status = IndexVersionStatus.FAILED
            version.stats = {"error": str(exc)}
            await session.flush()
            await append_domain_event(
                session,
                aggregate_type="code_index_version",
                aggregate_id=version.id,
                event_type="code_index.failed",
                payload={"repository_id": str(repository_id), "commit_sha": sha, "error": str(exc)},
                actor_id=ctx.actor.id,
                correlation_id=ctx.correlation_id,
                project_id=repo.project_id,
            )
            raise
