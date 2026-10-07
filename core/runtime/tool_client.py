from __future__ import annotations

from typing import Protocol

from core.runtime.contracts import ToolResult
from core.runtime.errors import RuntimeError as OlympusRuntimeError


class ToolGatewayClient(Protocol):
    async def request(self, tool: str, params: dict[str, object]) -> ToolResult: ...


class DenyAllToolGateway:
    async def request(self, tool: str, params: dict[str, object]) -> ToolResult:
        raise OlympusRuntimeError(
            code="TOOL_DENIED",
            message=f"Tool gateway denied request for {tool}",
            details={"tool": tool, "params": params},
        )
