from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Protocol

from core.runtime.contracts import (
    AgentEvent,
    AgentResumeRequest,
    AgentRunRequest,
    AgentRunResult,
)


class AgentRuntime(Protocol):
    async def run(self, request: AgentRunRequest) -> AgentRunResult: ...

    async def resume(self, request: AgentResumeRequest) -> AgentRunResult: ...

    async def cancel(self, run_id: str) -> None: ...

    async def stream(self, run_id: str) -> AsyncIterator[AgentEvent]: ...
