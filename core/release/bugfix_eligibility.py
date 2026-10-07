"""Bug-fix release eligibility conditions."""

from __future__ import annotations

from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.assurance.enums import EvidenceResult, EvidenceType
from core.assurance.models import Evidence
from core.domain.candidate_commits.models import CandidateCommit
from core.domain.canonical_json import sha256_hex
from core.domain.delivery_cycles.models import DeliveryCycle
from core.domain.enums import DeliveryCycleType
from core.domain.tasks.models import Task
from core.integration.models import IntegrationCandidate
from core.product_model.defects.models import Defect, Reproduction
from core.release.eligibility import ConditionResult, get_eligibility_registry
from core.release.models import Release


async def _cond_defect_reproduced_before_repair(
    session: AsyncSession,
    cycle: DeliveryCycle,
    ic: IntegrationCandidate | None,
    _release: Release | None,
    _inputs: dict[str, Any],
) -> ConditionResult:
    name = "defect_reproduced_before_repair"
    if cycle.type != DeliveryCycleType.BUG_FIX or ic is None:
        return ConditionResult(name, True, (), sha256_hex({}))
    defect = (
        await session.execute(select(Defect).where(Defect.delivery_cycle_id == cycle.id))
    ).scalar_one_or_none()
    if defect is None:
        return ConditionResult(name, False, ("DEFECT_MISSING",), sha256_hex({}))
    from core.domain.approvals.models import Approval
    from core.domain.enums import ApprovalStatus, ApprovalType

    unrepro = (
        await session.execute(
            select(Approval).where(
                Approval.delivery_cycle_id == cycle.id,
                Approval.approval_type == ApprovalType.UNREPRODUCED_REPAIR,
                Approval.status == ApprovalStatus.APPROVED,
            )
        )
    ).scalar_one_or_none()
    if unrepro is not None:
        return ConditionResult(name, True, (), sha256_hex({"unreproduced": True}))
    pre = (
        await session.execute(
            select(Reproduction).where(
                Reproduction.defect_id == defect.id,
                Reproduction.phase == "PRE_REPAIR",
                Reproduction.outcome == "REPRODUCED",
            )
        )
    ).scalar_one_or_none()
    if pre is None or pre.evidence_id is None:
        return ConditionResult(name, False, ("PRE_REPAIR_MISSING",), sha256_hex({}))
    ev = await session.get(Evidence, pre.evidence_id)
    if ev is None or not ev.details.get("reproduced"):
        return ConditionResult(name, False, ("PRE_REPAIR_NOT_VALID",), sha256_hex({}))
    first_cc = (
        await session.execute(
            select(CandidateCommit)
            .join(Task, CandidateCommit.task_id == Task.id)
            .where(Task.delivery_cycle_id == cycle.id)
            .order_by(CandidateCommit.created_at.asc())
            .limit(1)
        )
    ).scalar_one_or_none()
    if first_cc is not None and ev.created_at > first_cc.created_at:
        return ConditionResult(name, False, ("PRE_REPAIR_AFTER_REPAIR",), sha256_hex({}))
    return ConditionResult(name, True, (), sha256_hex({"evidence_id": str(ev.id)}))


async def _cond_original_reproduction_passes(
    session: AsyncSession,
    cycle: DeliveryCycle,
    ic: IntegrationCandidate | None,
    _release: Release | None,
    _inputs: dict[str, Any],
) -> ConditionResult:
    name = "original_reproduction_passes"
    if cycle.type != DeliveryCycleType.BUG_FIX or ic is None:
        return ConditionResult(name, True, (), sha256_hex({}))
    defect = (
        await session.execute(select(Defect).where(Defect.delivery_cycle_id == cycle.id))
    ).scalar_one_or_none()
    if defect is None:
        return ConditionResult(name, False, ("DEFECT_MISSING",), sha256_hex({}))
    rows = (
        await session.execute(
            select(Evidence).where(
                Evidence.integration_candidate_id == ic.id,
                Evidence.subject_id == defect.id,
                Evidence.evidence_type == EvidenceType.REPRODUCTION,
                Evidence.result == EvidenceResult.PASS,
            )
        )
    ).scalars()
    ev = next((e for e in rows if e.details.get("phase") == "POST_REPAIR"), None)
    if ev is None:
        return ConditionResult(name, False, ("POST_REPAIR_MISSING",), sha256_hex({}))
    pre = (
        await session.execute(
            select(Reproduction).where(
                Reproduction.defect_id == defect.id,
                Reproduction.phase == "PRE_REPAIR",
            )
        )
    ).scalar_one_or_none()
    if pre and ev.details.get("artifact_hash") != pre.artifact_hash:
        return ConditionResult(name, False, ("ARTIFACT_HASH_MISMATCH",), sha256_hex({}))
    return ConditionResult(name, True, (), sha256_hex({}))


async def _cond_regression_evidence_present(
    session: AsyncSession,
    cycle: DeliveryCycle,
    ic: IntegrationCandidate | None,
    _release: Release | None,
    _inputs: dict[str, Any],
) -> ConditionResult:
    name = "regression_evidence_present"
    if cycle.type != DeliveryCycleType.BUG_FIX or ic is None:
        return ConditionResult(name, True, (), sha256_hex({}))
    defect = (
        await session.execute(select(Defect).where(Defect.delivery_cycle_id == cycle.id))
    ).scalar_one_or_none()
    if defect is None:
        return ConditionResult(name, False, ("DEFECT_MISSING",), sha256_hex({}))
    rows = (
        await session.execute(
            select(Evidence).where(
                Evidence.integration_candidate_id == ic.id,
                Evidence.subject_id == defect.id,
                Evidence.evidence_type == EvidenceType.REGRESSION_TEST,
                Evidence.result == EvidenceResult.PASS,
            )
        )
    ).scalars()
    ic_ev = None
    validated_ev = None
    for ev in rows:
        if ev.details.get("regression_test_validated"):
            validated_ev = ev
        elif ic_ev is None:
            ic_ev = ev
    if ic_ev is None:
        return ConditionResult(name, False, ("REGRESSION_EVIDENCE_MISSING",), sha256_hex({}))
    if validated_ev is None:
        return ConditionResult(name, False, ("REGRESSION_NOT_VALIDATED",), sha256_hex({}))
    return ConditionResult(
        name,
        True,
        (),
        sha256_hex({"evidence_id": str(ic_ev.id), "validated_evidence_id": str(validated_ev.id)}),
    )


def register_bugfix_eligibility_conditions() -> None:
    reg = get_eligibility_registry()
    reg.register("defect_reproduced_before_repair", _cond_defect_reproduced_before_repair)
    reg.register("original_reproduction_passes", _cond_original_reproduction_passes)
    reg.register("regression_evidence_present", _cond_regression_evidence_present)


register_bugfix_eligibility_conditions()
