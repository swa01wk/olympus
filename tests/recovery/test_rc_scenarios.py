from __future__ import annotations

import os
import shutil
import subprocess
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from core.domain.enums import ExecutionStatus
from core.ops.invariants import assert_system_invariants
from core.ops.startup_reconcilers import reconcile_orphan_leases
from core.runtime.contracts import AgentResumeRequest
from core.runtime.langgraph_runtime import LangGraphRuntime
from core.runtime.providers.fake_provider import FakeScriptStep
from core.testing.faults import fault_point
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from tests.fixtures.execution_harness import seed_ready_task

pytestmark = pytest.mark.recovery


async def _invariants_ok(session: AsyncSession, project_id=None) -> None:
    report = await assert_system_invariants(session, project_id)
    assert report.ok, report.violations


@pytest.mark.asyncio
async def test_rc01_execution_lease_expiry_and_retry(async_engine) -> None:
    """RC-01 surrogate: lease loss mid-run → FAILED(LEASE_EXPIRED) → retry completes."""
    from tests.workflow.execution.test_recovery import (
        test_expired_lease_after_start_fails_and_retries,
    )

    await test_expired_lease_after_start_fails_and_retries(async_engine)
    factory = async_sessionmaker(bind=async_engine, class_=AsyncSession, expire_on_commit=False)
    async with factory() as session:
        await _invariants_ok(session)


@pytest.mark.asyncio
async def test_rc02_langgraph_state_loss_continuation_resume(
    model_router, fake_provider, db_session
) -> None:
    """RC-02: resume from continuation package without LangGraph checkpoint."""
    from pathlib import Path as P
    from uuid import uuid4

    text = P("tests/fixtures/diagnostic/paragraph.txt").read_text(encoding="utf-8")
    step = FakeScriptStep(
        structured={"title": "Resume ok", "bullet_points": ["one"], "word_count_estimate": 10}
    )
    fake_provider.set_script([step])
    runtime = LangGraphRuntime(db_session, model_router)
    result = await runtime.resume(
        AgentResumeRequest(
            run_id=uuid4(),
            agent_profile="diagnostic.structured_echo",
            continuation={"source_text": text},
        )
    )
    assert result.status == "OUTPUT_PRODUCED"
    await _invariants_ok(db_session)


@pytest.mark.asyncio
async def test_rc03_command_idempotency_no_duplicate_state(
    db_session, sample_project, system_actor
) -> None:
    """RC-03 surrogate: duplicate Idempotency-Key does not duplicate transitions."""
    from tests.persistence.test_idempotency import test_idempotent_create_replays

    await test_idempotent_create_replays(db_session, sample_project, system_actor)
    await _invariants_ok(db_session, sample_project.id)


@pytest.mark.asyncio
async def test_rc04_startup_reconciler_expires_stale_active_leases(db_session, system_ctx) -> None:
    """RC-04 surrogate: orphan/stale lease reconciled on startup."""
    from core.execution.leases.manager import LeaseManager
    from core.scheduler.admission import AdmissionService

    bundle = await seed_ready_task(db_session, key_prefix="rc04")
    ex = await AdmissionService().admit_task(db_session, bundle.task.id, system_ctx)
    lease = await LeaseManager().claim(db_session, "rc04-worker", system_ctx)
    assert lease is not None
    from core.execution.service import ExecutionService

    await ExecutionService().transition(db_session, ex.id, "start", system_ctx, lease_id=lease.id)
    lease.expires_at = datetime.now(UTC).replace(tzinfo=None) - timedelta(hours=1)
    await db_session.flush()
    count = await reconcile_orphan_leases(db_session)
    assert count >= 1
    await db_session.refresh(ex)
    assert ex.status == ExecutionStatus.FAILED
    await _invariants_ok(db_session, bundle.project.id)


@pytest.mark.asyncio
async def test_rc05_integrating_ic_recovery_placeholder(db_session) -> None:
    """RC-05 full IC merge kill — covered by Phase 08 git E2E; invariants hold on empty DB."""
    await _invariants_ok(db_session)


