from __future__ import annotations

import subprocess

from core.tools.context import ToolExecutionContext
from core.tools.shell_policy import load_shell_policy, scrubbed_env, validate_shell_argv


async def shell_run(ctx: ToolExecutionContext, params: dict[str, object]) -> dict[str, object]:
    assert ctx.workspace_path
    category = str(params["category"])
    raw_argv = params.get("argv", [])
    if not isinstance(raw_argv, list):
        raise ValueError("argv must be a list")
    argv = [str(x) for x in raw_argv]
    policy = load_shell_policy()
    validate_shell_argv(category, argv, policy)
    proc = subprocess.run(
        argv,
        cwd=str(ctx.workspace_path),
        capture_output=True,
        text=True,
        timeout=policy.timeout_s,
        env=scrubbed_env(),
        check=False,
    )
    stdout = proc.stdout[: policy.max_output_bytes]
    stderr = proc.stderr[: policy.max_output_bytes]
    return {
        "returncode": proc.returncode,
        "stdout": stdout,
        "stderr": stderr,
        "truncated": len(proc.stdout) > policy.max_output_bytes,
    }
