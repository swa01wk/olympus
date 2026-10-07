"""Local dev sandbox — subprocess with limits (local/test only)."""

from __future__ import annotations

import asyncio
import subprocess

from core.execution.sandbox.types import SandboxConfig, SandboxResult


class LocalSandboxRunner:
    async def run(self, config: SandboxConfig) -> SandboxResult:
        try:
            proc = await asyncio.to_thread(
                subprocess.run,
                config.argv,
                cwd=str(config.workspace_path),
                capture_output=True,
                text=True,
                timeout=config.timeout_s,
                env=config.env,
                check=False,
            )
            return SandboxResult(
                returncode=proc.returncode,
                stdout=proc.stdout[: config.max_output_bytes],
                stderr=proc.stderr[: config.max_output_bytes],
            )
        except subprocess.TimeoutExpired:
            return SandboxResult(returncode=-1, stdout="", stderr="", timed_out=True)
