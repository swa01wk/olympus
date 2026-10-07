from __future__ import annotations

from typing import Literal

from core.planning.schemas import ArchitectureBody, ImplementationSpecBody
from core.product_model.schemas import FeatureSpecBody
from pydantic import BaseModel, ConfigDict, Field


class Citation(BaseModel):
    ref_type: Literal["OBSERVED_BEHAVIOR", "FACT", "CODE_ENTITY", "TEST"]
    ref: str


class InferenceDraft(BaseModel):
    statement: str
    citations: list[Citation] = Field(min_length=1)
    confidence: Literal["HIGH", "MEDIUM", "LOW"]


class UncertaintyDraft(BaseModel):
    question: str
    why_uncertain: str
    citations: list[Citation] = Field(default_factory=list)
    blocking_suggested: bool


class CapabilityDraft(BaseModel):
    ref: str
    name: str
    description: str


class RecoveredFeatureDraft(BaseModel):
    ref: str
    capability_ref: str
    name: str
    description: str
    principal_entities: list[str]
    supporting_behaviors: list[str]


class RepositorySurvey(BaseModel):
    model_config = ConfigDict(extra="forbid")

    recovered_architecture: ArchitectureBody
    capabilities: list[CapabilityDraft]
    features: list[RecoveredFeatureDraft]
    inferences: list[InferenceDraft]
    uncertainties: list[UncertaintyDraft]


class RequirementDraft(BaseModel):
    ref: str
    statement: str
    citations: list[Citation] = Field(min_length=1)


class RecoveredAcDraft(BaseModel):
    ref: str
    statement: str
    given: str | None = None
    when: str | None = None
    then: str | None = None
    citations: list[Citation] = Field(min_length=1)
    confidence: Literal["HIGH", "MEDIUM", "LOW"]


class RecoveredFeatureSpec(BaseModel):
    model_config = ConfigDict(extra="forbid")

    feature_ref: str
    body: FeatureSpecBody
    rule_citations: dict[str, list[Citation]]
    requirements: list[RequirementDraft]
    acceptance_criteria: list[RecoveredAcDraft]
    implementation: ImplementationSpecBody | None = None
    principal_entity_links: list[dict[str, object]]
    inferences: list[InferenceDraft]
    uncertainties: list[UncertaintyDraft]
    confidence: Literal["HIGH", "MEDIUM", "LOW"]
