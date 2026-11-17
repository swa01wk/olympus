from __future__ import annotations

import subprocess
from pathlib import Path

import pytest
from core.domain.enums import ExecutionStatus, TaskContractStatus, TaskOrigin, TaskStatus, WorkType
from core.domain.repositories.models import Repository, RepositoryWorkspace
from core.domain.task_contracts.models import TaskContract
from core.domain.task_contracts.schemas import TaskContractBody
from core.domain.tasks.service import TaskService
from core.intelligence.impact.engine import ImpactEngine
from core.intelligence.impact.enums import ImpactAssessmentStatus
from core.intelligence.impact.models import StalenessEvent
from core.intelligence.impact.staleness import StalenessService
from core.product_model.specifications.delta import SpecDeltaService
from core.repositories.workspace_locator import WorkspaceLocator
from core.scheduler.admission import AdmissionService
from sqlalchemy import select
from tests.fixtures.code_index_harness import SUPPORTDESK_R1
from tests.fixtures.impact_harness import seed_supportdesk_ticket_priority_impact
from tests.fixtures.repositories import fixture_origin

pytestmark = [pytest.mark.integration, pytest.mark.asyncio]


def _advance_fixture_origin(work: Path) -> str:
    """Commit on top of the fixture origin in a private clone (never in tests/fixtures)."""
    subprocess.run(
        ["git", "clone", "-q", str(fixture_origin(SUPPORTDESK_R1)), str(work)],
        check=True,
        capture_output=True,
    )
    (work / ".canonical_staleness").write_text("touch\n", encoding="utf-8")
    subprocess.run(["git", "add", "-A"], cwd=work, check=True, capture_output=True)
    subprocess.run(
        [
            "git",
            "-c",
            "user.email=t@t.com",
            "-c",
            "user.name=t",
            "commit",
            "-m",
            "canonical staleness touch",
        ],
        cwd=work,
        check=True,
        capture_output=True,
    )
    return subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=work,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()


async def _fetch_origin_into_workspace(session, repository_id, origin: Path) -> None:
    repo = await session.get(Repository, repository_id)
    assert repo is not None and repo.workspace_id is not None
    ws = await session.get(RepositoryWorkspace, repo.workspace_id)
    assert ws is not None
    git_dir = WorkspaceLocator().resolve(ws.storage_backend, ws.logical_location)
    subprocess.run(
        ["git", "--git-dir", str(git_dir), "fetch", f"file://{origin}", "HEAD:main"],
        check=True,
        capture_output=True,
    )


async def test_canonical_revision_stales_ia_not_execution_on_descendant(
    db_session, system_ctx, tmp_path
) -> None:
    fx = await seed_supportdesk_ticket_priority_impact(db_session, system_ctx)
    delta = await SpecDeltaService().compute(
        db_session,
        from_spec_id=fx.spec_v1_id,
        to_spec_id=fx.spec_v2_id,
        delivery_cycle_id=fx.cycle_id,
        ctx=system_ctx,
    )
    ia = await ImpactEngine().assess(
        db_session,
        fx.cycle_id,
        spec_delta_id=delta.id,
        index_version_id=fx.index_version.id,
        ctx=system_ctx,
    )
    old_sha = fx.commit_sha
    work = tmp_path / "origin"
    new_sha = _advance_fixture_origin(work)
    await _fetch_origin_into_workspace(db_session, fx.repository_id, work)

    task = await TaskService().create_task(
        db_session,
        fx.cycle_id,
        "completed",
        WorkType.ANALYSIS,
        TaskOrigin.CONTROL_PLANE,
        system_ctx,
    )
    contract = TaskContract(
        task_id=task.id,
        key="v1",
        version=1,
        status=TaskContractStatus.ISSUED,
        body=TaskContractBody(
            objective="staleness",
            work_type=WorkType.ANALYSIS,
            inputs=[],
            executor_kind="DETERMINISTIC",
            deterministic_executor="noop.verify_artifact",
        ).model_dump(mode="json"),
        content_hash="staleness-contract",
        compiled_by="test",
    )
    db_session.add(contract)
    await db_session.flush()
    task.current_contract_id = contract.id
    task.status = TaskStatus.READY
    await db_session.flush()
    ex = await AdmissionService().admit_task(db_session, task.id, system_ctx)
    task.status = TaskStatus.COMPLETED
    await db_session.flush()

    report = await StalenessService().on_canonical_revision_changed(
        db_session,
        fx.repository_id,
        old_sha,
        new_sha,
        "CANONICAL_REVISION_CHANGED",
        ctx=system_ctx,
    )
    await db_session.refresh(ia)
    assert ia.status == ImpactAssessmentStatus.STALE.value
    await db_session.refresh(task)
    assert task.status == TaskStatus.REVALIDATION_REQUIRED
    await db_session.refresh(ex)
    assert ex.status == ExecutionStatus.QUEUED
    assert any(e.cause_type == "CANONICAL_REVISION_CHANGED" for e in report.events)
    events = (
        await db_session.execute(
            select(StalenessEvent).where(StalenessEvent.cause_type == "CANONICAL_REVISION_CHANGED")
        )
    ).scalars()
    assert events
