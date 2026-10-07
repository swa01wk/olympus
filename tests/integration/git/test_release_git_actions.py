"""Git fast-forward and tag actions for release (Phase 10)."""

from __future__ import annotations

import tempfile
import uuid
from pathlib import Path

import pytest
from core.execution.worktrees.git import GitCli
from core.integrations.connectors.base import ConnectorAction
from core.integrations.connectors.git_local import GitLocalConnector

pytestmark = [pytest.mark.integration, pytest.mark.git]


async def _bare_repo_with_main(logical: str) -> GitLocalConnector:
    connector = GitLocalConnector()
    init = ConnectorAction(
        connector="git_local",
        action="init_repository",
        target_resource="repo",
        inputs={"logical_location": logical, "default_branch": "main"},
        idempotency_key=f"init-{logical}",
        correlation_id="test",
        expected_result_schema="InitResult",
    )
    assert (await connector.execute(init)).status == "SUCCEEDED"
    baseline = ConnectorAction(
        connector="git_local",
        action="baseline_commit",
        target_resource="repo",
        inputs={
            "logical_location": logical,
            "default_branch": "main",
            "files": {"README.md": "x\n"},
            "message": "init",
        },
        idempotency_key=f"base-{logical}",
        correlation_id="test",
        expected_result_schema="BaselineResult",
    )
    assert (await connector.execute(baseline)).status == "SUCCEEDED"
    return connector


def _push_empty_commit(git_dir: Path, branch: str, message: str) -> str:
    git = GitCli()
    with tempfile.TemporaryDirectory() as tmp:
        src = Path(tmp) / "src"
        src.mkdir()
        git.run(GitCli.hook_disabled_config_args() + ["clone", str(git_dir), str(src)], check=True)
        git.run(["checkout", branch], cwd=src, check=True)
        git.run(["commit", "--allow-empty", "-m", message], cwd=src, check=True)
        sha = git.run(["rev-parse", "HEAD"], cwd=src, check=True).stdout.strip()
        git.run(
            GitCli.hook_disabled_config_args() + ["push", "origin", branch],
            cwd=src,
            check=True,
        )
        return sha


@pytest.mark.asyncio
async def test_fast_forward_ref_and_tag() -> None:
    logical = f"projects/test-release-{uuid.uuid4().hex}/repo"
    connector = await _bare_repo_with_main(logical)
    git_dir = connector._git_dir(logical)
    base = connector._git.run(["rev-parse", "main"], git_dir=git_dir, check=True).stdout.strip()
    target = _push_empty_commit(git_dir, "main", "ahead")
    connector._git.run(["update-ref", "refs/heads/main", base], git_dir=git_dir, check=True)
    ff = ConnectorAction(
        connector="git_local",
        action="fast_forward_ref",
        target_resource="repo",
        inputs={"logical_location": logical, "ref": "refs/heads/main", "target_sha": target},
        idempotency_key="ff-test",
        correlation_id="test",
        expected_result_schema="FastForwardResult",
    )
    result = await connector.execute(ff)
    assert result.status == "SUCCEEDED"
    head = connector._git.run(["rev-parse", "main"], git_dir=git_dir, check=True).stdout.strip()
    assert head == target
    tag_action = ConnectorAction(
        connector="git_local",
        action="create_tag",
        target_resource="repo",
        inputs={"logical_location": logical, "tag": "olympus/release/R1", "target_sha": target},
        idempotency_key="tag-test",
        correlation_id="test",
        expected_result_schema="CreateTagResult",
    )
    assert (await connector.execute(tag_action)).status == "SUCCEEDED"


def _push_new_branch(git_dir: Path, branch: str, message: str) -> str:
    git = GitCli()
    with tempfile.TemporaryDirectory() as tmp:
        src = Path(tmp) / "src"
        src.mkdir()
        git.run(GitCli.hook_disabled_config_args() + ["clone", str(git_dir), str(src)], check=True)
        git.run(["checkout", "-b", branch], cwd=src, check=True)
        git.run(["commit", "--allow-empty", "-m", message], cwd=src, check=True)
        sha = git.run(["rev-parse", "HEAD"], cwd=src, check=True).stdout.strip()
        git.run(
            GitCli.hook_disabled_config_args() + ["push", "origin", f"HEAD:{branch}"],
            cwd=src,
            check=True,
        )
        return sha


@pytest.mark.asyncio
async def test_fast_forward_rejects_non_ancestor() -> None:
    logical = f"projects/test-release-{uuid.uuid4().hex}/repo"
    connector = await _bare_repo_with_main(logical)
    git_dir = connector._git_dir(logical)
    side_sha = _push_new_branch(git_dir, "side", "side")
    _push_empty_commit(git_dir, "main", "main-only")
    ff = ConnectorAction(
        connector="git_local",
        action="fast_forward_ref",
        target_resource="repo",
        inputs={"logical_location": logical, "ref": "refs/heads/main", "target_sha": side_sha},
        idempotency_key="ff-fail",
        correlation_id="test",
        expected_result_schema="FastForwardResult",
    )
    result = await connector.execute(ff)
    assert result.status == "FAILED_FINAL"
    assert result.error_class == "NOT_FAST_FORWARD"
