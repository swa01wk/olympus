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


@pytest.mark.asyncio
async def test_git_commit_denied_when_protected_test_is_missing(db_session, system_ctx) -> None:
    from core.intelligence.baselines.enums import (
        BaselineActivation,
        BaselineCheckKind,
        BaselineSource,
        BaselineStatus,
    )
    from core.intelligence.baselines.models import BehavioralBaseline

    project, repo, sha = await seed_greenfield_repository(
        db_session, system_ctx, project_key="prot-test"
    )
    db_session.add(
        BehavioralBaseline(
            project_id=project.id,
            lineage_key="BL-TICKET-DEFAULT-OPEN",
            version=1,
            status=BaselineStatus.ACTIVE,
            source=BaselineSource.BROWNFIELD_EXISTING_TEST,
            given="a caller creates a ticket",
            when="POST /tickets",
            then="status OPEN",
            check_kind=BaselineCheckKind.EXISTING_TEST,
            check_ref="tests/test_ticket_service.py::test_create_defaults_open",
            observed_behavior_ids=[],
            exercised_stable_keys=[],
            established_sha=sha,
            activation=BaselineActivation.HUMAN,
        )
    )
    await db_session.flush()
    fixture = await seed_code_change_task(db_session, system_ctx, project, repo, sha)
    bundle = await seed_execution_with_worktree(
        db_session, system_ctx, fixture, key_prefix="prot-test"
    )
    gateway = ToolGateway(db_session)
    await gateway.handle(
        bundle.token,
        "repo.write",
        {
            "path": "tests/test_ticket_service.py",
            "content": "def test_create_ticket_defaults_priority_to_medium():\n    assert True\n",
        },
    )
    result = await gateway.handle(
        bundle.token,
        "git.commit",
        {"branch": f"olympus/{bundle.execution.key}", "message": "rename test"},
    )
    assert result.status == "FAILED"
    assert "protected tests missing" in (result.error or "")


@pytest.mark.asyncio
async def test_second_git_commit_is_refused_without_touching_the_branch(
    db_session, system_ctx
) -> None:
    project, repo, sha = await seed_greenfield_repository(
        db_session, system_ctx, project_key="two-commits"
    )
    fixture = await seed_code_change_task(db_session, system_ctx, project, repo, sha)
    bundle = await seed_execution_with_worktree(
        db_session, system_ctx, fixture, key_prefix="two-commits"
    )
    gateway = ToolGateway(db_session)
    branch = f"olympus/{bundle.execution.key}"

    async def write_and_commit(content: str):  # type: ignore[no-untyped-def]
        await gateway.handle(
            bundle.token, "repo.write", {"path": "app/feature.py", "content": content}
        )
        return await gateway.handle(
            bundle.token, "git.commit", {"branch": branch, "message": "change"}
        )

    first = await write_and_commit("A = 1\n")
    assert first.status == "SUCCEEDED", first.error

    second = await write_and_commit("A = 2\n")
    assert second.status == "FAILED"
    assert "already exists" in (second.error or "")
    # Refused before git ran: the edit is still uncommitted instead of an unrecorded commit.
    status = await gateway.handle(bundle.token, "git.status", {})
    assert "app/feature.py" in str(status.output)


@pytest.mark.asyncio
async def test_unchanged_write_is_flagged_and_empty_commit_is_a_clean_refusal(
    db_session, system_ctx
) -> None:
    project, repo, sha = await seed_greenfield_repository(
        db_session, system_ctx, project_key="noop-write"
    )
    fixture = await seed_code_change_task(db_session, system_ctx, project, repo, sha)
    bundle = await seed_execution_with_worktree(
        db_session, system_ctx, fixture, key_prefix="noop-write"
    )
    gateway = ToolGateway(db_session)
    # Fresh worktree, nothing changed yet: committing is a clean refusal, not a crashed call.
    empty = await gateway.handle(
        bundle.token, "git.commit", {"branch": f"olympus/{bundle.execution.key}", "message": "m"}
    )
    assert empty.status == "FAILED"
    assert "nothing to commit" in (empty.error or "")

    args = {"path": "app/x.py", "content": "X = 1\n"}
    first = await gateway.handle(bundle.token, "repo.write", args)
    assert "unchanged" not in str(first.output)
    again = await gateway.handle(bundle.token, "repo.write", args)
    assert again.status == "SUCCEEDED"
    assert (again.output or {}).get("unchanged") is True
