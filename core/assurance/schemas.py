from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class ApiProbe(BaseModel):
    model_config = ConfigDict(extra="forbid")

    method: str
    path: str
    body: dict[str, Any] | None = None
    expected_status: int = 200
    expected_json_subset: dict[str, Any] | None = None


class PlannedCheck(BaseModel):
    model_config = ConfigDict(extra="forbid")

    obligation_key: str
    kind: Literal["EXISTING_TEST", "AUTHORED_TEST", "API_PROBE"]
    test_node_id: str | None = None
    test_code: str | None = None
    test_filename: str | None = None
    probe: ApiProbe | None = None
    rationale: str = ""


class VerificationPlan(BaseModel):
    model_config = ConfigDict(extra="forbid")

    checks: list[PlannedCheck]
    uncovered_obligations: list[str] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)


class SentinelRecommendation(BaseModel):
    model_config = ConfigDict(extra="forbid")

    recommended: Literal["PASS", "FAIL"]
    uncovered_obligations: list[str] = Field(default_factory=list)
    observations: list[str] = Field(default_factory=list)


class WardenConformanceEntry(BaseModel):
    model_config = ConfigDict(extra="forbid")

    implementation_spec_key: str
    conforms: bool
    notes: str = ""


class WardenFindingDraft(BaseModel):
    model_config = ConfigDict(extra="forbid")

    category: Literal[
        "ARCHITECTURE_CONFORMANCE",
        "CONTRACT_CONFORMANCE",
        "SECURITY",
        "CORRECTNESS",
        "MAINTAINABILITY",
        "TEST_ADEQUACY",
        "SCOPE_VIOLATION",
        "RISK",
    ]
    severity: Literal["BLOCKER", "MAJOR", "MINOR", "INFO"]
    title: str
    detail: str
    file_path: str | None = None
    line_start: int | None = None
    spec_refs: list[str] = Field(default_factory=list)


class WardenReview(BaseModel):
    model_config = ConfigDict(extra="forbid")

    findings: list[WardenFindingDraft]
    recommendation: Literal["APPROVE", "REQUEST_CHANGES"]
    conformance: list[WardenConformanceEntry] = Field(default_factory=list)
    summary: str
