from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from core.domain.task_contracts.schemas import TaskContractBody


class ContextItem(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    kind: Literal["TEXT", "CODE", "SPEC", "FACT", "ARTIFACT", "INSTRUCTION"]
    content: str
    source_ref: str | None = None
    provenance: Literal["DETERMINISTIC", "HUMAN", "AGENT", "SOURCE_DOCUMENT"] | None = None


class ToolSpec(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    name: str
    description: str
    parameters_schema: dict[str, Any]


class ToolCall(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    id: str
    name: str
    arguments: dict[str, Any]


class ToolResult(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    tool_call_id: str
    content: str
    is_error: bool = False


class ModelRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", arbitrary_types_allowed=True)

    purpose: str
    alias: str
    system_instructions: str
    context: list[ContextItem]
    output_schema: type[BaseModel] | None = None
    max_output_tokens: int | None = None
    temperature: float | None = None
    tools: list[ToolSpec] = Field(default_factory=list)
    metadata: dict[str, str] = Field(default_factory=dict)


class ModelResult(BaseModel):
    model_config = ConfigDict(extra="forbid", arbitrary_types_allowed=True)

    parsed_output: BaseModel | None
    raw_text: str | None
    tool_calls: list[ToolCall] = Field(default_factory=list)
    provider: str
    model: str
    input_tokens: int
    output_tokens: int
    latency_ms: int
    provider_request_id: str | None
    model_call_id: uuid.UUID
    cost_usd_estimate: Decimal


class EmbeddingRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    alias: str
    texts: list[str]
    metadata: dict[str, str] = Field(default_factory=dict)


class EmbeddingResult(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    vectors: list[list[float]]
    provider: str
    model: str
    input_tokens: int
    latency_ms: int
    provider_request_id: str | None
    model_call_id: uuid.UUID
    cost_usd_estimate: Decimal


class ProviderRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", arbitrary_types_allowed=True)

    model: str
    system: str
    user_content: str
    max_output_tokens: int
    temperature: float
    output_schema: type[BaseModel] | None = None
    json_schema: dict[str, Any] | None = None
    tools: list[ToolSpec] = Field(default_factory=list)


class ProviderResponse(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    raw_text: str | None
    structured: dict[str, Any] | None
    tool_calls: list[ToolCall] = Field(default_factory=list)
    input_tokens: int
    output_tokens: int
    provider_request_id: str | None


class CheckpointRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    reason: str
    questions: list[str] = Field(default_factory=list)
    continuation: dict[str, Any] = Field(default_factory=dict)


class ArtifactProposal(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    kind: str
    content_ref: str
    metadata: dict[str, str] = Field(default_factory=dict)


class RuntimeErrorInfo(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    code: str
    message: str
    details: dict[str, Any] = Field(default_factory=dict)


class AgentRunRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    run_id: uuid.UUID
    agent_profile: str
    contract: TaskContractBody | None = None
    snapshot: dict[str, Any] | None = None
    context: list[ContextItem]
    workspace_path: str | None = None
    continuation: dict[str, Any] | None = None


class AgentResumeRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    run_id: uuid.UUID
    agent_profile: str
    continuation: dict[str, Any]
    context: list[ContextItem] = Field(default_factory=list)
    contract: TaskContractBody | None = None
    snapshot: dict[str, Any] | None = None
    workspace_path: str | None = None


class AgentRunResult(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    run_id: uuid.UUID
    status: Literal["OUTPUT_PRODUCED", "CHECKPOINT_REQUESTED", "FAILED", "CANCELLED"]
    output: dict[str, Any] | None = None
    output_schema: str | None = None
    checkpoint_request: CheckpointRequest | None = None
    artifacts: list[ArtifactProposal] = Field(default_factory=list)
    model_call_ids: list[uuid.UUID] = Field(default_factory=list)
    runtime_metadata: dict[str, Any] = Field(default_factory=dict)
    error: RuntimeErrorInfo | None = None


class AgentEvent(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    run_id: uuid.UUID
    seq: int
    type: Literal[
        "MODEL_CALL_STARTED",
        "MODEL_CALL_COMPLETED",
        "TOOL_REQUESTED",
        "TOOL_RESULT",
        "PROGRESS",
        "CHECKPOINT_REQUESTED",
        "OUTPUT_PROPOSED",
        "ERROR",
    ]
    payload: dict[str, Any]
    at: datetime
