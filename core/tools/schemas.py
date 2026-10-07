from __future__ import annotations

import uuid
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class GatewayToolResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    action_request_id: uuid.UUID
    status: Literal[
        "SUCCEEDED",
        "DENIED",
        "FAILED",
        "PENDING_APPROVAL",
        "RECONCILIATION_REQUIRED",
    ]
    output: dict[str, object] | None = None
    denial_reasons: list[str] = Field(default_factory=list)
    error: str | None = None
