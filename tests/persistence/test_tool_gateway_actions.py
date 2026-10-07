from __future__ import annotations

import pytest
from core.domain.actions.models import ActionRequest, ActionResult
from core.execution.worktrees.manager import WorktreeManager
from core.tools.gateway import ToolGateway
from sqlalchemy import func, select
from tests.fixtures.gateway_harness import seed_gateway_execution

pytestmark = pytest.mark.persistence


@pytest.mark.asyncio
async def test_gateway_persists_denied_and_allowed(db_session, system_ctx) -> None:
    from core.domain.projects.models import Project
    from core.repositories.materialization import RepositoryMaterializationService
    from core.repositories.service import RepositoryService

    project = Project(key="gw-persist", name="GW")
    db_session.add(project)
    await db_session.flush()
    repo_svc = RepositoryService()
    repo = await repo_svc.declare_managed(db_session, project.id, system_ctx)
    await RepositoryMaterializationService().provision_managed(db_session, repo.id, system_ctx)
    await db_session.refresh(repo)
    base = repo.canonical_commit
    assert base
    bundle = await seed_gateway_execution(
        db_session,
        repository=repo,
        base_commit=base,
    )
    wt = WorktreeManager()
    await wt.create(
        db_session,
        bundle.execution,
        repo.id,
        base,
        actor_id=bundle.actor.id,
        correlation_id="gw",
        project_id=bundle.project.id,
    )
    gateway = ToolGateway(db_session)
    denied = await gateway.handle(
        bundle.token,
        "git.commit",
        {"branch": "main", "message": "bad"},
    )
    assert denied.status == "DENIED"
    allowed = await gateway.handle(
        bundle.token,
        "git.status",
        {},
    )
    assert allowed.status == "SUCCEEDED"
    count = await db_session.scalar(select(func.count()).select_from(ActionRequest))
    assert count is not None and count >= 2
    results = await db_session.scalar(select(func.count()).select_from(ActionResult))
    assert results is not None and results >= 2
    denied_row = await db_session.get(ActionRequest, denied.action_request_id)
    assert denied_row is not None
    assert denied_row.policy_decision is not None
