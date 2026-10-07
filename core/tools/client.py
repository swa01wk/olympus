from __future__ import annotations

import json

from sqlalchemy.ext.asyncio import AsyncSession

from core.runtime.contracts import ToolResult
from core.tools.gateway import ToolGateway


class GatewayToolClient:
    """Binds an execution-scoped token to ToolGateway.handle."""

    def __init__(
        self,
        session: AsyncSession,
        token: str,
        *,
        tool_call_id_prefix: str = "tc",
    ) -> None:
        self._session = session
        self._token = token
        self._prefix = tool_call_id_prefix
        self._seq = 0

    async def request(self, tool: str, params: dict[str, object]) -> ToolResult:
        self._seq += 1
        gateway = ToolGateway(self._session)
        result = await gateway.handle(self._token, tool, dict(params))
        if result.status == "DENIED":
            return ToolResult(
                tool_call_id=f"{self._prefix}-{self._seq}",
                content=json.dumps({"denied": result.denial_reasons}),
                is_error=True,
            )
        if result.status == "FAILED":
            return ToolResult(
                tool_call_id=f"{self._prefix}-{self._seq}",
                content=json.dumps({"error": result.error}),
                is_error=True,
            )
        if result.status == "PENDING_APPROVAL":
            return ToolResult(
                tool_call_id=f"{self._prefix}-{self._seq}",
                content=json.dumps({"pending_approval": result.denial_reasons}),
                is_error=True,
            )
        return ToolResult(
            tool_call_id=f"{self._prefix}-{self._seq}",
            content=json.dumps(result.output or {}),
            is_error=False,
        )
