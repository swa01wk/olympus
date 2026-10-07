"""Git pre-commit hook in execution worktrees — blocks secret patterns."""

from __future__ import annotations

from pathlib import Path

_HOOK = r"""#!/bin/sh
set -e
for f in $(git diff --cached --name-only); do
  [ -f "$f" ] || continue
  if grep -qE 'sk-[A-Za-z0-9]{20,}|ghp_[A-Za-z0-9]{20,}|AKIA[A-Z0-9]{16}' "$f" 2>/dev/null \
    || grep -qE 'BEGIN [A-Z ]+ PRIVATE KEY' "$f" 2>/dev/null; then
    echo "SECRET BLOCKED: $f" >&2
    exit 1
  fi
done
"""


def install_pre_commit_hook(worktree_path: Path) -> None:
    hooks = worktree_path / ".git"
    if hooks.is_file():
        # worktree gitdir pointer
        gitdir = hooks.read_text(encoding="utf-8").split("gitdir:", 1)[-1].strip()
        hooks_dir = Path(gitdir).parent / "hooks"
    else:
        hooks_dir = worktree_path / ".git" / "hooks"
    hooks_dir.mkdir(parents=True, exist_ok=True)
    hook_path = hooks_dir / "pre-commit"
    hook_path.write_text(_HOOK, encoding="utf-8")
    hook_path.chmod(0o755)
