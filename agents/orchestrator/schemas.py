from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class ProposedCommand(BaseModel):
    model_config = ConfigDict(extra="forbid")

    command: str
    target_ref: str
    args: dict[str, object] = Field(default_factory=dict)
    rationale: str


class ClarificationAnswerDraft(BaseModel):
    model_config = ConfigDict(extra="forbid")

    clarification_id: str
    answer: str


class OrchestratorTurn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    intent: Literal[
        "EXPLAIN",
        "ANSWER_CLARIFICATION",
        "PROPOSE_COMMAND",
        "NAVIGATE",
        "OUT_OF_SCOPE",
    ]
    message: str
    refs: list[str] = Field(default_factory=list)
    proposed_command: ProposedCommand | None = None
    clarification_answer_draft: ClarificationAnswerDraft | None = None
    navigate_to: str | None = None
