"""Deterministic bug-fix repair for SupportDesk defect fixture (no live Forge)."""

from __future__ import annotations

import uuid

from core.commands.context import CommandContext
from core.domain.candidate_commits.models import CandidateCommit  # noqa: TC001
from core.domain.delivery_cycles.models import DeliveryCycle
from core.domain.enums import ExecutionStatus, TaskContractStatus, TaskOrigin, TaskStatus, WorkType
from core.domain.repositories.models import Repository
from core.domain.sequences import next_project_key
from core.domain.task_contracts.models import TaskContract
from core.domain.tasks.models import Task
from core.execution.artifacts import ArtifactStore
from core.execution.worktrees.git import GitCli
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from tests.fixtures.gateway_harness import GatewayExecutionBundle, seed_gateway_execution
from tests.fixtures.integration_harness import _worktree_path
from tests.journey.greenfield_dev import _ensure_execution_worktree


async def _commit_repair_in_worktree(
    session: AsyncSession,
    bundle: GatewayExecutionBundle,
    task: Task,
    files: dict[str, str],
    *,
    message: str,
) -> str:
    wt = await _worktree_path(session, bundle.execution.id)
    for rel, content in files.items():
        path = wt / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
    git = GitCli()
    branch = f"olympus/{bundle.execution.key}"
    git.run(["add", "-A"], cwd=wt)
    status = git.run(["status", "--porcelain"], cwd=wt).stdout.splitlines()
    changed: list[dict[str, object]] = []
    for line in status:
        if len(line) < 4:
            continue
        code, rel = line[:2], line[3:].strip()
        if " -> " in rel:
            rel = rel.split(" -> ", 1)[1]
        changed.append({"path": rel, "change_type": code.strip(), "additions": 0, "deletions": 0})
    parent = git.run(["rev-parse", "HEAD"], cwd=wt).stdout.strip()
    git.run(
        [
            "-c",
            "user.name=Olympus Forge",
            "-c",
            "user.email=forge@olympus.local",
            "commit",
            "-m",
            message,
            "--trailer",
            f"Olympus-Execution: {bundle.execution.key}",
            "--trailer",
            f"Olympus-Task: {task.id}",
        ],
        cwd=wt,
    )
    sha = git.run(["rev-parse", "HEAD"], cwd=wt).stdout.strip()
    diff = git.run(["diff", f"{parent}..{sha}"], cwd=wt).stdout
    store = ArtifactStore()
    diff_artifact = await store.put(
        session,
        project_id=bundle.repository.project_id,
        delivery_cycle_id=task.delivery_cycle_id,
        execution_id=bundle.execution.id,
        kind="CANDIDATE_DIFF",
        schema_name="GitDiff",
        schema_version="1",
        content=diff.encode("utf-8"),
    )
    cc_key = await next_project_key(
        session, bundle.repository.project_id, "candidate_commit", prefix="CC"
    )
    session.add(
        CandidateCommit(
            key=cc_key,
            execution_id=bundle.execution.id,
            task_id=task.id,
            repository_id=bundle.repository.id,
            branch=branch,
            sha=sha,
            parent_sha=parent,
            base_sha=parent,
            changed_files=changed,
            diff_artifact_id=diff_artifact.id,
            principal_symbols_declared=[],
        )
    )
    task.status = TaskStatus.COMPLETED
    exec_row = bundle.execution
    exec_row.status = ExecutionStatus.COMPLETED
    await session.flush()
    return sha


async def _repair_tasks_missing_candidate_commit(
    session: AsyncSession,
    cycle_id: uuid.UUID,
) -> list[Task]:
    """REPAIR tasks with no CandidateCommit (Forge COMPLETED without git.commit)."""
    tasks = list(
        (
            await session.execute(
                select(Task).where(
                    Task.delivery_cycle_id == cycle_id,
                    Task.origin == TaskOrigin.REPAIR,
                    Task.work_type == WorkType.CODE_CHANGE,
                    Task.status.not_in((TaskStatus.FAILED, TaskStatus.CANCELLED)),
                )
            )
        ).scalars()
    )
    missing: list[Task] = []
    for task in tasks:
        cc = (
            await session.execute(
                select(CandidateCommit.id).where(CandidateCommit.task_id == task.id).limit(1)
            )
        ).scalar_one_or_none()
        if cc is None:
            missing.append(task)
    return missing


async def complete_bug_fix_repair_tasks(
    session: AsyncSession,
    ctx: CommandContext,
    *,
    repository: Repository,
    cycle: DeliveryCycle,
    base_sha: str,
) -> str:
    """Apply CLOSED-ticket 409 fix + regression test; return commit sha."""
    tasks = sorted(
        list(
            (
                await session.execute(
                    select(Task).where(
                        Task.delivery_cycle_id == cycle.id,
                        Task.origin == TaskOrigin.REPAIR,
                        Task.work_type == WorkType.CODE_CHANGE,
                        Task.status.not_in((TaskStatus.FAILED, TaskStatus.CANCELLED)),
                    )
                )
            ).scalars()
        ),
        key=lambda t: t.key,
    )
    if not tasks:
        return base_sha
    last_sha = await _complete_one_repair_task(
        session,
        ctx,
        repository=repository,
        cycle=cycle,
        base_sha=base_sha,
        task=tasks[0],
    )
    for extra in tasks[1:]:
        extra.status = TaskStatus.CANCELLED
    await session.flush()
    return last_sha


