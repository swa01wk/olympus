from __future__ import annotations

import json
import uuid

import pytest
from core.commands.context import CommandContext
from core.domain.actors.models import Actor
from core.domain.enums import ActorKind, ActorRole, RepositoryStatus
from core.repositories.service import RepositoryService
from core.state.transition_service import TransitionService
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from tests.fixtures.phase04_harness import (
    seed_code_change_task,
    seed_execution_with_worktree,
    seed_greenfield_repository,
)

pytestmark = [pytest.mark.integration]


@pytest.mark.asyncio
async def test_connectors_api(api_client) -> None:
    resp = await api_client.get("/connectors")
    assert resp.status_code == 200
    body = resp.json()
    assert isinstance(body, list)
    names = {row["name"] for row in body}
    assert "git_local" in names
    validate = await api_client.post("/connectors/git_local/validate")
    assert validate.status_code == 200
    assert validate.json()["ok"] is True


@pytest.mark.asyncio
async def test_repository_materializations_api(api_client, async_engine) -> None:
    factory = async_sessionmaker(bind=async_engine, class_=AsyncSession, expire_on_commit=False)
    repo_id: uuid.UUID
    async with factory() as session, session.begin():
        actor = Actor(kind=ActorKind.SYSTEM, name="mat-api", roles=[ActorRole.SYSTEM.value])
        session.add(actor)
        await session.flush()
        ctx = CommandContext(actor=actor, correlation_id="mat-api")
        _project, repo, _sha = await seed_greenfield_repository(session, ctx, project_key="mat-api")
        repo_id = repo.id

    mats = await api_client.get(f"/repositories/{repo_id}/materializations")
    assert mats.status_code == 200
    attempts = mats.json()
    assert len(attempts) >= 1
    assert attempts[0]["status"] == "SUCCEEDED"
    assert attempts[0]["resulting_sha"]


@pytest.mark.asyncio
async def test_retry_materialization_api(api_client, async_engine) -> None:
    factory = async_sessionmaker(bind=async_engine, class_=AsyncSession, expire_on_commit=False)
    repo_id: uuid.UUID
    async with factory() as session, session.begin():
        actor = Actor(kind=ActorKind.SYSTEM, name="retry-api", roles=[ActorRole.SYSTEM.value])
        session.add(actor)
        await session.flush()
        ctx = CommandContext(actor=actor, correlation_id="retry-api")
        from core.domain.projects.models import Project

        project = Project(key="retry-api", name="Retry API")
        session.add(project)
        await session.flush()
        repo = await RepositoryService().declare_managed(session, project.id, ctx)
        repo_id = repo.id
        await TransitionService().transition(
            session,
            "repository",
            repo.id,
            RepositoryStatus.PROVISIONING.value,
            "materialization_failed",
            ctx,
            payload={"reason": "simulated"},
        )

    retry = await api_client.post(f"/repositories/{repo_id}/commands/retry_materialization")
    assert retry.status_code == 200, retry.text
    assert retry.json()["status"] in ("PROVISIONING", "CLONING")


