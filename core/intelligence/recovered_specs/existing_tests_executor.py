from __future__ import annotations

import tempfile
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.assurance.pytest_node import junit_case_node_id
from core.commands.context import CommandContext
from core.domain.delivery_cycles.models import DeliveryCycle
from core.domain.enums import ActorKind
from core.domain.repositories.models import Repository, RepositoryWorkspace
from core.execution.executors.base import ExecutionContext, ExecutorOutcome
from core.execution.worktrees.manager import WorktreeManager
from core.repositories.workspace_locator import WorkspaceLocator
from core.tools.handlers.test_runner import run_pytest_in_workspace


def _parse_junit_cases(path: Path, workspace: Path) -> list[dict[str, Any]]:
    if not path.is_file():
        return []
    root = ET.parse(path).getroot()
    cases: list[dict[str, Any]] = []
    for case in root.iter("testcase"):
        nodeid = junit_case_node_id(workspace, case.get("classname", ""), case.get("name", ""))
        failed = case.find("failure") is not None or case.find("error") is not None
        cases.append({"nodeid": nodeid, "passed": not failed})
    return cases


async def run_brownfield_existing_tests(
    session: AsyncSession,
    ctx: ExecutionContext,
    command_ctx: CommandContext,
) -> ExecutorOutcome:
    cycle = await session.get(DeliveryCycle, ctx.execution.delivery_cycle_id)
    if cycle is None or cycle.repository_id is None or cycle.base_sha is None:
        return ExecutorOutcome(
            status="FAILED",
            error_code="CYCLE_NOT_READY",
            error_message="Brownfield cycle missing base SHA",
        )
    repo = await session.get(Repository, cycle.repository_id)
    if repo is None:
        return ExecutorOutcome(status="FAILED", error_code="NOT_FOUND", error_message="repo")
    from core.domain.actors.models import Actor

    actor = (
        await session.execute(select(Actor).where(Actor.kind == ActorKind.SYSTEM).limit(1))
    ).scalar_one()
    await WorktreeManager().create_readonly(
        session,
        ctx.execution,
        cycle.repository_id,
        cycle.base_sha,
        actor_id=actor.id,
        correlation_id=str(ctx.execution.id),
        project_id=cycle.project_id,
    )
    from core.domain.execution_workspaces.models import ExecutionWorkspace

    ws = (
        await session.execute(
            select(ExecutionWorkspace).where(ExecutionWorkspace.execution_id == ctx.execution.id)
        )
    ).scalar_one()
    canonical_ws = await session.get(RepositoryWorkspace, repo.workspace_id)
    assert canonical_ws is not None
    wt_path = WorkspaceLocator().resolve(canonical_ws.storage_backend, ws.logical_location)
    with tempfile.TemporaryDirectory() as tmp:
        junit = Path(tmp) / "junit.xml"
        result = await run_pytest_in_workspace(
            wt_path,
            {"runner": "pytest", "args": ["--junitxml=" + str(junit)]},
        )
        cases = _parse_junit_cases(junit, wt_path)
        payload: dict[str, Any] = {
            **result,
            "cases": cases,
            "commit_sha": cycle.base_sha,
        }
        return ExecutorOutcome(status="OUTPUT_PRODUCED", output=payload)
