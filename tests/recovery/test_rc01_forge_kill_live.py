"""RC-01 live: Forge lease kill mid-execution then retry completes (Phase 18/19)."""

from __future__ import annotations

import os
import shutil
import subprocess
import uuid
from pathlib import Path

import pytest
from core.commands.context import CommandContext
from core.domain.candidate_commits.models import CandidateCommit
from core.domain.delivery_cycles.models import DeliveryCycle
from core.domain.enums import (
    DeliveryCycleType,
    ExecutionStatus,
    RepositoryProvider,
    TaskContractStatus,
    TaskOrigin,
    TaskStatus,
    WorkType,
)
from core.domain.executions.models import Execution
from core.domain.projects.models import Project
from core.domain.task_contracts.models import TaskContract
from core.domain.task_contracts.schemas import TaskContractBody
from core.domain.tasks.service import TaskService
from core.execution.worker import ExecutionWorker
from core.repositories.materialization import RepositoryMaterializationService
from core.repositories.service import RepositoryService
from core.scheduler.admission import AdmissionService
from sqlalchemy import select
from tests.journey.chained import chaos_hooks
from tests.journey.chained.chaos_hooks import inject_rc01_forge_lease_expiry
from tests.live_credentials import any_live_provider_configured

pytestmark = [pytest.mark.recovery, pytest.mark.live_llm]


@pytest.mark.asyncio
async def test_rc01_forge_kill_mid_execution_live(db_session, system_actor) -> None:
    if os.environ.get("LLM_LIVE_TESTS") != "1":
        pytest.skip("LLM_LIVE_TESTS=1 required")
    if not any_live_provider_configured():
        pytest.skip("No live provider API key configured")
    if os.environ.get("OLYMPUS_FULL_RECOVERY") != "1":
        pytest.skip("Set OLYMPUS_FULL_RECOVERY=1 to run RC-01 live Forge kill proof")

    os.environ["MVP_CHAOS"] = "1"
    os.environ["MVP_CHAOS_FORGE_KILL"] = "1"
    chaos_hooks._rc01_forge_done = False
    chaos_hooks._docker_worker_kill_done = True

    fixture_root = Path(__file__).resolve().parents[1] / "fixtures" / "repos" / "mini_python"
    if not fixture_root.exists():
        pytest.skip("mini_python fixture missing")

    work_origin = (
        Path(os.environ.get("OLYMPUS_WORKSPACE_ROOT", "/tmp"))
        / f"rc01-forge-{uuid.uuid4().hex[:8]}"
    )
    if work_origin.exists():
        shutil.rmtree(work_origin)
    shutil.copytree(fixture_root, work_origin)
    subprocess.run(["git", "init", "-b", "main"], cwd=work_origin, check=True, capture_output=True)
    subprocess.run(["git", "add", "-A"], cwd=work_origin, check=True, capture_output=True)
    subprocess.run(
        [
            "git",
            "-c",
            "user.email=forge@olympus.local",
            "-c",
            "user.name=Forge",
            "commit",
            "-m",
            "init",
        ],
        cwd=work_origin,
        check=True,
        capture_output=True,
    )

    ctx = CommandContext(actor=system_actor, correlation_id="rc01-forge-live")
    project = Project(key="rc01-forge", name="RC01 Forge")
    db_session.add(project)
    await db_session.flush()

    repo = await RepositoryService().register_external(
        db_session,
        project.id,
        "mini",
        RepositoryProvider.LOCAL,
        f"file://{work_origin.resolve()}",
        "main",
        "none:",
        ctx,
    )
    await RepositoryMaterializationService().materialize_external(db_session, repo.id, ctx)
    await db_session.refresh(repo)
    canonical_before = repo.canonical_commit

    cycle = DeliveryCycle(
        project_id=project.id,
        key="C-RC01",
        type=DeliveryCycleType.FEATURE_CHANGE,
        objective="slugify",
        state="DEVELOPMENT",
        state_version=0,
        opened_by_actor_id=system_actor.id,
        repository_id=repo.id,
    )
    db_session.add(cycle)
    await db_session.flush()
    os.environ["MVP_CHAOS_CYCLE_ID"] = str(cycle.id)

    task = await TaskService().create_task(
        db_session,
        cycle.id,
        "Add slugify",
        WorkType.CODE_CHANGE,
        TaskOrigin.IMPLEMENTATION_PLAN,
        ctx,
    )
    body = TaskContractBody(
        objective="Add function slugify(text) in mini/core.py with tests in tests/",
        work_type=WorkType.CODE_CHANGE,
        repository_id=repo.id,
        base_policy="EXPLICIT_SHA",
        base_commit=canonical_before,
        allowed_scope=["mini/**", "tests/**"],
        allowed_actions=[
            "repo.read",
            "repo.search",
            "repo.list",
            "repo.write",
            "shell.run",
            "test.run",
            "git.diff",
            "git.status",
            "git.commit",
            "olympus.ask_question",
            "olympus.submit_artifact",
        ],
        required_outputs=["candidate_commit"],
        inputs=[],
        executor_kind="AGENT_RUNTIME",
        agent_profile="forge.implementation",
    )
    contract = TaskContract(
        task_id=task.id,
        key="v1",
        version=1,
        status=TaskContractStatus.ISSUED,
        body=body.model_dump(mode="json"),
        content_hash="rc01-forge-hash",
        compiled_by="compiler:TaskContractCompiler",
    )
    db_session.add(contract)
    await db_session.flush()
    task.current_contract_id = contract.id
    task.status = TaskStatus.READY
    await db_session.flush()

    worker = ExecutionWorker(worker_id=f"rc01-forge-{uuid.uuid4().hex[:6]}")
    execution = await AdmissionService().admit_task(db_session, task.id, ctx)
    first_id = execution.id
    lease_injected = False

    for _ in range(120):
        await worker.run_once(db_session, ctx)
        execution = await db_session.get(Execution, first_id)
        assert execution is not None
        if execution.status == ExecutionStatus.STARTED and not lease_injected:
            assert await inject_rc01_forge_lease_expiry(db_session, ctx, cycle.id)
            lease_injected = True
        if execution.status in {ExecutionStatus.FAILED, ExecutionStatus.COMPLETED}:
            break

    assert lease_injected, "Forge never reached STARTED for RC-01 injection"
    assert execution.status == ExecutionStatus.FAILED
    assert execution.failure_class == "LEASE_EXPIRED"

    retry = await AdmissionService().admit_task(db_session, task.id, ctx)
    retry_id = retry.id
    for _ in range(120):
        await worker.run_once(db_session, ctx)
        retry = await db_session.get(Execution, retry_id)
        assert retry is not None
        if retry.status == ExecutionStatus.COMPLETED:
            break

    assert retry.status == ExecutionStatus.COMPLETED, retry.failure_detail
    cc = (
        await db_session.execute(
            select(CandidateCommit).where(CandidateCommit.execution_id == retry.id)
        )
    ).scalar_one_or_none()
    assert cc is not None
