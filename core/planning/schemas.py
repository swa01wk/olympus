from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from core.product_model.schemas import ClarificationDraft


class ComponentDef(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str
    layer: str
    responsibility: str
    directory: str


class DecisionDef(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    title: str
    decision: str
    rationale: str


class TechnologyStack(BaseModel):
    """Fixed keys so OpenAI strict json_schema can represent the stack."""

    model_config = ConfigDict(extra="forbid")

    language: str
    web: str
    orm: str
    tests: str


class DirectoryConventionEntry(BaseModel):
    model_config = ConfigDict(extra="forbid")

    path: str
    purpose: str


class ArchitectureBody(BaseModel):
    model_config = ConfigDict(extra="forbid")

    summary: str
    technology_stack: TechnologyStack
    components: list[ComponentDef]
    layers: list[str]
    dependency_rules: list[str]
    directory_conventions: list[DirectoryConventionEntry]
    decisions: list[DecisionDef]
    constraints: list[str]
    risks: list[str] = Field(default_factory=list)


class ContractDraft(BaseModel):
    model_config = ConfigDict(extra="forbid")

    key: str
    kind: Literal["API", "DATA", "EVENT"]
    name: str
    method: str = ""
    path: str = ""
    description: str = ""


class ArchitectureProposal(BaseModel):
    model_config = ConfigDict(extra="forbid")

    body: ArchitectureBody
    contracts: list[ContractDraft] = Field(default_factory=list)
    open_questions: list[ClarificationDraft] = Field(default_factory=list)


class ApiDef(BaseModel):
    model_config = ConfigDict(extra="forbid")

    method: str
    path: str
    contract_key: str | None = None


class SchemaDef(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str
    description: str = ""


class DataChangeDef(BaseModel):
    model_config = ConfigDict(extra="forbid")

    kind: str
    description: str


class TestRequirement(BaseModel):
    model_config = ConfigDict(extra="forbid")

    kind: Literal["unit", "integration", "api"]
    ac_keys: list[str]
    description: str


class AcCoverageEntry(BaseModel):
    model_config = ConfigDict(extra="forbid")

    ac_key: str
    locations: list[str]


class ImplementationSpecBody(BaseModel):
    model_config = ConfigDict(extra="forbid")

    summary: str
    components: list[str]
    apis: list[ApiDef] = Field(default_factory=list)
    schemas: list[SchemaDef] = Field(default_factory=list)
    data_changes: list[DataChangeDef] = Field(default_factory=list)
    integration_points: list[str] = Field(default_factory=list)
    required_tests: list[TestRequirement] = Field(default_factory=list)
    file_scope: list[str]
    architecture_refs: list[str] = Field(default_factory=list)
    ac_coverage: list[AcCoverageEntry] = Field(default_factory=list)


class ImplementationSpecDraft(BaseModel):
    model_config = ConfigDict(extra="forbid")

    body: ImplementationSpecBody
    open_questions: list[ClarificationDraft] = Field(default_factory=list)


class TaskDraft(BaseModel):
    model_config = ConfigDict(extra="forbid")

    ref: str
    title: str
    objective: str
    work_type: Literal["CODE_CHANGE"] = "CODE_CHANGE"
    implementation_spec_ref: str
    ac_refs: list[str]
    requirement_refs: list[str] = Field(default_factory=list)
    allowed_scope: list[str]
    constraints: list[str] = Field(default_factory=list)
    required_outputs: list[str]
    verification_requirements: list[str]
    estimated_size: Literal["S", "M", "L"]


class DependencyDraft(BaseModel):
    model_config = ConfigDict(extra="forbid")

    task_ref: str
    depends_on_ref: str
    reason: str


class RiskObservation(BaseModel):
    model_config = ConfigDict(extra="forbid")

    description: str
    severity: Literal["LOW", "MEDIUM", "HIGH"]
    related_refs: list[str] = Field(default_factory=list)


class TaskPlan(BaseModel):
    model_config = ConfigDict(extra="forbid")

    tasks: list[TaskDraft]
    dependencies: list[DependencyDraft] = Field(default_factory=list)
    risks: list[RiskObservation] = Field(default_factory=list)
    open_questions: list[ClarificationDraft] = Field(default_factory=list)


class ConformanceReport(BaseModel):
    model_config = ConfigDict(extra="forbid")

    ok: bool
    violations: list[str] = Field(default_factory=list)


class PlanValidationReport(BaseModel):
    model_config = ConfigDict(extra="forbid")

    ok: bool
    errors: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
