from __future__ import annotations

import uuid
from typing import Literal

from core.domain.enums import WorkType
from pydantic import BaseModel, ConfigDict


class VersionedRef(BaseModel):
    ref_type: str
    ref_id: uuid.UUID
    version: int | None = None
    key: str | None = None


def parse_task_contract_body(raw: object) -> TaskContractBody:
    """Validate persisted contract JSON, ignoring orchestrator / executor extension keys."""
    if isinstance(raw, dict):
        allowed = set(TaskContractBody.model_fields)
        filtered = {k: v for k, v in raw.items() if k in allowed}
        return TaskContractBody.model_validate(filtered)
    return TaskContractBody.model_validate(raw)


class TaskContractBody(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    objective: str
    work_type: WorkType
    inputs: list[VersionedRef]
    repository_id: uuid.UUID | None = None
    base_policy: Literal["CYCLE_BASE", "DEPENDENCY_INTEGRATION", "EXPLICIT_SHA", "NONE"] = "NONE"
    base_commit: str | None = None
    allowed_scope: list[str] = []
    constraints: list[str] = []
    prohibited_operations: list[str] = []
    allowed_actions: list[str] = []
    required_outputs: list[str] = []
    verification_requirements: list[str] = []
    escalation_rules: dict[str, Literal["REQUIRE_APPROVAL", "ASK_HUMAN", "FAIL"]] = {}
    required_approvals: list[uuid.UUID] = []
    agent_profile: str | None = None
    executor_kind: Literal["AGENT_RUNTIME", "DETERMINISTIC"]
    deterministic_executor: str | None = None
    model_alias: str | None = None
    timeouts: dict[str, int] = {"wall_clock_s": 1800}
    budgets: dict[str, float] = {}
