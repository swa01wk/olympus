from __future__ import annotations

import uuid

import pytest
from core.domain.enums import ApprovalStatus, RepositoryStatus, TaskStatus
from core.domain.task_contracts.schemas import VersionedRef
from core.scheduler.eligibility import evaluate
from core.scheduler.types import EligibilityContext, TaskView

pytestmark = pytest.mark.unit


def _task(**overrides: object) -> TaskView:
    base = dict(
        id=uuid.uuid4(),
        key="T-0001",
        status=TaskStatus.READY,
        delivery_cycle_id=uuid.uuid4(),
        current_contract_id=uuid.uuid4(),
        allow_parallel_executions=False,
        max_attempts=3,
        work_type="ANALYSIS",
        origin="CONTROL_PLANE",
        repository_id=None,
    )
    base.update(overrides)
    return TaskView(**base)  # type: ignore[arg-type]


def _ctx(**overrides: object) -> EligibilityContext:
    issued = uuid.uuid4()
    base = dict(
        dependency_statuses={},
        dependency_keys={},
        issued_contract_id=issued,
        issued_contract_version=1,
        contract_inputs=(),
        required_approvals=(),
        approval_statuses={},
        policy_blocked_rules=(),
        conflicting_execution_key=None,
        attempt_count=0,
        ref_exists={},
        ref_current={},
        repository_status=None,
        base_commit_available=None,
        base_resolver_available=True,
    )
    base.update(overrides)
    return EligibilityContext(**base)  # type: ignore[arg-type]


def test_not_ready() -> None:
    result = evaluate(_task(status=TaskStatus.DRAFT), _ctx())
    assert "NOT_READY" in result.reasons


def test_dependency_incomplete() -> None:
    dep = uuid.uuid4()
    result = evaluate(
        _task(),
        _ctx(
            dependency_statuses={dep: TaskStatus.RUNNING},
            dependency_keys={dep: "T-0002"},
        ),
    )
    assert any(r.startswith("DEPENDENCY_INCOMPLETE:") for r in result.reasons)


def test_eligible_minimal() -> None:
    cid = uuid.uuid4()
    result = evaluate(
        _task(current_contract_id=cid),
        _ctx(issued_contract_id=cid),
    )
    assert result.eligible is True


def test_base_commit_unavailable() -> None:
    repo_id = uuid.uuid4()
    result = evaluate(
        _task(repository_id=repo_id),
        _ctx(repository_status=RepositoryStatus.READY, base_commit_available=False),
    )
    assert "BASE_COMMIT_UNAVAILABLE" in result.reasons


def test_repository_not_ready() -> None:
    repo_id = uuid.uuid4()
    result = evaluate(
        _task(repository_id=repo_id),
        _ctx(repository_status=RepositoryStatus.CLONING, base_commit_available=False),
    )
    assert any(r.startswith("REPOSITORY_NOT_READY:") for r in result.reasons)


def test_approval_missing() -> None:
    approval_id = uuid.uuid4()
    result = evaluate(
        _task(),
        _ctx(
            required_approvals=(approval_id,),
            approval_statuses={approval_id: ApprovalStatus.PENDING},
        ),
    )
    assert any(r.startswith("APPROVAL_MISSING:") for r in result.reasons)


def test_artifact_missing() -> None:
    ref = VersionedRef(ref_type="ARTIFACT", ref_id=uuid.uuid4(), key="A-1")
    key = (ref.ref_type, ref.ref_id, ref.version)
    result = evaluate(
        _task(),
        _ctx(
            contract_inputs=(ref,),
            ref_exists={key: False},
        ),
    )
    assert any(r.startswith("ARTIFACT_MISSING:") for r in result.reasons)
