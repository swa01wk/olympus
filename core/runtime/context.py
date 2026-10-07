from __future__ import annotations

import asyncio
import uuid
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from sqlalchemy.ext.asyncio import AsyncSession

from core.runtime.contracts import AgentRunRequest
from core.runtime.tool_client import ToolGatewayClient

if TYPE_CHECKING:
    from core.runtime.agent_profiles import AgentProfile
    from core.runtime.model_router import ModelRouter


@dataclass
class GraphDeps:
    model_router: ModelRouter
    tool_gateway: ToolGatewayClient
    profile: AgentProfile
    request: AgentRunRequest
    cancel_event: asyncio.Event
    session: AsyncSession | None = None
    model_call_ids: list[uuid.UUID] = field(default_factory=list)
    emit_event: object | None = None
    checkpointer: object | None = None
