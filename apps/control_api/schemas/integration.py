from __future__ import annotations

import uuid
from typing import Any

from core.integration.models import IntegrationCandidate
from pydantic import BaseModel


class IntegrationCandidateResponse(BaseModel):
    id: uuid.UUID
    key: str
    delivery_cycle_id: uuid.UUID
    repository_id: uuid.UUID
    base_sha: str
    integration_branch: str
    integrated_sha: str | None
    status: str
    ordering: list[Any]
    integration_execution_id: uuid.UUID | None
    checks_artifact_id: uuid.UUID | None
    canonical_index_version_id: uuid.UUID | None

    @classmethod
    def from_model(cls, row: IntegrationCandidate) -> IntegrationCandidateResponse:
        return cls(
            id=row.id,
            key=row.key,
            delivery_cycle_id=row.delivery_cycle_id,
            repository_id=row.repository_id,
            base_sha=row.base_sha,
            integration_branch=row.integration_branch,
            integrated_sha=row.integrated_sha,
            status=row.status.value,
            ordering=row.ordering,
            integration_execution_id=row.integration_execution_id,
            checks_artifact_id=row.checks_artifact_id,
            canonical_index_version_id=row.canonical_index_version_id,
        )
