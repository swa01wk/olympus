"""Deterministic delivery-cycle workflow: candidates → IC READY → canonical index (Phase 08 §15)."""

from __future__ import annotations

import pytest
from core.assurance.findings_policy import FindingPolicy
from core.integration.enums import ICStatus
from core.traceability.lineage.factory import build_lineage_service
from core.traceability.models import RepositoryIndexPointer
from tests.fixtures.integration_harness import (
    add_implementation_code_task,
    attach_product_lineage,
    commit_files_in_worktree,
    create_and_run_integration,
    seed_integration_fixture,
)

pytestmark = [pytest.mark.workflow, pytest.mark.integration]


@pytest.mark.asyncio
async def test_workflow_two_candidates_integration_ready(
    db_session,
    system_ctx,
) -> None:
    fixture = await seed_integration_fixture(db_session, system_ctx, project_key="wf-ic")
    shas: list[str] = []
    lineage_root = None
    for idx in (1, 2):
        bundle = await add_implementation_code_task(
            db_session,
            system_ctx,
            fixture,
            title=f"WF task {idx}",
            key_prefix=f"wfic{idx}",
        )
        if idx == 1:
            lineage_root = await attach_product_lineage(db_session, fixture, bundle.task)
        sha = await commit_files_in_worktree(
            db_session,
            system_ctx,
            bundle,
            {f"src/wf_part{idx}.py": f"def wf_part_{idx}():\n    return {idx}\n"},
            message=f"feat: wf part {idx}",
            principal_symbols=[f"wf_part_{idx}"] if idx == 1 else None,
        )
        shas.append(sha)

    ic = await create_and_run_integration(db_session, system_ctx, fixture.cycle.id)
    assert ic.status == ICStatus.READY
    assert ic.integrated_sha is not None

    await db_session.refresh(fixture.repository)
    assert fixture.repository.canonical_commit == ic.integrated_sha

    pointer = await db_session.get(RepositoryIndexPointer, fixture.repository.id)
    assert pointer is not None and pointer.canonical_index_version_id is not None

    policy = FindingPolicy()
    assert policy.is_blocking("MAJOR", "MERGE_CONFLICT") is True
    assert policy.is_blocking("MINOR", "STYLE") is False

    assert lineage_root is not None
    lineage = build_lineage_service()
    graph = await lineage.forward(db_session, "FEATURE", lineage_root.feature_id)
    assert any(n.type == "FEATURE" for n in graph.nodes)
