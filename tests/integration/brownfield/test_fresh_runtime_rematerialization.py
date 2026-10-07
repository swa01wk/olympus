"""Phase 11 §14: re-materialize workspace and preserve durable repository understanding."""

from __future__ import annotations

import shutil
import subprocess

import pytest
from core.commands.context import CommandContext
from core.domain.enums import WorkspaceState
from core.domain.repositories.models import Repository, RepositoryWorkspace
from core.integrations.connectors.base import ConnectorAction
from core.integrations.connectors.registry import get_connector_registry
from core.intelligence.brownfield.models import RepositoryDiscovery
from core.intelligence.code_index.enums import IndexKind, IndexVersionStatus
from core.intelligence.code_index.models import CodeIndexVersion
from core.repositories.materialization import RepositoryMaterializationService
from core.repositories.workspace_locator import WorkspaceLocator
from core.traceability.models import RepositoryIndexPointer
from sqlalchemy import select
from tests.fixtures.brownfield_harness import brownfield_cycle_at_code_index

pytestmark = [pytest.mark.integration, pytest.mark.git, pytest.mark.asyncio]


@pytest.mark.asyncio
async def test_fresh_runtime_rematerialization_preserves_understanding(
    db_session,
    system_ctx: CommandContext,
) -> None:
    cycle, registered_sha, repo_id = await brownfield_cycle_at_code_index(db_session, system_ctx)
    discovery = (
        await db_session.execute(
            select(RepositoryDiscovery).where(RepositoryDiscovery.delivery_cycle_id == cycle.id)
        )
    ).scalar_one()
    discovery_hash = discovery.content_hash

    pointer = await db_session.get(RepositoryIndexPointer, repo_id)
    assert pointer and pointer.canonical_index_version_id
    canonical = await db_session.get(CodeIndexVersion, pointer.canonical_index_version_id)
    assert canonical and canonical.content_hash
    canonical_hash = canonical.content_hash

    repo = await db_session.get(Repository, repo_id)
    assert repo and repo.workspace_id and repo.registered_sha == registered_sha
    workspace = await db_session.get(RepositoryWorkspace, repo.workspace_id)
    assert workspace is not None
    path = WorkspaceLocator().resolve(workspace.storage_backend, workspace.logical_location)
    assert path.exists()
    shutil.rmtree(path)
    parent = path.parent
    parent.mkdir(parents=True, exist_ok=True)

    service = RepositoryMaterializationService()
    assert await service.resolve_materialization_head(db_session, repo_id) is None

    # Plan §12: until Phase 18 startup reconciler, operators use retry_materialization;
    # re-clone at the pinned registered_sha without mutating durable registration.
    assert repo.remote_url and repo.remote_url.startswith("file://")
    registry = get_connector_registry()
    await registry.execute_with_persistence(
        db_session,
        ConnectorAction(
            connector="git_local",
            action="clone_repository",
            target_resource=workspace.logical_location,
            inputs={
                "logical_location": workspace.logical_location,
                "remote_url": repo.remote_url,
            },
            idempotency_key=f"fresh-runtime:{repo_id}",
            correlation_id=system_ctx.correlation_id,
            expected_result_schema="CloneResult",
        ),
        actor_id=system_ctx.actor.id,
    )
    workspace.state = WorkspaceState.READY
    workspace.materialized_commit = registered_sha
    await db_session.flush()

    assert repo.registered_sha == registered_sha
    assert repo.canonical_commit == registered_sha

    head = await service.resolve_materialization_head(db_session, repo_id)
    assert head is not None
    assert head is not None
    assert head[0] == registered_sha
    subprocess.run(
        ["git", "rev-parse", registered_sha],
        cwd=path,
        check=True,
        capture_output=True,
    )

    from core.intelligence.code_index.canonical_service import CanonicalIndexService

    rebuilt = await CanonicalIndexService().promote_repository_snapshot(
        db_session, repo_id, registered_sha, system_ctx
    )
    assert rebuilt.content_hash == canonical_hash

    rediscovery = (
        await db_session.execute(
            select(RepositoryDiscovery).where(RepositoryDiscovery.delivery_cycle_id == cycle.id)
        )
    ).scalar_one()
    assert rediscovery.content_hash == discovery_hash

    candidate = (
        (
            await db_session.execute(
                select(CodeIndexVersion).where(
                    CodeIndexVersion.repository_id == repo_id,
                    CodeIndexVersion.commit_sha == registered_sha,
                    CodeIndexVersion.kind == IndexKind.CANDIDATE,
                    CodeIndexVersion.status == IndexVersionStatus.READY,
                )
            )
        )
        .scalars()
        .first()
    )
    if candidate is not None:
        assert candidate.content_hash == canonical_hash
