"""Live Forge workflow precursor: live Forge + deterministic candidate → IC READY (Phase 08 §15).

Two fully live Forge tasks often merge-conflict when the model touches shared paths; this
test keeps one live Forge execution (real ModelRouter path) and one harness commit so
integration merge is stable in verify scripts.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import uuid
from contextlib import suppress
from pathlib import Path

import pytest
from core.commands.context import CommandContext
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
from core.domain.task_contracts.models import TaskContract
from core.domain.task_contracts.schemas import TaskContractBody
from core.domain.tasks.service import TaskService
from core.execution.worker import ExecutionWorker
from core.integration.enums import ICStatus
from core.integration.service import IntegrationService
from core.repositories.materialization import RepositoryMaterializationService
from core.repositories.service import RepositoryService
from core.scheduler.admission import AdmissionService
from core.traceability.models import RepositoryIndexPointer
from sqlalchemy import select
from tests.fixtures.integration_harness import (
    IntegrationFixture,
    add_implementation_code_task,
    commit_files_in_worktree,
    run_worker_until_ic_settled,
)
from tests.live_credentials import any_live_provider_configured

pytestmark = [
    pytest.mark.workflow,
    pytest.mark.live_llm,
    pytest.mark.integration,
]


async def _run_forge_live_task(
    db_session,
    ctx: CommandContext,
    *,
    cycle_id: uuid.UUID,
    repository_id: uuid.UUID,
    base_commit: str,
    title: str,
    objective: str,
    scope: list[str],
    content_hash: str,
) -> None:
    task = await TaskService().create_task(
        db_session,
        cycle_id,
        title,
        WorkType.CODE_CHANGE,
        TaskOrigin.IMPLEMENTATION_PLAN,
        ctx,
    )
    body = TaskContractBody(
        objective=objective,
        work_type=WorkType.CODE_CHANGE,
        repository_id=repository_id,
        base_policy="EXPLICIT_SHA",
        base_commit=base_commit,
        allowed_scope=scope,
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
        content_hash=content_hash,
        compiled_by="compiler:TaskContractCompiler",
    )
    db_session.add(contract)
    await db_session.flush()
    task.current_contract_id = contract.id
    task.status = TaskStatus.READY
    await db_session.flush()

    execution = await AdmissionService().admit_task(db_session, task.id, ctx)
    execution_id = execution.id
    worker = ExecutionWorker(worker_id=f"wf-ic-live-{uuid.uuid4().hex[:6]}")
    for _ in range(120):
        await worker.run_once(db_session, ctx)
        execution = await db_session.get(Execution, execution_id)
        assert execution is not None
        if execution.status in {ExecutionStatus.COMPLETED, ExecutionStatus.FAILED}:
            break
    assert execution.status == ExecutionStatus.COMPLETED, execution.failure_detail


async def _run_forge_live_task_with_retry(
    db_session,
    ctx: CommandContext,
    *,
    attempts: int = 3,
    **kwargs: object,
) -> None:
    last_error: AssertionError | None = None
    content_hash = str(kwargs.pop("content_hash"))
    for attempt in range(attempts):
        try:
            await _run_forge_live_task(
                db_session,
                ctx,
                content_hash=f"{content_hash}-try{attempt}",
                **kwargs,  # type: ignore[arg-type]
            )
            return
        except AssertionError as exc:
            last_error = exc
        except Exception as exc:
            from sqlalchemy.exc import PendingRollbackError

            if isinstance(exc, PendingRollbackError):
                with suppress(Exception):
                    await db_session.rollback()
            last_error = AssertionError(str(exc))
    assert last_error is not None
    raise last_error


@pytest.mark.asyncio
async def test_live_forge_and_deterministic_candidates_integration_ready(
    db_session,
    system_actor,
) -> None:
    if os.getenv("LLM_LIVE_TESTS") != "1":
        pytest.skip("LLM_LIVE_TESTS=1 required")
    if not any_live_provider_configured():
        pytest.skip("No live provider API key configured")

    fixture_root = Path(__file__).resolve().parents[2] / "fixtures" / "repos" / "mini_python"
    if not fixture_root.exists():
        pytest.skip("mini_python fixture missing")

    work_origin = (
        Path(os.environ.get("OLYMPUS_WORKSPACE_ROOT", "/tmp"))
        / f"wf-ic-live-{uuid.uuid4().hex[:8]}"
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

    ctx = CommandContext(actor=system_actor, correlation_id="wf-ic-live")
    from core.domain.projects.models import Project

    project = Project(key="wf-ic-live", name="WF IC Live")
    db_session.add(project)
    await db_session.flush()

    repo = await RepositoryService().register_external(
        db_session,
        project.id,
        "mini-wf-ic",
        RepositoryProvider.LOCAL,
        f"file://{work_origin.resolve()}",
        "main",
        "none:",
        ctx,
    )
    await RepositoryMaterializationService().materialize_external(db_session, repo.id, ctx)
    await db_session.refresh(repo)
    base_sha = repo.canonical_commit
    assert base_sha is not None

    from core.intelligence.code_index.canonical_service import CanonicalIndexService

    await CanonicalIndexService().promote_repository_snapshot(db_session, repo.id, base_sha, ctx)

    cycle = DeliveryCycle(
        project_id=project.id,
        key="C-WF-IC-LIVE",
        type=DeliveryCycleType.FEATURE_CHANGE,
        objective="live ic precursor",
        state="DEVELOPMENT",
        state_version=0,
        opened_by_actor_id=system_actor.id,
        repository_id=repo.id,
        base_sha=base_sha,
    )
    db_session.add(cycle)
    await db_session.flush()

    await _run_forge_live_task_with_retry(
        db_session,
        ctx,
        cycle_id=cycle.id,
        repository_id=repo.id,
        base_commit=base_sha,
        title="Add greet module",
        objective=(
            "Create only mini/greet.py with def greet(name: str) -> str and "
            "tests/test_greet.py with one pytest. Do not edit mini/core.py or other files."
        ),
        scope=["mini/greet.py", "tests/test_greet.py", "mini/__init__.py"],
        content_hash="wf-ic-live-1",
    )
    fixture = IntegrationFixture(
        project=project,
        repository=repo,
        cycle=cycle,
        base_sha=base_sha,
    )
    det_bundle = await add_implementation_code_task(
        db_session,
        ctx,
        fixture,
        title="Add trim module (deterministic)",
        key_prefix="wficdet",
    )
    await commit_files_in_worktree(
        db_session,
        ctx,
        det_bundle,
        {
            "mini/trim.py": "def trim(text: str) -> str:\n    return text.strip()\n",
            "tests/test_trim.py": (
                "from mini.trim import trim\n\ndef test_trim():\n    assert trim(' x ') == 'x'\n"
            ),
        },
        message="feat: trim module",
        principal_symbols=["trim"],
    )

    ic = await IntegrationService().create(db_session, cycle.id, ctx)
    ic = await run_worker_until_ic_settled(db_session, ctx, ic.id)
    assert ic.status == ICStatus.READY, (ic.status, ic.failure_detail)
    assert ic.integrated_sha is not None

    await db_session.refresh(repo)
    assert repo.canonical_commit == ic.integrated_sha

    pointer = await db_session.get(RepositoryIndexPointer, repo.id)
    assert pointer is not None and pointer.canonical_index_version_id is not None

    from core.domain.candidate_commits.models import CandidateCommit
    from core.domain.tasks.models import Task

    candidates = (
        await db_session.execute(
            select(CandidateCommit)
            .join(Task, CandidateCommit.task_id == Task.id)
            .where(Task.delivery_cycle_id == cycle.id)
        )
    ).scalars()
    assert len(list(candidates)) >= 2
