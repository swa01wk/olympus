from __future__ import annotations

from pathlib import Path

import pytest
from core.execution.sandbox import SandboxConfig, get_sandbox_runner
from core.tools.shell_policy import load_shell_policy, scrubbed_env

pytestmark = pytest.mark.security


@pytest.mark.asyncio
async def test_sandbox_echo(tmp_path: Path) -> None:
    policy = load_shell_policy()
    runner = get_sandbox_runner()
    result = await runner.run(
        SandboxConfig(
            workspace_path=tmp_path,
            argv=["python", "-c", "print('ok')"],
            env=scrubbed_env(),
            timeout_s=30,
            max_output_bytes=policy.max_output_bytes,
        )
    )
    assert result.returncode == 0
    assert "ok" in result.stdout
