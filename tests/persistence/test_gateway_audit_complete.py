from __future__ import annotations

import pytest
from core.domain.actions.models import ActionRequest, ActionResult
from core.tools.gateway import ToolGateway
from sqlalchemy import func, select
from tests.fixtures.phase04_harness import (
    seed_code_change_task,
    seed_execution_with_worktree,
    seed_greenfield_repository,
)

pytestmark = pytest.mark.persistence


@pytest.mark.asyncio
async def test_every_gateway_call_persists_request_and_result(
    db_session,
    system_ctx,
) -> None:
    project, repo, sha = await seed_greenfield_repository(
        db_session, system_ctx, project_key="audit"
    )
    fixture = await seed_code_change_task(db_session, system_ctx, project, repo, sha)
    bundle = await seed_execution_with_worktree(db_session, system_ctx, fixture, key_prefix="aud")
    gateway = ToolGateway(db_session)
    calls = [
        ("git.status", {}),
        ("repo.read", {"path": "README.md"}),
        ("git.commit", {"branch": f"olympus/{bundle.execution.key}", "message": "x"}),
    ]
    for tool, params in calls:
        if tool == "git.commit":
            from core.domain.execution_workspaces.models import ExecutionWorkspace
            from core.repositories.workspace_locator import WorkspaceLocator
            from sqlalchemy import select as sa_select

            ws = (
                await db_session.execute(
                    sa_select(ExecutionWorkspace).where(
                        ExecutionWorkspace.execution_id == bundle.execution.id
                    )
                )
            ).scalar_one()
            path = WorkspaceLocator().resolve("LOCAL_FILESYSTEM", ws.logical_location)
            (path / "audit.txt").write_text("1\n", encoding="utf-8")
        result = await gateway.handle(bundle.token, tool, params)
        assert result.status in {"SUCCEEDED", "DENIED", "FAILED"}, (tool, result.denial_reasons)

    req_count = await db_session.scalar(
        select(func.count())
        .select_from(ActionRequest)
        .where(ActionRequest.execution_id == bundle.execution.id)
    )
    res_count = await db_session.scalar(
        select(func.count())
        .select_from(ActionResult)
        .join(ActionRequest, ActionResult.action_request_id == ActionRequest.id)
        .where(ActionRequest.execution_id == bundle.execution.id)
    )
    assert req_count == len(calls)
    assert res_count == len(calls)
