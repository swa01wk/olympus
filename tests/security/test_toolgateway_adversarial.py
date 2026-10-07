from __future__ import annotations

from pathlib import Path

import pytest
from core.tools.policy.paths import (
    PathPolicyViolation,
    normalize_relative_path,
    resolve_in_workspace,
)
from core.tools.policy.shell import validate_shell_invocation
from core.tools.shell_policy import load_shell_policy

pytestmark = pytest.mark.security

_TRAVERSAL_PATHS = [
    "../etc/passwd",
    "..\\windows",
    "/absolute",
    "~/.ssh/id_rsa",
    "foo/../../bar",
    ".git/config",
    "src/.olympus/x",
    "a/../b/../../etc/shadow",
    ".git/HEAD",
    ".olympus/secrets",
    "src/../../../tmp/x",
    "/etc/passwd",
    "~/secrets",
    "foo/bar/../../../outside",
    ".git/objects/pack",
    "nested/../../.git/config",
    "foo/./../../bar",
    "unicode/../etc",
    "src//../outside",
    "x/.git/hooks/pre-push",
    "work/../canonical",
    ".git/logs/HEAD",
    "foo\\..\\bar",
    "..\\..\\windows\\system32",
    "a/b/c/../../../../d",
    ".olympus/../../etc",
    "src/../../.git/config",
    "foo/..\\..\\bar",
]

_SHELL_CASES = [
    (["git", "-c", "core.hooksPath=/tmp", "status"], "git"),
    (["git", "config", "user.email", "x"], "git"),
    (["git", "-c", "user.name=x", "commit"], "git"),
    (["git", "--exec-path=/tmp", "status"], "git"),
    (["pytest", "a;rm"], "metachar"),
    (["pytest", "a&&rm"], "metachar"),
    (["pytest", "a|rm"], "metachar"),
    (["pytest", "`id`"], "metachar"),
    (["pytest", "$(whoami)"], "metachar"),
    (["pytest", "FOO=bar"], "env"),
    (["pytest", "PATH=/tmp:$PATH"], "metachar"),
    (["pytest", "a>out"], "metachar"),
    (["pytest", "a<in"], "metachar"),
]


@pytest.mark.parametrize("path", _TRAVERSAL_PATHS)
def test_path_traversal_denied(path: str) -> None:
    with pytest.raises(PathPolicyViolation):
        normalize_relative_path(path)


@pytest.mark.parametrize("argv,msg", _SHELL_CASES)
def test_shell_hardening(argv: list[str], msg: str) -> None:
    policy = load_shell_policy()
    with pytest.raises(ValueError, match=msg):
        validate_shell_invocation("pytest", argv, policy)


def test_resolve_workspace_symlink_escape(tmp_path: Path) -> None:
    ws = tmp_path / "ws"
    ws.mkdir()
    outside = tmp_path / "outside.txt"
    outside.write_text("x")
    link = ws / "link"
    link.symlink_to(outside)
    with pytest.raises(PathPolicyViolation):
        resolve_in_workspace(ws, "link")