async def complete_stale_code_change_tasks(session: AsyncSession, cycle_id: uuid.UUID) -> None:
    """Mark stray non-REPAIR code tasks completed; cancel duplicate REPAIR tasks without CC."""
    origins = (TaskOrigin.IMPLEMENTATION_PLAN, TaskOrigin.REMEDIATION)
    for task in (
        await session.execute(
            select(Task).where(
                Task.delivery_cycle_id == cycle_id,
                Task.work_type == WorkType.CODE_CHANGE,
                Task.origin.in_(origins),
            )
        )
    ).scalars():
        if task.status not in (TaskStatus.COMPLETED, TaskStatus.CANCELLED):
            task.status = TaskStatus.COMPLETED
    repair_tasks = list(
        (
            await session.execute(
                select(Task).where(
                    Task.delivery_cycle_id == cycle_id,
                    Task.work_type == WorkType.CODE_CHANGE,
                    Task.origin == TaskOrigin.REPAIR,
                )
            )
        ).scalars()
    )
    if len(repair_tasks) > 1:
        primary = sorted(repair_tasks, key=lambda t: t.key)[0]
        for task in repair_tasks:
            if task.id != primary.id:
                task.status = TaskStatus.CANCELLED
    done = (TaskStatus.COMPLETED, TaskStatus.CANCELLED)
    for task in (
        await session.execute(
            select(Task).where(
                Task.delivery_cycle_id == cycle_id,
                Task.work_type == WorkType.CODE_CHANGE,
            )
        )
    ).scalars():
        if task.status not in done:
            task.status = TaskStatus.COMPLETED
    await session.flush()


async def _complete_one_repair_task(
    session: AsyncSession,
    ctx: CommandContext,
    *,
    repository: Repository,
    cycle: DeliveryCycle,
    base_sha: str,
    task: Task,
) -> str:
    contract = await session.get(TaskContract, task.current_contract_id)
    assert contract is not None
    key_prefix = f"bf-repair-{task.key.lower()}-{uuid.uuid4().hex[:6]}"
    bundle = await seed_gateway_execution(
        session,
        repository=repository,
        base_commit=base_sha,
        key_prefix=key_prefix,
        existing_task=task,
        existing_contract=contract,
        existing_cycle=cycle,
    )
    await _ensure_execution_worktree(
        session, bundle.execution, repository, base_sha, bundle.ctx, project_id=cycle.project_id
    )
    fixed_service = """from sqlalchemy.orm import Session

from app.models.ticket import Ticket
from app.repositories.ticket_repository import TicketRepository
from app.schemas.ticket import TicketCreate, TicketStatus

TRANSITIONS: dict[str, set[str]] = {
    TicketStatus.OPEN.value: {TicketStatus.CLOSED.value},
    TicketStatus.CLOSED.value: set(),
}


class TicketService:
    def __init__(self, session: Session) -> None:
        self._session = session
        self._repo = TicketRepository(session)

    def create(self, payload: TicketCreate) -> Ticket:
        ticket = Ticket(title=payload.title, status=payload.status.value)
        ticket = self._repo.add(ticket)
        self._session.commit()
        return ticket

    def update_status(self, ticket_id: int, status: TicketStatus) -> Ticket | None:
        ticket = self._session.get(Ticket, ticket_id)
        if ticket is None:
            return None
        allowed = TRANSITIONS.get(ticket.status, set())
        if status.value not in allowed:
            from fastapi import HTTPException

            raise HTTPException(status_code=409, detail="invalid status transition")
        ticket.status = status.value
        self._session.commit()
        return ticket
"""
    regression = """import app.models.ticket  # noqa: F401
from app.db import Base, engine

Base.metadata.create_all(bind=engine)

from app.main import app
from fastapi.testclient import TestClient


def test_closed_ticket_update_returns_409():
    client = TestClient(app, raise_server_exceptions=False)
    created = client.post("/tickets", json={"title": "x"})
    tid = created.json()["id"]
    client.patch(f"/tickets/{tid}", json={"status": "CLOSED"})
    resp = client.patch(f"/tickets/{tid}", json={"status": "OPEN"})
    assert resp.status_code == 409
"""
    sha = await _commit_repair_in_worktree(
        session,
        bundle,
        task,
        {
            "app/services/ticket_service.py": fixed_service,
            "tests/test_closed_ticket_update.py": regression,
        },
        message="fix: reject updates to CLOSED tickets with 409",
    )
    contract.status = TaskContractStatus.ISSUED
    from core.product_model.defects.models import Defect

    defect = (
        await session.execute(select(Defect).where(Defect.delivery_cycle_id == cycle.id))
    ).scalar_one_or_none()
    if defect is not None and defect.triage is not None:
        triage = dict(defect.triage)
        triage["regression_test_path"] = "tests/test_closed_ticket_update.py"
        defect.triage = triage
    await session.flush()
    return sha
