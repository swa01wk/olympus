from __future__ import annotations

import uuid
from typing import Any, Literal, Protocol

from pydantic import BaseModel, ConfigDict, Field


class ConnectorAction(BaseModel):
    model_config = ConfigDict(extra="forbid")

    connector: str
    action: str
    execution_id: uuid.UUID | None = None
    task_contract_version: str | None = None
    target_resource: str
    inputs: dict[str, Any] = Field(default_factory=dict)
    idempotency_key: str
    correlation_id: str
    policy_context: dict[str, Any] = Field(default_factory=dict)
    expected_result_schema: str


class ConnectorResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: Literal["SUCCEEDED", "FAILED_RETRYABLE", "FAILED_FINAL", "UNKNOWN"]
    normalized_result: dict[str, Any] | None = None
    external_ref: str | None = None
    error_class: str | None = None
    error_detail: str | None = None


class ConnectorHealth(BaseModel):
    model_config = ConfigDict(extra="forbid")

    ok: bool
    message: str = ""


class ReconciliationRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    connector_action_id: uuid.UUID
    connector: str = ""
    action: str = ""
    idempotency_key: str = ""
    correlation_id: str = ""
    expected: dict[str, Any] = Field(default_factory=dict)


class Connector(Protocol):
    name: str
    actions: set[str]

    async def execute(self, action: ConnectorAction) -> ConnectorResult: ...

    async def reconcile(self, request: ReconciliationRequest) -> ConnectorResult: ...

    async def validate(self) -> ConnectorHealth: ...
