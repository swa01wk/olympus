from __future__ import annotations

import uuid
from dataclasses import dataclass
from pathlib import Path

from sqlalchemy.ext.asyncio import AsyncSession

from core.domain.task_contracts.schemas import TaskContractBody


@dataclass
class ToolExecutionContext:
    session: AsyncSession
    execution_id: uuid.UUID
    task_id: uuid.UUID
    delivery_cycle_id: uuid.UUID
    project_id: uuid.UUID
    repository_id: uuid.UUID | None
    workspace_path: Path | None
    workspace_branch: str | None
    contract: TaskContractBody | None
    task_contract_id: uuid.UUID | None
    task_contract_version: int | None
    execution_key: str
    correlation_id: str
    actor_id: uuid.UUID | None = None
