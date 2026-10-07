from __future__ import annotations

from pathlib import Path

import pytest
from core.execution.sandbox import SandboxConfig, get_sandbox_runner
from core.tools.shell_policy import load_shell_policy, scrubbed_env

pytestmark = pytest.mark.security


@pytest.mark.asyncio
async def test_sandbox_blocks_outbound_network(tmp_path: Path) -> None:
    runner = get_sandbox_runner()
    policy = load_shell_policy()
    script = (
        "import socket\n"
        "s = socket.socket()\n"
        "try:\n"
        "  s.connect(('127.0.0.1', 9))\n"
        "  print('connected')\n"
        "except OSError:\n"
        "  print('blocked')\n"
        "finally:\n"
        "  s.close()\n"
    )
    result = await runner.run(
        SandboxConfig(
            workspace_path=tmp_path,
            argv=["python", "-c", script],
            env=scrubbed_env(),
            timeout_s=30,
            max_output_bytes=policy.max_output_bytes,
        )
    )
    assert result.returncode == 0
    assert "blocked" in result.stdout or "connected" not in result.stdout
