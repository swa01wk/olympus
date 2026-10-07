from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class InboundEventEnvelope(BaseModel):
    model_config = ConfigDict(extra="forbid")

    source_type: str
    source_id: str
    event_id: str
    project_id: str | None = None
    payload: dict[str, Any] = Field(default_factory=dict)
