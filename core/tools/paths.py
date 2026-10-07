"""Path confinement for tool operations within an ExecutionWorkspace."""

from __future__ import annotations

import fnmatch
import os
from pathlib import Path


class PathPolicyViolation(Exception):
    def __init__(self, reason: str) -> None:
        super().__init__(reason)
        self.reason = reason


def resolve_in_workspace(workspace_root: Path, relative_path: str) -> Path:
    if relative_path.startswith("/") or relative_path.startswith("~"):
        raise PathPolicyViolation("absolute paths denied")
    parts_in = Path(relative_path).parts
    if ".." in parts_in or ".git" in parts_in:
        raise PathPolicyViolation("path traversal or .git access denied")
    candidate = (workspace_root / relative_path).resolve()
    root = workspace_root.resolve()
    if root not in candidate.parents and candidate != root:
        raise PathPolicyViolation("path escapes workspace")
    if candidate.exists() and not os.path.samefile(candidate, candidate.resolve()):
        raise PathPolicyViolation("symlink escape")
    rel = candidate.relative_to(root)
    parts = rel.parts
    if parts and parts[0] == ".git":
        raise PathPolicyViolation(".git access denied")
    if ".olympus" in parts:
        raise PathPolicyViolation(".olympus access denied")
    return candidate


def assert_write_scope(path: Path, workspace_root: Path, allowed_scope: list[str]) -> None:
    rel = str(path.relative_to(workspace_root.resolve()))
    if not allowed_scope:
        raise PathPolicyViolation("no allowed_scope configured")
    if any(fnmatch.fnmatch(rel, pattern) for pattern in allowed_scope):
        return
    raise PathPolicyViolation(f"path {rel} outside allowed_scope")


def deny_cross_workspace(
    path: Path,
    *,
    workspace_root: Path,
    canonical_repo: Path | None,
    other_worktrees: list[Path],
) -> None:
    resolved = path.resolve()
    if canonical_repo is not None:
        canon = canonical_repo.resolve()
        ws_root = workspace_root.resolve()
        touches_canonical = canon in resolved.parents or resolved == canon
        if touches_canonical and ws_root != resolved and ws_root not in resolved.parents:
            raise PathPolicyViolation("canonical repository access denied")
