from __future__ import annotations

import os
import shutil
import subprocess
import uuid
from pathlib import Path

import pytest
from core.commands.context import CommandContext
from core.domain.actions.models import ActionRequest
from core.domain.actors.models import Actor
from core.domain.candidate_commits.models import CandidateCommit
from core.domain.enums import ExecutionStatus, TaskContractStatus, TaskOrigin, TaskStatus, WorkType
from core.domain.executions.models import Execution
from core.domain.model_calls.models import ModelCall
from core.domain.task_contracts.models import TaskContract
from core.domain.task_contracts.schemas import TaskContractBody
from core.domain.tasks.service import TaskService
from core.execution.worker import ExecutionWorker
from core.repositories.materialization import RepositoryMaterializationService
from core.repositories.service import RepositoryService
from core.scheduler.admission import AdmissionService
from sqlalchemy import func, select
from tests.live_credentials import any_live_provider_configured

pytestmark = [pytest.mark.live_llm, pytest.mark.integration]


@pytest.mark.asyncio
async def test_forge_candidate_commit_live(db_session, system_actor) -> None:
    if os.getenv("LLM_LIVE_TESTS") != "1":
        pytest.skip("LLM_LIVE_TESTS=1 required")
    if not any_live_provider_configured():
        pytest.skip("No live provider API key configured")

    fixture_root = Path(__file__).resolve().parents[2] / "fixtures" / "repos" / "mini_python"
    if not fixture_root.exists():
        pytest.skip("mini_python fixture missing")

    work_origin = (
        Path(os.environ.get("OLYMPUS_WORKSPACE_ROOT", "/tmp"))
        / f"forge-origin-{uuid.uuid4().hex[:8]}"
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

    from core.domain.enums import ActorKind, ActorRole

    agent_actor = Actor(
        kind=ActorKind.AGENT,
        name="forge-live-agent",
        roles=[ActorRole.SYSTEM.value],
    )
    db_session.add(agent_actor)
    await db_session.flush()
    ctx = CommandContext(actor=system_actor, correlation_id="live-forge")
    from core.domain.delivery_cycles.models import DeliveryCycle
    from core.domain.enums import DeliveryCycleType
    from core.domain.projects.models import Project

    project = Project(key="forge-live", name="Forge Live")
    db_session.add(project)
    await db_session.flush()
    from core.domain.enums import RepositoryProvider

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
        key="C-FORGE",
        type=DeliveryCycleType.FEATURE_CHANGE,
        objective="slugify",
        state="DEVELOPMENT",
        state_version=0,
        opened_by_actor_id=system_actor.id,
        repository_id=repo.id,
    )
    db_session.add(cycle)
    await db_session.flush()
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
        content_hash="forge-live-hash",
        compiled_by="compiler:TaskContractCompiler",
    )
    db_session.add(contract)
    await db_session.flush()
    task.current_contract_id = contract.id
    task.status = TaskStatus.READY
    await db_session.flush()

    worker = ExecutionWorker(worker_id=f"forge-live-{uuid.uuid4().hex[:6]}")
    execution: Execution | None = None
    for attempt in range(2):
        if attempt > 0:
            task.status = TaskStatus.READY
            await db_session.flush()
        execution = await AdmissionService().admit_task(db_session, task.id, ctx)
        execution_id = execution.id
        for _ in range(120):
            await worker.run_once(db_session, ctx)
            execution = await db_session.get(Execution, execution_id)
            assert execution is not None
            if execution.status in {ExecutionStatus.COMPLETED, ExecutionStatus.FAILED}:
                break
        if execution.status == ExecutionStatus.COMPLETED:
            break
        detail = execution.failure_detail or {}
        msg = detail.get("message", "") if isinstance(detail, dict) else str(detail)
        if attempt == 0 and "Structured output validation failed" in msg:
            continue
        break

    assert execution is not None
    assert execution.status == ExecutionStatus.COMPLETED, execution.failure_detail
    cc = await db_session.execute(
        select(CandidateCommit).where(CandidateCommit.execution_id == execution.id)
    )
    row = cc.scalar_one_or_none()
    assert row is not None
    assert row.diff_artifact_id is not None
    assert row.branch.startswith("olympus/")

    action_count = await db_session.scalar(
        select(func.count())
        .select_from(ActionRequest)
        .where(ActionRequest.execution_id == execution.id)
    )
    assert action_count and action_count > 0

    calls = (
        await db_session.execute(
            select(ModelCall).where(ModelCall.execution_id == execution.id).limit(1)
        )
    ).scalar_one_or_none()
    assert calls is not None

    await db_session.refresh(repo)
    assert repo.canonical_commit == canonical_before
