from __future__ import annotations

import subprocess
import uuid

import pytest
from core.commands.context import CommandContext
from core.domain.actors.models import Actor
from core.domain.enums import ClarificationStatus, ExecutionStatus, RepositoryProvider, TaskStatus
from core.domain.executions.models import Execution
from core.domain.task_contracts.schemas import TaskContractBody
from core.domain.task_contracts.service import ContractService
from core.execution.checkpoints import CheckpointService
from core.execution.leases.manager import LeaseManager
from core.execution.resume import ResumeService
from core.execution.service import ExecutionService
from core.execution.snapshots.builder import SnapshotBuilder
from core.repositories.service import RepositoryService
from core.scheduler.admission import AdmissionService
from core.state.transition_service import TransitionService
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from tests.fixtures.execution_harness import seed_ready_task
from tests.fixtures.repositories import materialize_existing_repository

pytestmark = [pytest.mark.workflow, pytest.mark.integration]


@pytest.mark.asyncio
async def test_resume_changed_base_commit_new_execution(async_engine, tmp_path) -> None:
    factory = async_sessionmaker(bind=async_engine, class_=AsyncSession, expire_on_commit=False)
    first_id: uuid.UUID
    task_id: uuid.UUID
    repo_id: uuid.UUID
    clarification_id: uuid.UUID
    actor_id: uuid.UUID
    original_hash: str

    async with factory() as session, session.begin():
        bundle = await seed_ready_task(session, key_prefix="resume-stale")
        origin = tmp_path / "origin"
        origin.mkdir(parents=True, exist_ok=True)
        repo = await RepositoryService().register_external(
            session,
            bundle.project.id,
            "resume-repo",
            RepositoryProvider.LOCAL,
            f"file://{origin.resolve()}",
            "main",
            "none:",
            bundle.ctx,
        )
        head = await materialize_existing_repository(session, repo.id, origin, bundle.ctx)
        repo_id = repo.id
        bundle.cycle.repository_id = repo.id
        bundle.cycle.base_sha = head
        base_body = TaskContractBody.model_validate(bundle.contract.body)
        repo_body = base_body.model_copy(
            update={"repository_id": repo.id, "base_policy": "CYCLE_BASE"}
        )
        contracts = ContractService()
        draft = await contracts.create_draft(
            session, bundle.task.id, repo_body, "resume-test", bundle.ctx
        )
        issued = await contracts.issue(session, draft.id, bundle.ctx)
        bundle.task.current_contract_id = issued.id
        await session.flush()

        ex = await AdmissionService().admit_task(session, bundle.task.id, bundle.ctx)
        first_id = ex.id
        task_id = bundle.task.id
        actor_id = bundle.actor.id
        snapshot = await SnapshotBuilder().build(session, ex)
        original_hash = snapshot.snapshot_hash
        lease = await LeaseManager().claim(session, "resume-w", bundle.ctx)
        assert lease is not None
        await ExecutionService().transition(session, ex.id, "start", bundle.ctx, lease_id=lease.id)
        await TransitionService().transition(
            session,
            "task",
            bundle.task.id,
            TaskStatus.QUEUED.value,
            "start_execution",
            bundle.ctx,
        )
        clarification = await CheckpointService().handle_checkpoint(
            session,
            ex,
            snapshot,
            lease.id,
            question="Which branch?",
            ctx=bundle.ctx,
        )
        clarification_id = clarification.id
        clarification.answer = "main"
        clarification.status = ClarificationStatus.ANSWERED

    origin = tmp_path / "origin"
    (origin / "second.txt").write_text("more\n", encoding="utf-8")
    subprocess.run(["git", "add", "second.txt"], cwd=origin, check=True, capture_output=True)
    subprocess.run(
        ["git", "-c", "user.email=t@t.com", "-c", "user.name=t", "commit", "-m", "second"],
        cwd=origin,
        check=True,
        capture_output=True,
    )
    new_head = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=origin,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()

    async with factory() as session:
        from core.domain.repositories.models import Repository, RepositoryWorkspace
        from core.repositories.workspace_locator import WorkspaceLocator

        repo_row = await session.get(Repository, repo_id)
        assert repo_row is not None and repo_row.workspace_id is not None
        workspace = await session.get(RepositoryWorkspace, repo_row.workspace_id)
        assert workspace is not None
        bare_path = WorkspaceLocator().resolve(
            workspace.storage_backend, workspace.logical_location
        )
        subprocess.run(
            ["git", "remote", "remove", "bare"],
            cwd=origin,
            capture_output=True,
        )
        subprocess.run(
            ["git", "remote", "add", "bare", str(bare_path)],
            cwd=origin,
            check=True,
            capture_output=True,
        )
        subprocess.run(
            ["git", "push", "bare", f"{new_head}:refs/heads/main"],
            cwd=origin,
            check=True,
            capture_output=True,
        )

    async with factory() as session, session.begin():
        from core.domain.delivery_cycles.models import DeliveryCycle
        from core.domain.tasks.models import Task

        task = await session.get(Task, task_id)
        assert task is not None
        cycle = await session.get(DeliveryCycle, task.delivery_cycle_id)
        assert cycle is not None
        cycle.base_sha = new_head
        actor = await session.get(Actor, actor_id)
        ctx = CommandContext(actor=actor, correlation_id="resume-answer")  # type: ignore[arg-type]
        decision = await ResumeService().on_clarification_answered(session, clarification_id, ctx)
        assert decision.action == "NEW_EXECUTION"
        new_id = decision.execution_id
        assert new_id != first_id

    async with factory() as session:
        first = await session.get(Execution, first_id)
        assert first is not None
        assert first.status == ExecutionStatus.STALE
        second = await session.get(Execution, new_id)
        assert second is not None
        assert second.previous_execution_id == first_id
        assert second.attempt_number == 2
        preview = await SnapshotBuilder().preview_hash(session, second)
        assert preview != original_hash
