from __future__ import annotations

import uuid
from dataclasses import dataclass, field

from core.domain.enums import ApprovalStatus, RepositoryStatus, TaskStatus
from core.domain.task_contracts.schemas import VersionedRef


@dataclass(frozen=True)
class TaskView:
    id: uuid.UUID
    key: str
    status: TaskStatus
    delivery_cycle_id: uuid.UUID
    current_contract_id: uuid.UUID | None
    allow_parallel_executions: bool
    max_attempts: int
    work_type: str
    origin: str
    repository_id: uuid.UUID | None


@dataclass(frozen=True)
class EligibilityContext:
    dependency_statuses: dict[uuid.UUID, TaskStatus]
    dependency_keys: dict[uuid.UUID, str]
    issued_contract_id: uuid.UUID | None
    issued_contract_version: int | None
    contract_inputs: tuple[VersionedRef, ...]
    required_approvals: tuple[uuid.UUID, ...]
    approval_statuses: dict[uuid.UUID, ApprovalStatus]
    policy_blocked_rules: tuple[str, ...]
    conflicting_execution_key: str | None
    attempt_count: int
    ref_exists: dict[tuple[str, uuid.UUID, int | None], bool]
    ref_current: dict[tuple[str, uuid.UUID, int | None], bool]
    repository_status: RepositoryStatus | None
    base_commit_available: bool | None
    base_resolver_available: bool = True


@dataclass(frozen=True)
class EligibilityResult:
    eligible: bool
    reasons: list[str] = field(default_factory=list)