@pytest.mark.asyncio
async def test_rc06_fault_after_gate_finalize(db_session, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("OLYMPUS_FAULTS", "1")
    monkeypatch.setenv("OLYMPUS_FAULT_POINT", "after_gate_finalize")
    with (
        pytest.raises(RuntimeError, match="after_gate_finalize"),
        fault_point("after_gate_finalize"),
    ):
        pass
    await _invariants_ok(db_session)


@pytest.mark.asyncio
async def test_rc07_release_tag_recovery_placeholder(db_session) -> None:
    """RC-07 Stratos tag idempotency — see release git integration tests."""
    await _invariants_ok(db_session)


@pytest.mark.asyncio
async def test_rc08_checkpointed_execution_survives_without_runtime(db_session, system_ctx) -> None:
    """RC-08 surrogate: execution can remain non-terminal while awaiting external input."""
    from core.execution.service import ExecutionService
    from core.execution.snapshots.builder import SnapshotBuilder

    bundle = await seed_ready_task(db_session, key_prefix="rc08")
    from core.execution.leases.manager import LeaseManager
    from core.scheduler.admission import AdmissionService

    ex = await AdmissionService().admit_task(db_session, bundle.task.id, system_ctx)
    lease_row = await LeaseManager().claim(db_session, "rc08-worker", system_ctx)
    assert lease_row is not None
    await SnapshotBuilder().build(db_session, ex)
    await ExecutionService().transition(
        db_session, ex.id, "start", system_ctx, lease_id=lease_row.id
    )
    await db_session.refresh(ex)
    non_terminal = {
        ExecutionStatus.STARTED,
        ExecutionStatus.CHECKPOINTED,
        ExecutionStatus.QUEUED,
    }
    assert ex.status in non_terminal
    await _invariants_ok(db_session, bundle.project.id)


@pytest.mark.asyncio
async def test_rc09_connector_unavailable_placeholder(db_session) -> None:
    """RC-09 live connector fault — deterministic invariant baseline."""
    await _invariants_ok(db_session)


@pytest.mark.asyncio
async def test_rc10_scheduler_admission_no_duplicate_executions(db_session, system_ctx) -> None:
    from core.scheduler.admission import AdmissionService

    await seed_ready_task(db_session, key_prefix="rc10")
    svc = AdmissionService()
    first_batch = await svc.admit_batch(db_session, 5, system_ctx)
    second_batch = await svc.admit_batch(db_session, 5, system_ctx)
    assert len(first_batch) == 1
    assert second_batch == []
    await _invariants_ok(db_session)


@pytest.mark.asyncio
async def test_rc12_backup_and_restore_smoke(postgres_url: str, tmp_path: Path) -> None:
    if shutil.which("pg_dump") is None or shutil.which("pg_restore") is None:
        pytest.skip("pg_dump/pg_restore not available")
    backup_dir = tmp_path / "backup"
    storage = tmp_path / "storage"
    workspace = tmp_path / "workspace"
    storage.mkdir()
    workspace.mkdir()
    (storage / "marker.txt").write_text("ok", encoding="utf-8")
    env = os.environ.copy()
    env["DATABASE_URL"] = postgres_url
    env["OLYMPUS_STORAGE_ROOT"] = str(storage)
    env["OLYMPUS_WORKSPACE_ROOT"] = str(workspace)
    root = Path(__file__).resolve().parents[2]
    subprocess.run([str(root / "scripts/ops/backup.sh"), str(backup_dir)], check=True, env=env)
    assert (backup_dir / "olympus.dump").is_file()
    (storage / "marker.txt").unlink()
    subprocess.run([str(root / "scripts/ops/restore.sh"), str(backup_dir)], check=True, env=env)
    assert (storage / "marker.txt").read_text(encoding="utf-8") == "ok"


@pytest.mark.asyncio
async def test_rc01_live_forge_kill_requires_full_stack() -> None:
    if os.environ.get("OLYMPUS_FULL_RECOVERY") != "1":
        pytest.skip(
            "RC-01 live kill: set OLYMPUS_FULL_RECOVERY=1 (see test_rc01_forge_kill_live.py)"
        )
    pytest.skip("RC-01 live wiring delegated to test_rc01_forge_kill_live.py")
