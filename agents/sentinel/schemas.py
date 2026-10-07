from __future__ import annotations

from typing import Literal

from core.assurance.schemas import PlannedCheck, SentinelRecommendation, VerificationPlan
from pydantic import BaseModel, ConfigDict, Field


class ApiProbe(BaseModel):
    model_config = ConfigDict(extra="forbid")

    method: Literal["GET"] = "GET"
    path: str
    expected_status: int = 200


class CharacterizationCheck(BaseModel):
    model_config = ConfigDict(extra="forbid")

    recovered_ac_key: str
    given: str
    when: str
    then: str
    kind: Literal["AUTHORED_TEST", "API_PROBE"]
    test_code: str | None = None
    test_filename: str | None = None
    probe: ApiProbe | None = None
    exercised_entities: list[str] = Field(default_factory=list)
    rationale: str = ""


class CharacterizationPlan(BaseModel):
    model_config = ConfigDict(extra="forbid")

    checks: list[CharacterizationCheck] = Field(default_factory=list)
    skipped: list[dict[str, str]] = Field(default_factory=list)


__all__ = [
    "PlannedCheck",
    "SentinelRecommendation",
    "VerificationPlan",
    "ApiProbe",
    "CharacterizationCheck",
    "CharacterizationPlan",
]
