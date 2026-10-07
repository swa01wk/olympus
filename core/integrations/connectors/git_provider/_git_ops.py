"""Shared git operations for remote providers (uses GitCli + credential env)."""

from __future__ import annotations

from pathlib import Path

from core.execution.worktrees.git import GitCli
from core.integrations.connectors.base import ConnectorAction, ConnectorResult
from core.repositories.credentials import ResolvedCredential
from core.repositories.workspace_locator import WorkspaceLocator


def _git(credential: ResolvedCredential | None) -> GitCli:
    if credential is None:
        return GitCli()
    return GitCli(credential_env={"OLYMPUS_GIT_CREDENTIAL": credential.secret.get_secret_value()})


def _logical_path(locator: WorkspaceLocator, logical: str) -> Path:
    return locator.resolve("LOCAL_FILESYSTEM", logical)


def action_fetch(
    locator: WorkspaceLocator,
    action: ConnectorAction,
    credential: ResolvedCredential | None,
) -> ConnectorResult:
    logical = str(action.inputs["logical_location"])
    remote = str(action.inputs.get("remote", "origin"))
    path = _logical_path(locator, logical)
    git = _git(credential)
    result = git.run(["fetch", "--prune", remote], git_dir=path, check=False)
    if result.returncode != 0:
        return ConnectorResult(
            status="FAILED_RETRYABLE",
            error_class="GIT_FETCH_FAILED",
            error_detail=result.stderr[:500],
        )
    return ConnectorResult(status="SUCCEEDED", normalized_result={"fetched": remote})


def action_push_branch(
    locator: WorkspaceLocator,
    action: ConnectorAction,
    credential: ResolvedCredential | None,
) -> ConnectorResult:
    logical = str(action.inputs["logical_location"])
    ref = str(action.inputs["ref"])
    remote = str(action.inputs.get("remote", "origin"))
    if not ref.startswith("refs/heads/olympus/"):
        return ConnectorResult(
            status="FAILED_FINAL",
            error_class="PROTECTED_REF",
            error_detail="Only olympus/* branches may be pushed by agents",
        )
    branch = ref.removeprefix("refs/heads/")
    path = _logical_path(locator, logical)
    git = _git(credential)
    result = git.run(["push", remote, f"{branch}:{branch}"], git_dir=path, check=False)
    if result.returncode != 0:
        detail = result.stderr[:500]
        if "401" in detail or "403" in detail:
            return ConnectorResult(status="FAILED_FINAL", error_class="AUTH", error_detail=detail)
        return ConnectorResult(
            status="FAILED_RETRYABLE", error_class="GIT_PUSH_FAILED", error_detail=detail
        )
    sha = git.run(["rev-parse", ref], git_dir=path).stdout.strip()
    return ConnectorResult(
        status="SUCCEEDED",
        normalized_result={"ref": ref, "sha": sha},
        external_ref=f"{remote}/{branch}",
    )


def _push_remote(action: ConnectorAction) -> str:
    """Remote name (e.g. origin) or explicit URL for first attach_remote push."""
    url = action.inputs.get("remote_url")
    if url:
        return str(url)
    return str(action.inputs.get("remote", "origin"))


def action_push_release(
    locator: WorkspaceLocator,
    action: ConnectorAction,
    credential: ResolvedCredential | None,
) -> ConnectorResult:
    logical = str(action.inputs["logical_location"])
    branch = str(action.inputs["branch"])
    sha = str(action.inputs["sha"])
    tag = str(action.inputs["tag"])
    remote = _push_remote(action)
    path = _logical_path(locator, logical)
    git = _git(credential)
    ff = git.run(
        ["push", remote, f"{sha}:refs/heads/{branch}"],
        git_dir=path,
        check=False,
    )
    if ff.returncode != 0:
        return ConnectorResult(
            status="FAILED_RETRYABLE",
            error_class="GIT_PUSH_FAILED",
            error_detail=ff.stderr[:500],
        )
    tag_ref = f"refs/tags/{tag}"
    if git.run(["rev-parse", tag_ref], git_dir=path, check=False).returncode == 0:
        tag_spec = tag_ref
    else:
        tag_spec = f"{sha}:refs/tags/{tag}"
    tag_r = git.run(["push", remote, tag_spec], git_dir=path, check=False)
    if tag_r.returncode != 0:
        return ConnectorResult(
            status="FAILED_RETRYABLE",
            error_class="GIT_TAG_PUSH_FAILED",
            error_detail=tag_r.stderr[:500],
        )
    return ConnectorResult(
        status="SUCCEEDED",
        normalized_result={"branch": branch, "sha": sha, "tag": tag},
        external_ref=f"{remote}/{branch}",
    )


def action_clone(
    locator: WorkspaceLocator,
    action: ConnectorAction,
    credential: ResolvedCredential | None,
) -> ConnectorResult:
    logical = str(action.inputs["logical_location"])
    remote_url = str(action.inputs["remote_url"])
    dest = _logical_path(locator, logical)
    dest.parent.mkdir(parents=True, exist_ok=True)
    git = _git(credential)
    if dest.exists():
        return ConnectorResult(status="SUCCEEDED", normalized_result={"cloned": False})
    result = git.run(["clone", "--bare", remote_url, str(dest)], check=False)
    if result.returncode != 0:
        return ConnectorResult(
            status="FAILED_FINAL",
            error_class="CLONE_FAILED",
            error_detail=result.stderr[:500],
        )
    return ConnectorResult(status="SUCCEEDED", normalized_result={"cloned": True})


def reconcile_ref_sha(
    locator: WorkspaceLocator,
    logical: str,
    ref: str,
    expected_sha: str,
    remote: str = "origin",
) -> ConnectorResult:
    path = _logical_path(locator, logical)
    git = GitCli()
    remote_ref = ref.replace("refs/heads/", f"refs/remotes/{remote}/")
    result = git.run(["rev-parse", remote_ref], git_dir=path, check=False)
    if result.returncode != 0:
        return ConnectorResult(status="UNKNOWN", error_class="REF_MISSING")
    actual = result.stdout.strip()
    if actual == expected_sha:
        return ConnectorResult(
            status="SUCCEEDED",
            normalized_result={"sha": actual, "outcome": "CONFIRMED_EXECUTED"},
        )
    return ConnectorResult(
        status="SUCCEEDED",
        normalized_result={"sha": actual, "outcome": "CONFIRMED_NOT_EXECUTED"},
    )
