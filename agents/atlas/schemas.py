from core.planning.schemas import (
    ArchitectureBody,
    ArchitectureProposal,
    ComponentDef,
    ContractDraft,
    DecisionDef,
)
from pydantic import BaseModel, ConfigDict, Field


class ArchitectureDeltaProposal(BaseModel):
    model_config = ConfigDict(extra="forbid")

    changed_components: list[ComponentDef] = Field(default_factory=list)
    added_components: list[ComponentDef] = Field(default_factory=list)
    changed_contracts: list[ContractDraft] = Field(default_factory=list)
    decisions: list[DecisionDef] = Field(default_factory=list)
    rationale: str
    impact_refs: list[str] = Field(default_factory=list)


__all__ = [
    "ArchitectureBody",
    "ArchitectureDeltaProposal",
    "ArchitectureProposal",
    "ComponentDef",
    "ContractDraft",
    "DecisionDef",
]
