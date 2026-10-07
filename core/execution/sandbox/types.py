from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Protocol


@dataclass(frozen=True)
class SandboxConfig:
    workspace_path: Path
    argv: list[str]
    env: dict[str, str]
    timeout_s: int
    max_output_bytes: int
    network: bool = False


@dataclass(frozen=True)
class SandboxResult:
    returncode: int
    stdout: str
    stderr: str
    timed_out: bool = False


class SandboxRunner(Protocol):
    async def run(self, config: SandboxConfig) -> SandboxResult: ...
