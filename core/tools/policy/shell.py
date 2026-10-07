"""Shell argv hardening beyond baseline policy."""

from __future__ import annotations

import re
from pathlib import Path

from core.tools.shell_policy import ShellPolicy, load_shell_policy, validate_shell_argv

_FORBIDDEN_GIT_FLAGS = re.compile(r"(-c|--config|--exec-path|--git-dir|--work-tree)", re.I)
_ENV_INJECTION = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*=")


def validate_shell_invocation(
    category: str,
    argv: list[str],
    policy: ShellPolicy | None = None,
) -> None:
    validate_shell_argv(category, argv, policy)
    pol = policy or load_shell_policy()
    if not argv:
        raise ValueError("empty argv")
    binary = Path(argv[0]).name
    if binary == "git":
        for part in argv[1:]:
            if _FORBIDDEN_GIT_FLAGS.search(part):
                raise ValueError("git config/hooks injection denied")
            if part.startswith("-c"):
                raise ValueError("git -c denied")
    for part in argv:
        if _ENV_INJECTION.match(part):
            raise ValueError("env injection in argv denied")
        if part.startswith("$(") or "`" in part:
            raise ValueError("command substitution denied")
    _ = pol
