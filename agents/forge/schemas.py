from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class AcTestMappingEntry(BaseModel):
    model_config = ConfigDict(extra="forbid")

    ac_ref: str
    test_ref: str


class ImplementationResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    summary: str
    changed_files: list[str]
    tests_added_or_changed: list[str]
    test_commands_run: list[str]
    principal_symbols: list[str]
    ac_test_mapping: list[AcTestMappingEntry] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)
    open_questions: list[str] = Field(default_factory=list)
