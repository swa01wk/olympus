"""Pure scheduler eligibility (ARCH §7.1). No I/O."""

from __future__ import annotations

from core.domain.enums import ApprovalStatus, RepositoryStatus, TaskStatus
from core.scheduler.types import EligibilityContext, EligibilityResult, TaskView


def evaluate(task: TaskView, ctx: EligibilityContext) -> EligibilityResult:
    reasons: list[str] = []

    if task.status != TaskStatus.READY:
        reasons.append("NOT_READY")

    for dep_id, status in ctx.dependency_statuses.items():
        if status != TaskStatus.COMPLETED:
            key = ctx.dependency_keys.get(dep_id, str(dep_id))
            reasons.append(f"DEPENDENCY_INCOMPLETE:{key}")

    if (
        task.current_contract_id is None
        or ctx.issued_contract_id is None
        or task.current_contract_id != ctx.issued_contract_id
    ):
        reasons.append("CONTRACT_VERSION_MISMATCH")

    for ref in ctx.contract_inputs:
        ref_key = (ref.ref_type, ref.ref_id, ref.version)
        if not ctx.ref_exists.get(ref_key, False):
            label = ref.key or f"{ref.ref_type}:{ref.ref_id}"
            reasons.append(f"ARTIFACT_MISSING:{label}")
        elif ref.version is not None and not ctx.ref_current.get(ref_key, True):
            reasons.append("CONTRACT_VERSION_MISMATCH")

    if task.repository_id is not None:
        if ctx.repository_status is not None and ctx.repository_status != RepositoryStatus.READY:
            reasons.append(f"REPOSITORY_NOT_READY:{ctx.repository_status.value}")
        if ctx.base_commit_available is False:
            reasons.append("BASE_COMMIT_UNAVAILABLE")

    for approval_id in ctx.required_approvals:
        approval_status = ctx.approval_statuses.get(approval_id)
        if approval_status != ApprovalStatus.APPROVED:
            reasons.append(f"APPROVAL_MISSING:{approval_id}")

    for rule in ctx.policy_blocked_rules:
        reasons.append(f"POLICY_BLOCKED:{rule}")

    if ctx.conflicting_execution_key and not task.allow_parallel_executions:
        reasons.append(f"CONFLICTING_EXECUTION:{ctx.conflicting_execution_key}")

    if not ctx.base_resolver_available:
        reasons.append("BASE_RESOLVER_UNAVAILABLE")

    if ctx.attempt_count >= task.max_attempts:
        reasons.append("MAX_ATTEMPTS_EXCEEDED")

    return EligibilityResult(eligible=len(reasons) == 0, reasons=reasons)
