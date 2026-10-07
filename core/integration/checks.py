"""Deterministic integration checks (compileall + pytest)."""

from __future__ import annotations

import os
import subprocess
import sys
import tomllib
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class IntegrationCheckResult:
    ok: bool
    compileall_rc: int
    collect_rc: int
    pytest_rc: int
    output: str


def _integration_pytest_argv(worktree_path: Path) -> list[str]:
    pyproject = worktree_path / "pyproject.toml"
    if pyproject.is_file():
        try:
            data = tomllib.loads(pyproject.read_text(encoding="utf-8"))
        except tomllib.TOMLDecodeError:
            data = {}
        raw = (data.get("tool") or {}).get("olympus") or {}
        extra = raw.get("integration_pytest_args")
        if isinstance(extra, list) and extra:
            return ["-q", *[str(x) for x in extra[:20]]]
    return ["-q"]


def _pytest_isolation_args(worktree_path: Path) -> list[str]:
    root = str(worktree_path.resolve())
    return ["--rootdir", root, "--confcutdir", root]


def run_integration_checks(worktree_path: Path, *, timeout_s: int = 600) -> IntegrationCheckResult:
    chunks: list[str] = []
    pytest_argv = _integration_pytest_argv(worktree_path)
    isolation = _pytest_isolation_args(worktree_path)
    collect_argv = [*isolation, "--collect-only", "-q", *pytest_argv[1:]]
    env = os.environ.copy()
    env["PYTHONPATH"] = str(worktree_path.resolve())
    env["PYTEST_DISABLE_PLUGIN_AUTOLOAD"] = "1"
    env.pop("PYTEST_ADDOPTS", None)
    python = sys.executable
    compileall = subprocess.run(
        [python, "-m", "compileall", "-q", "."],
        cwd=worktree_path,
        capture_output=True,
        text=True,
        timeout=timeout_s,
        env=env,
    )
    chunks.append(f"compileall rc={compileall.returncode}\n{compileall.stdout}{compileall.stderr}")
    collect = subprocess.run(
        [python, "-m", "pytest", *collect_argv],
        cwd=worktree_path,
        capture_output=True,
        text=True,
        timeout=timeout_s,
        env=env,
    )
    chunks.append(f"collect rc={collect.returncode}\n{collect.stdout}{collect.stderr}")
    pytest_run = subprocess.run(
        [python, "-m", "pytest", *isolation, *pytest_argv],
        cwd=worktree_path,
        capture_output=True,
        text=True,
        timeout=timeout_s,
        env=env,
    )
    chunks.append(f"pytest rc={pytest_run.returncode}\n{pytest_run.stdout}{pytest_run.stderr}")
    ok = (
        compileall.returncode == 0
        and collect.returncode in (0, 5)
        and pytest_run.returncode in (0, 5)
    )
    return IntegrationCheckResult(
        ok=ok,
        compileall_rc=compileall.returncode,
        collect_rc=collect.returncode,
        pytest_rc=pytest_run.returncode,
        output="\n---\n".join(chunks),
    )
