from __future__ import annotations

from pathlib import Path

from core.execution.worktrees.git import GitCli


class GitInspector:
    """Read-only git introspection against a materialized workspace."""

    def __init__(self, git: GitCli | None = None) -> None:
        self._git = git or GitCli()

    def commit_exists(self, path: Path, sha: str) -> bool:
        result = self._git.run(
            ["cat-file", "-e", f"{sha}^{{commit}}"],
            git_dir=path,
            check=False,
        )
        return result.returncode == 0

    def is_ancestor(self, path: Path, ancestor: str, descendant: str) -> bool:
        result = self._git.run(
            ["merge-base", "--is-ancestor", ancestor, descendant],
            git_dir=path,
            check=False,
        )
        return result.returncode == 0

    def resolve_ref(self, path: Path, ref: str) -> str:
        result = self._git.run(["rev-parse", ref], git_dir=path, check=False)
        if result.returncode != 0:
            raise ValueError(f"Cannot resolve ref {ref}")
        return result.stdout.strip()
