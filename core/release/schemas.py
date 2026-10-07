from __future__ import annotations

import uuid
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from core.domain.task_contracts.schemas import VersionedRef


class ReleaseManifestContent(BaseModel):
    model_config = ConfigDict(extra="forbid")

    release_key: str
    project_key: str
    delivery_cycle_key: str
    cycle_type: str
    repository: dict[str, Any]
    integration_candidate: dict[str, Any]
    canonical_index_version_id: uuid.UUID
    canonical_index_hash: str
    feature_specs: list[VersionedRef]
    implementation_specs: list[VersionedRef]
    architecture: VersionedRef | None = None
    acceptance: list[dict[str, Any]] = Field(default_factory=list)
    baselines: list[dict[str, Any]] = Field(default_factory=list)
    gates: dict[str, str]
    approvals: list[str]
    waived_findings: list[str]
    blocking_findings: int
    executions: list[str]
    candidate_commits: list[str]
    policy_version: str
