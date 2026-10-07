from __future__ import annotations

import pytest
from core.domain.enums import ActorKind
from core.policy.action_policy import evaluate_action_policy
from core.tools.gateway import ToolGateway
from tests.fixtures.phase04_harness import (
    seed_code_change_task,
    seed_execution_with_worktree,
    seed_greenfield_repository,
)

pytestmark = [pytest.mark.integration]


@pytest.mark.asyncio
async def test_denied_tool_not_in_contract_allowed_actions(db_session, system_ctx) -> None:
    project, repo, sha = await seed_greenfield_repository(
        db_session, system_ctx, project_key="deny-tool"
    )
    fixture = await seed_code_change_task(
        db_session,
        system_ctx,
        project,
        repo,
        sha,
        allowed_actions=["git.status"],
    )
    bundle = await seed_execution_with_worktree(db_session, system_ctx, fixture, key_prefix="dt")
    gateway = ToolGateway(db_session)
    result = await gateway.handle(bundle.token, "repo.write", {"path": "x.txt", "content": "y"})
    assert result.status == "DENIED"
    assert any("allowed_actions" in r for r in (result.denial_reasons or []))


@pytest.mark.asyncio
async def test_denied_tool_not_in_agent_profile(db_session, system_ctx) -> None:
    project, repo, sha = await seed_greenfield_repository(
        db_session, system_ctx, project_key="deny-prof"
    )
    fixture = await seed_code_change_task(
        db_session,
        system_ctx,
        project,
        repo,
        sha,
        allowed_actions=["repo.read", "repo.write", "git.status", "git.commit", "repo.delete"],
    )
    bundle = await seed_execution_with_worktree(db_session, system_ctx, fixture, key_prefix="dp")
    gateway = ToolGateway(db_session)
    result = await gateway.handle(
        bundle.token,
        "repo.delete",
        {"path": "README.md"},
    )
    assert result.status == "DENIED"


@pytest.mark.unit
def test_forge_denied_release_resource() -> None:
    decision = evaluate_action_policy(
        resource="release",
        action="publish",
        tool="release.publish",
        agent_profile="forge.implementation",
        actor_kind=ActorKind.AGENT,
        params={},
        policy_version_id=None,
    )
    assert decision.decision == "DENY"


@pytest.mark.asyncio
async def test_protected_branch_commit_denied(db_session, system_ctx) -> None:
    project, repo, sha = await seed_greenfield_repository(
        db_session, system_ctx, project_key="prot"
    )
    fixture = await seed_code_change_task(db_session, system_ctx, project, repo, sha)
    bundle = await seed_execution_with_worktree(db_session, system_ctx, fixture, key_prefix="prot")
    gateway = ToolGateway(db_session)
    result = await gateway.handle(
        bundle.token,
        "git.commit",
        {"branch": "release/1.0", "message": "nope"},
    )
    assert result.status == "DENIED"
