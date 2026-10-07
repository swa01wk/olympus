"""Managed Git CLI wrapper with allowlisted subcommands and scrubbed environment."""

from __future__ import annotations

import os
import subprocess
from dataclasses import dataclass
from pathlib import Path

ALLOWED_SUBCOMMANDS = frozenset(
    {
        "init",
        "clone",
        "fetch",
        "worktree",
        "checkout",
        "switch",
        "branch",
        "add",
        "commit",
        "diff",
        "status",
        "rev-parse",
        "log",
        "show",
        "merge",
        "merge-base",
        "tag",
        "update-ref",
        "cat-file",
        "ls-files",
        "ls-tree",
        "symbolic-ref",
        "fsck",
        "count-objects",
        "for-each-ref",
        "rev-list",
        "config",
        "push",
        "remote",
    }
)

DEFAULT_TIMEOUT_S = 120
MAX_OUTPUT_BYTES = 2_000_000


@dataclass(frozen=True)
class GitRunResult:
    returncode: int
    stdout: str
    stderr: str


class GitCliError(Exception):
    def __init__(self, message: str, *, result: GitRunResult | None = None) -> None:
        super().__init__(message)
        self.result = result


def _subcommand_from_args(args: list[str]) -> str:
    idx = 0
    while idx < len(args):
        if args[idx] == "-c":
            idx += 2
            continue
        return args[idx]
    raise GitCliError("git subcommand missing")


class GitCli:
    def __init__(
        self,
        *,
        timeout_s: float = DEFAULT_TIMEOUT_S,
        max_output_bytes: int = MAX_OUTPUT_BYTES,
        credential_env: dict[str, str] | None = None,
        askpass_helper: Path | None = None,
    ) -> None:
        self._timeout_s = timeout_s
        self._max_output_bytes = max_output_bytes
        self._credential_env = credential_env or {}
        self._askpass_helper = askpass_helper

    def run(
        self,
        args: list[str],
        *,
        cwd: Path | None = None,
        git_dir: Path | None = None,
        check: bool = True,
    ) -> GitRunResult:
        subcommand = _subcommand_from_args(args)
        if subcommand not in ALLOWED_SUBCOMMANDS:
            raise GitCliError(f"git subcommand not allowed: {subcommand}")
        cmd: list[str] = ["git"]
        if git_dir is not None:
            cmd.extend(["--git-dir", str(git_dir)])
        cmd.extend(args)
        env = self._scrubbed_env()
        env.update(self._credential_env)
        askpass = self._askpass_helper
        if askpass is None and env.get("OLYMPUS_GIT_CREDENTIAL"):
            askpass = Path(__file__).with_name("git_askpass.py")
        if askpass is not None:
            env["GIT_ASKPASS"] = str(askpass)
            env["GIT_TERMINAL_PROMPT"] = "0"
        proc = subprocess.run(
            cmd,
            cwd=str(cwd) if cwd else None,
            capture_output=True,
            timeout=self._timeout_s,
            env=env,
            text=True,
            check=False,
        )
        stdout = proc.stdout[: self._max_output_bytes]
        stderr = proc.stderr[: self._max_output_bytes]
        result = GitRunResult(returncode=proc.returncode, stdout=stdout, stderr=stderr)
        if check and proc.returncode != 0:
            raise GitCliError(
                f"git {' '.join(args)} failed: {stderr.strip() or stdout.strip()}",
                result=result,
            )
        return result

    def _scrubbed_env(self) -> dict[str, str]:
        env = {
            "PATH": os.environ.get("PATH", ""),
            "HOME": os.environ.get("HOME", "/tmp"),
            "LANG": "C.UTF-8",
            "GIT_CONFIG_NOSYSTEM": "1",
            "GIT_CONFIG_GLOBAL": "/dev/null",
        }
        return env

    @staticmethod
    def hook_disabled_config_args() -> list[str]:
        return ["-c", "core.hooksPath=/dev/null"]


def resolve_git_metadata_dir(worktree_path: Path) -> Path:
    """Directory that holds ``info/exclude`` (linked worktree gitdir or ``.git/``)."""
    git_entry = worktree_path / ".git"
    if git_entry.is_file():
        for line in git_entry.read_text(encoding="utf-8").splitlines():
            stripped = line.strip()
            if stripped.startswith("gitdir:"):
                return Path(stripped.split(":", 1)[1].strip())
    if git_entry.is_dir():
        return git_entry
    raise GitCliError(f"not a git worktree: {worktree_path}")
