from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Protocol

from core.domain.executions.models import Execution, ExecutionSnapshot

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession
from core.domain.task_contracts.schemas import TaskContractBody


@dataclass
class ExecutionContext:
    execution: Execution
    snapshot: ExecutionSnapshot
    contract: TaskContractBody
    lease_id: uuid.UUID
    worker_id: str
    contract_payload: dict[str, Any] | None = None
    continuation: dict[str, Any] | None = None
    session: AsyncSession | None = None


@dataclass
class ExecutorOutcome:
    status: str
    output: dict[str, Any] | None = None
    artifacts: list[dict[str, Any]] = field(default_factory=list)
    checkpoint: dict[str, Any] | None = None
    runtime_metadata: dict[str, Any] = field(default_factory=dict)
    model_call_ids: list[uuid.UUID] = field(default_factory=list)
    error_code: str | None = None
    error_message: str | None = None


class Executor(Protocol):
    async def execute(self, ctx: ExecutionContext) -> ExecutorOutcome: ...
