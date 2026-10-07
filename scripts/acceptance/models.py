"""MVP acceptance report shapes (Phase 19 §6)."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, Field


class AcceptanceCheck(BaseModel):
    name: str
    source: Literal["ARCH_26", "TECH_32", "ARCH_22", "TECH_31", "STATUS_DOD"]
    ok: bool
    evidence_refs: list[str] = Field(default_factory=list)
    query: str
    detail: str | None = None


class MvpAcceptanceReport(BaseModel):
    run_id: str
    started_at: datetime
    finished_at: datetime
    chaos: bool
    project_key: str
    cycles: dict[str, str]
    releases: dict[str, str]
    llm: dict[str, Decimal | int | float]
    restart_fingerprints: dict[str, tuple[str, str]]
    checks: list[AcceptanceCheck]
    mvp_complete: bool
