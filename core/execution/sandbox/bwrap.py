"""Linux bubblewrap sandbox for integration/journey workers."""

from __future__ import annotations

import asyncio
import shutil
import subprocess

from core.execution.sandbox.types import SandboxConfig, SandboxResult


def bubblewrap_available() -> bool:
    return shutil.which("bwrap") is not None


class BwrapSandboxRunner:
    async def run(self, config: SandboxConfig) -> SandboxResult:
        if not bubblewrap_available():
            raise RuntimeError("bubblewrap (bwrap) not available")
        ws = config.workspace_path.resolve()
        cmd = [
            "bwrap",
            "--die-with-parent",
            "--unshare-net",
            "--ro-bind",
            str(ws),
            "/work",
            "--tmpfs",
            "/tmp",
            "--chdir",
            "/work",
            "--dev",
            "/dev",
            "--proc",
            "/proc",
            *config.argv,
        ]
        try:
            proc = await asyncio.to_thread(
                subprocess.run,
                cmd,
                capture_output=True,
                text=True,
                timeout=config.timeout_s,
                env={k: v for k, v in config.env.items() if k in {"PATH", "LANG", "HOME"}},
                check=False,
            )
            return SandboxResult(
                returncode=proc.returncode,
                stdout=proc.stdout[: config.max_output_bytes],
                stderr=proc.stderr[: config.max_output_bytes],
            )
        except subprocess.TimeoutExpired:
            return SandboxResult(returncode=-1, stdout="", stderr="", timed_out=True)
