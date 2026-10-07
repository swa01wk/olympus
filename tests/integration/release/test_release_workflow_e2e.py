"""Phase 10 acceptance — release eligibility, approval, execution, outcome."""

from __future__ import annotations

import pytest
from core.domain.approvals.models import Approval
from core.domain.enums import ApprovalType, RevisionCause
from core.domain.execution_workspaces.models import ExecutionWorkspace
from core.domain.repositories.models import Repository, RepositoryRevision, RepositoryWorkspace
from core.integration.enums import ICStatus
from core.release.enums import ReleaseStatus
from core.release.manifest import ManifestBuilder
from core.release.models import DeliveryOutcome, Release, ReleaseEligibilityEvaluation
from core.release.schemas import ReleaseManifestContent
from core.traceability.lineage.factory import build_lineage_service
from core.traceability.models import RepositoryIndexPointer
from sqlalchemy import select
from sqlalchemy.exc import DBAPIError
from tests.fixtures.integration_harness import (
    default_branch_head,
    git_dir_for_repository,
)
from tests.fixtures.release_harness import (
    approve_and_execute_release,
    ready_eligible_release,
)

pytestmark = [pytest.mark.integration, pytest.mark.git]


@pytest.mark.asyncio
async def test_eligibility_persisted_with_per_condition_reasons(
    db_session,
    system_ctx,
    operator_ctx,
) -> None:
    ic, _, release = await ready_eligible_release(
        db_session, system_ctx, operator_ctx, project_key="rel-elig"
    )
    assert release.latest_eligibility_id is not None
    ev = await db_session.get(ReleaseEligibilityEvaluation, release.latest_eligibility_id)
    assert ev is not None and ev.eligible is True
    names = {c["name"] for c in ev.conditions}
    assert "manifest_valid" in names
    assert "required_gates_pass" in names
    assert all(c["ok"] for c in ev.conditions)
    assert ic.status == ICStatus.READY


@pytest.mark.asyncio
async def test_release_approval_pinned_to_manifest_hash(
    db_session,
    system_ctx,
    operator_ctx,
) -> None:
    _, _, release = await ready_eligible_release(
        db_session, system_ctx, operator_ctx, project_key="rel-appr"
    )
    assert release.approval_id is not None
    manifest = await ManifestBuilder().load_manifest(db_session, release.manifest_id)
    assert manifest is not None
    approval = await db_session.get(Approval, release.approval_id)
    assert approval is not None
    assert approval.approval_type == ApprovalType.RELEASE
    assert approval.subject_type == "release_manifest"
    assert approval.subject_hash == manifest.content_hash
    manifest.content = {"tampered": True}
    with pytest.raises(DBAPIError):
        await db_session.flush()


@pytest.mark.asyncio
async def test_release_e2e_sha_alignment_outcome_and_lineage(
    db_session,
    system_ctx,
    operator_ctx,
) -> None:
    ic, fixture, release = await ready_eligible_release(
        db_session, system_ctx, operator_ctx, project_key="rel-e2e"
    )
    manifest_row = await ManifestBuilder().load_manifest(db_session, release.manifest_id)
    assert manifest_row is not None
    content = ReleaseManifestContent.model_validate(manifest_row.content)
    assert content.integration_candidate.get("integrated_sha") == ic.integrated_sha
    assert content.repository.get("canonical_commit") == ic.integrated_sha

    release = await approve_and_execute_release(db_session, release, operator_ctx, system_ctx)
    assert release.status == ReleaseStatus.RELEASED
    integrated = ic.integrated_sha
    assert integrated is not None

    repo = await db_session.get(Repository, fixture.repository.id)
    assert repo is not None
    assert repo.canonical_commit == integrated
    assert repo.released_commit == integrated

    git_dir = await git_dir_for_repository(db_session, repo.id)
    assert await default_branch_head(git_dir) == integrated

    rev = (
        await db_session.execute(
            select(RepositoryRevision).where(
                RepositoryRevision.repository_id == repo.id,
                RepositoryRevision.cause == RevisionCause.RELEASED,
            )
        )
    ).scalar_one()
    assert rev.commit_sha == integrated
    assert rev.release_id == release.id

    pointer = await db_session.get(RepositoryIndexPointer, repo.id)
    assert pointer is not None
    assert pointer.released_index_version_id == pointer.canonical_index_version_id

    outcome = (
        await db_session.execute(
            select(DeliveryOutcome).where(DeliveryOutcome.delivery_cycle_id == fixture.cycle.id)
        )
    ).scalar_one()
    assert outcome.result == "RELEASED"

    svc = build_lineage_service()
    forward_ic = await svc.forward(db_session, "INTEGRATION_CANDIDATE", ic.id)
    forward_types = {n.type for n in forward_ic.nodes}
    assert "RELEASE" in forward_types

    snapshot = {
        "release_status": release.status.value,
        "outcome_id": str(outcome.id),
        "eligibility_id": str(release.latest_eligibility_id),
        "integrated_sha": integrated,
    }

    release_id = release.id
    outcome_id = outcome.id
    eligibility_id = release.latest_eligibility_id
    db_session.expire_all()
    rel2 = await db_session.get(Release, release_id)
    assert rel2 is not None and rel2.status == ReleaseStatus.RELEASED
    out2 = await db_session.get(DeliveryOutcome, outcome_id)
    assert out2 is not None and out2.result == "RELEASED"
    if eligibility_id is not None:
        ev2 = await db_session.get(ReleaseEligibilityEvaluation, eligibility_id)
        assert ev2 is not None and ev2.eligible is True

    assert snapshot["release_status"] == "RELEASED"


@pytest.mark.asyncio
async def test_forge_workspace_isolated_from_canonical(
    db_session,
    system_ctx,
    operator_ctx,
) -> None:
    ic, fixture, _release = await ready_eligible_release(
        db_session, system_ctx, operator_ctx, project_key="rel-wt"
    )
    assert ic.integrated_sha is not None
    repo = await db_session.get(Repository, fixture.repository.id)
    assert repo is not None and repo.workspace_id is not None
    canonical_ws = await db_session.get(RepositoryWorkspace, repo.workspace_id)
    assert canonical_ws is not None

    from core.domain.candidate_commits.models import CandidateCommit
    from core.domain.executions.models import Execution
    from core.integration.models import IntegrationCandidateCommit

    cc_ids = (
        await db_session.execute(
            select(IntegrationCandidateCommit.candidate_commit_id).where(
                IntegrationCandidateCommit.integration_candidate_id == ic.id
            )
        )
    ).scalars()
    exec_ids = []
    for cc_id in cc_ids:
        cc = await db_session.get(CandidateCommit, cc_id)
        if cc and cc.execution_id:
            exec_ids.append(cc.execution_id)
    assert exec_ids
    for exec_id in exec_ids:
        ex_ws = (
            await db_session.execute(
                select(ExecutionWorkspace).where(ExecutionWorkspace.execution_id == exec_id)
            )
        ).scalar_one()
        ex = await db_session.get(Execution, exec_id)
        assert ex is not None
        assert ex_ws.logical_location != canonical_ws.logical_location
        assert "worktrees" in ex_ws.logical_location
