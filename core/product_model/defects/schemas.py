from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


class ReproductionStep(BaseModel):
    kind: Literal["http", "function", "setup"]
    description: str
    method: str | None = None
    path: str | None = None
    body: dict[str, Any] | None = None


class ReproductionPlan(BaseModel):
    preconditions: list[str] = Field(default_factory=list)
    steps: list[ReproductionStep]
    observed_symptom: str


class DefectTriage(BaseModel):
    feature_keys: list[str] = Field(default_factory=list)
    suspected_ac_lineage_keys: list[str] = Field(default_factory=list)
    suspected_baseline_keys: list[str] = Field(default_factory=list)
    severity: Literal["S1", "S2", "S3", "S4"]
    reproduction_plan: ReproductionPlan
    observed_symptom_signature: dict[str, Any]
    open_questions: list[str] = Field(default_factory=list)


class ExpectedBehaviorProposal(BaseModel):
    classification: Literal["SPECIFIED", "UNDERSPECIFIED", "CONFLICTING", "NOT_A_DEFECT"]
    cited_ac_lineage_keys: list[str] = Field(default_factory=list)
    proposed_ac: dict[str, Any] | None = None
    expected_behavior_statement: str
    questions: list[str] = Field(default_factory=list)


class RootCauseHypothesis(BaseModel):
    faulty_stable_keys: list[str]
    explanation: str
    confidence: float = Field(ge=0.0, le=1.0)
    fix_outline: str
    regression_risks: list[str] = Field(default_factory=list)
    cited_evidence_ids: list[str] = Field(default_factory=list)


class ReproductionTestArtifact(BaseModel):
    relative_path: str
    test_source: str
    observed_symptom_signature: dict[str, Any] | None = None
