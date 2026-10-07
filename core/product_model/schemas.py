from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from core.domain.enums import EvidenceRequirement


class FeatureSpecBody(BaseModel):
    model_config = ConfigDict(extra="forbid")

    behavior: str
    summary: str
    inputs: list[str]
    outputs: list[str]
    rules: list[str]
    constraints: list[str] = Field(default_factory=list)
    out_of_scope: list[str] = Field(default_factory=list)


class CapabilityDraft(BaseModel):
    ref: str
    name: str
    description: str
    source_sections: list[str]


class FeatureDraft(BaseModel):
    ref: str
    capability_ref: str
    name: str
    description: str
    source_sections: list[str]


class FeatureSpecDraft(BaseModel):
    ref: str
    feature_ref: str
    body: FeatureSpecBody


class RequirementDraft(BaseModel):
    ref: str
    feature_spec_ref: str
    statement: str
    kind: str
    priority: str


class UserStoryDraft(BaseModel):
    ref: str
    feature_spec_ref: str
    actor: str
    goal: str
    benefit: str


class AcceptanceCriterionDraft(BaseModel):
    ref: str
    feature_spec_ref: str
    statement: str
    given: str | None
    when: str | None
    then: str | None
    mandatory: bool
    evidence_requirement: EvidenceRequirement
    requirement_refs: list[str]


class ClarificationDraft(BaseModel):
    question: str
    context: str
    options: list[str] = Field(default_factory=list)
    blocking: bool
    related_refs: list[str] = Field(default_factory=list)


class ProductDecomposition(BaseModel):
    model_config = ConfigDict(extra="forbid")

    capabilities: list[CapabilityDraft]
    features: list[FeatureDraft]
    feature_specs: list[FeatureSpecDraft]
    requirements: list[RequirementDraft]
    user_stories: list[UserStoryDraft]
    acceptance_criteria: list[AcceptanceCriterionDraft]
    open_questions: list[ClarificationDraft]
    assumptions: list[str] = Field(default_factory=list)
