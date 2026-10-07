from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from core.domain.task_contracts.schemas import TaskContractBody
from core.execution.executors.agent_runtime_executor import AgentRuntimeExecutor
from core.execution.executors.base import Executor
from core.execution.executors.deterministic import DeterministicExecutor


def select_executor(contract: TaskContractBody, session: AsyncSession) -> Executor:
    if contract.executor_kind == "AGENT_RUNTIME":
        return AgentRuntimeExecutor(session)
    if contract.executor_kind == "DETERMINISTIC":
        return DeterministicExecutor()
    raise ValueError(f"unsupported executor_kind: {contract.executor_kind}")
