from core.assurance.schemas import WardenFindingDraft, WardenReview
from pydantic import BaseModel, Field


class RootCauseHypothesis(BaseModel):
    faulty_stable_keys: list[str]
    explanation: str
    confidence: float = Field(ge=0.0, le=1.0)
    fix_outline: str
    regression_risks: list[str] = Field(default_factory=list)
    cited_evidence_ids: list[str] = Field(default_factory=list)


__all__ = ["RootCauseHypothesis", "WardenFindingDraft", "WardenReview"]