@pytest.mark.asyncio
async def test_execution_workspace_and_actions_api(
    api_client,
    control_app,
    async_engine,
) -> None:
    factory = async_sessionmaker(bind=async_engine, class_=AsyncSession, expire_on_commit=False)
    execution_id: uuid.UUID
    exec_token: str
    async with factory() as session, session.begin():
        actor = Actor(kind=ActorKind.SYSTEM, name="ws-api", roles=[ActorRole.SYSTEM.value])
        session.add(actor)
        await session.flush()
        ctx = CommandContext(actor=actor, correlation_id="ws-api")
        project, repo, sha = await seed_greenfield_repository(session, ctx, project_key="ws-api")
        fixture = await seed_code_change_task(session, ctx, project, repo, sha)
        bundle = await seed_execution_with_worktree(session, ctx, fixture, key_prefix="ws")
        execution_id = bundle.execution.id
        exec_token = bundle.token

    ws = await api_client.get(f"/executions/{execution_id}/workspace")
    assert ws.status_code == 200, ws.text
    ws_body = ws.json()
    assert ws_body["execution_id"] == str(execution_id)
    assert ws_body["mode"] == "WRITABLE"
    assert "logical_location" in ws_body
    assert "/Users/" not in json.dumps(ws_body)

    alias = await api_client.get(f"/executions/{execution_id}/worktree")
    assert alias.status_code == 200
    assert alias.json()["id"] == ws_body["id"]

    transport = ASGITransport(app=control_app)
    async with AsyncClient(
        transport=transport,
        base_url="http://test",
        headers={"Authorization": f"Bearer {exec_token}"},
    ) as exec_client:
        invoke = await exec_client.post(
            f"/executions/{execution_id}/actions",
            json={"tool": "git.status", "params": {}},
        )
        assert invoke.status_code == 200, invoke.text
        action_id = invoke.json()["id"]
        assert invoke.json()["result_status"] == "SUCCEEDED"

    listed = await api_client.get(f"/executions/{execution_id}/actions")
    assert listed.status_code == 200
    assert any(row["id"] == action_id for row in listed.json())

    detail = await api_client.get(f"/actions/{action_id}")
    assert detail.status_code == 200
    assert detail.json()["tool"] == "git.status"

    empty_calls = await api_client.get(f"/executions/{execution_id}/model-calls")
    assert empty_calls.status_code == 200
    assert empty_calls.json() == []

    async with factory() as session, session.begin():
        from core.domain.model_calls.models import ModelCall

        session.add(
            ModelCall(
                execution_id=execution_id,
                agent_profile="forge.implementation",
                purpose="implementation",
                alias="implementation",
                provider="fake",
                model="fake-1",
                prompt_hash="abc123",
                status="SUCCESS",
                correlation_id="ws-api-mc",
            )
        )

    listed_calls = await api_client.get(f"/executions/{execution_id}/model-calls")
    assert listed_calls.status_code == 200
    calls = listed_calls.json()
    assert len(calls) == 1
    assert calls[0]["model_alias"] == "implementation"
    assert calls[0]["execution_id"] == str(execution_id)

    missing = await api_client.get(f"/executions/{uuid.uuid4()}/model-calls")
    assert missing.status_code == 404


@pytest.mark.asyncio
async def test_candidate_commit_api(
    api_client,
    async_engine,
) -> None:
    from core.domain.execution_workspaces.models import ExecutionWorkspace
    from core.repositories.workspace_locator import WorkspaceLocator
    from core.tools.gateway import ToolGateway
    from sqlalchemy import select

    factory = async_sessionmaker(bind=async_engine, class_=AsyncSession, expire_on_commit=False)
    execution_id: uuid.UUID
    repo_id: uuid.UUID
    canonical_before: str
    async with factory() as session, session.begin():
        actor = Actor(kind=ActorKind.SYSTEM, name="cc-api", roles=[ActorRole.SYSTEM.value])
        session.add(actor)
        await session.flush()
        ctx = CommandContext(actor=actor, correlation_id="cc-api")
        project, repo, sha = await seed_greenfield_repository(session, ctx, project_key="cc-api")
        canonical_before = sha
        repo_id = repo.id
        fixture = await seed_code_change_task(
            session,
            ctx,
            project,
            repo,
            sha,
            allowed_scope=["**"],
        )
        bundle = await seed_execution_with_worktree(session, ctx, fixture, key_prefix="cc")
        execution_id = bundle.execution.id
        ws_row = (
            await session.execute(
                select(ExecutionWorkspace).where(
                    ExecutionWorkspace.execution_id == bundle.execution.id
                )
            )
        ).scalar_one()
        locator = WorkspaceLocator()
        path = locator.resolve("LOCAL_FILESYSTEM", ws_row.logical_location)
        (path / "feature.txt").write_text("x\n", encoding="utf-8")
        gateway = ToolGateway(session)
        branch = f"olympus/{bundle.execution.key}"
        commit = await gateway.handle(
            bundle.token,
            "git.commit",
            {"branch": branch, "message": "feat: api test", "task_contract_ref": "v1"},
        )
        assert commit.status == "SUCCEEDED", commit.denial_reasons

    cc = await api_client.get(f"/executions/{execution_id}/candidate-commit")
    assert cc.status_code == 200, cc.text
    body = cc.json()
    assert body["execution_id"] == str(execution_id)
    assert body["diff_artifact_id"] is not None
    assert body["sha"]

    by_id = await api_client.get(f"/candidate-commits/{body['id']}")
    assert by_id.status_code == 200

    repo_resp = await api_client.get(f"/repositories/{repo_id}")
    assert repo_resp.status_code == 200
    assert repo_resp.json()["canonical_commit"] == canonical_before
