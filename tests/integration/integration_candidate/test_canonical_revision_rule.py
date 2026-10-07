from __future__ import annotations

import pytest
from core.domain.enums import RevisionCause
from core.domain.repositories.models import RepositoryRevision
from core.integration.enums import ICStatus
from core.traceability.models import RepositoryIndexPointer
from sqlalchemy import select
from tests.fixtures.integration_harness import (
    add_implementation_code_task,
    commit_files_in_worktree,
    create_and_run_integration,
    default_branch_head,
    git_dir_for_repository,
    seed_integration_fixture,
)

pytestmark = [pytest.mark.integration, pytest.mark.git]


@pytest.mark.asyncio
async def test_three_candidates_ready_advances_canonical_once(
    db_session,
    system_ctx,
) -> None:
    fixture = await seed_integration_fixture(db_session, system_ctx, project_key="ic-rule")
    materialization_sha = fixture.base_sha
    assert fixture.repository.canonical_commit == materialization_sha

    shas: list[str] = []
    for idx in range(1, 4):
        bundle = await add_implementation_code_task(
            db_session,
            system_ctx,
            fixture,
            title=f"Task {idx}",
            key_prefix=f"ex22{idx}",
        )
        sha = await commit_files_in_worktree(
            db_session,
            system_ctx,
            bundle,
            {f"src/part{idx}.py": f"def feature_{idx}():\n    return {idx}\n"},
            message=f"feat: part {idx}",
        )
        shas.append(sha)

    for candidate_sha in shas:
        rev = await db_session.execute(
            select(RepositoryRevision).where(RepositoryRevision.commit_sha == candidate_sha)
        )
        assert rev.scalar_one_or_none() is None

    ic = await create_and_run_integration(db_session, system_ctx, fixture.cycle.id)
    assert ic.status == ICStatus.READY
    assert ic.integrated_sha is not None
    integrated = ic.integrated_sha

    await db_session.refresh(fixture.repository)
    assert fixture.repository.canonical_commit == integrated
    assert fixture.repository.canonical_commit != shas[0]
    assert fixture.repository.canonical_commit != materialization_sha

    pointer = await db_session.get(RepositoryIndexPointer, fixture.repository.id)
    assert pointer is not None and pointer.canonical_index_version_id is not None

    from core.intelligence.code_index.models import CodeIndexVersion

    version = await db_session.get(CodeIndexVersion, pointer.canonical_index_version_id)
    assert version is not None
    assert version.commit_sha == integrated

    latest_rev = (
        await db_session.execute(
            select(RepositoryRevision)
            .where(RepositoryRevision.repository_id == fixture.repository.id)
            .order_by(RepositoryRevision.sequence.desc())
            .limit(1)
        )
    ).scalar_one()
    assert latest_rev.cause == RevisionCause.INTEGRATION_READY
    assert latest_rev.integration_candidate_id == ic.id
    assert latest_rev.commit_sha == integrated

    for candidate_sha in shas:
        rev = await db_session.execute(
            select(RepositoryRevision).where(RepositoryRevision.commit_sha == candidate_sha)
        )
        assert rev.scalar_one_or_none() is None


@pytest.mark.asyncio
async def test_default_branch_unchanged_after_integration(
    db_session,
    system_ctx,
) -> None:
    fixture = await seed_integration_fixture(db_session, system_ctx, project_key="ic-branch")
    git_dir = await git_dir_for_repository(db_session, fixture.repository.id)
    before = await default_branch_head(git_dir)
    bundle = await add_implementation_code_task(
        db_session,
        system_ctx,
        fixture,
        title="Only task",
        key_prefix="br1",
    )
    await commit_files_in_worktree(
        db_session,
        system_ctx,
        bundle,
        {"src/only.py": "def only():\n    return 1\n"},
    )
    ic = await create_and_run_integration(db_session, system_ctx, fixture.cycle.id)
    assert ic.status == ICStatus.READY
    after = await default_branch_head(git_dir)
    assert before == after
