from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from core.domain.enums import EvidenceRequirement
from core.product_model.schemas import ClarificationDraft, FeatureSpecBody


class AcChange(BaseModel):
    model_config = ConfigDict(extra="forbid")

    op: Literal["ADD", "MODIFY", "REMOVE"]
    lineage_key: str | None = None
    statement: str | None = None
    given: str | None = None
    when: str | None = None
    then: str | None = None
    mandatory: bool | None = None
    evidence_requirement: EvidenceRequirement | None = None
    rationale: str


class ChangeInterpretation(BaseModel):
    model_config = ConfigDict(extra="forbid")

    resolution: Literal["EXISTING_FEATURE", "NEW_FEATURE_IN_CAPABILITY", "NEW_CAPABILITY"]
    feature_key: str | None = None
    capability_key: str | None = None
    proposed_feature_spec: FeatureSpecBody
    requirement_changes: list[dict[str, object]] = Field(default_factory=list)
    acceptance_criteria_changes: list[AcChange] = Field(default_factory=list)
    architecture_change_expected: bool
    architecture_rationale: str
    open_questions: list[ClarificationDraft] = Field(default_factory=list)
    candidate_ranking_rationale: str
