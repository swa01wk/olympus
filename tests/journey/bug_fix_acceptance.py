"""Phase 15 acceptance assertions for Bug Fix journey."""

from __future__ import annotations

import uuid

from core.assurance.enums import EvidenceResult, EvidenceType, GateStatus, GateType
from core.assurance.models import Evidence, Gate
from core.domain.delivery_cycles.models import DeliveryCycle
from core.domain.enums import DeliveryCycleType, SpecStatus, TaskOrigin, WorkType
from core.domain.repositories.models import Repository
from core.domain.task_contracts.models import TaskContract
from core.domain.tasks.models import Task
from core.integration.models import IntegrationCandidate
from core.planning.models import ImplementationSpec
from core.product_model.defects.models import (
    Defect,
    ExpectedBehaviorResolution,
    Reproduction,
    RootCauseAnalysis,
    TraceCorrelation,
)
from core.product_model.models import AcceptanceCriterion, Feature
from core.release.models import Release
from core.traceability.models import RepositoryIndexPointer
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession


async def assert_bug_fix_phase15_acceptance(
    session: AsyncSession,
    *,
    project_id: uuid.UUID,
    cycle_id: uuid.UUID,
    ic: IntegrationCandidate,
    release: Release,
) -> None:
    """Assert plan §14 acceptance criteria for the bug-fix journey."""
    assert ic.integrated_sha is not None
    integrated_sha = ic.integrated_sha

    cycle = await session.get(DeliveryCycle, cycle_id)
    assert cycle is not None
    assert cycle.type == DeliveryCycleType.BUG_FIX
    assert cycle.base_sha is not None

    defect = (
        await session.execute(select(Defect).where(Defect.delivery_cycle_id == cycle_id))
    ).scalar_one()
    assert defect.affected_sha == cycle.base_sha
    assert defect.status in {"FIXED", "RELEASED"}
    assert defect.linked_feature_ids
    feat = await session.get(Feature, uuid.UUID(defect.linked_feature_ids[0]))
    assert feat is not None

    dup_count = await session.scalar(
        select(func.count()).select_from(Defect).where(Defect.delivery_cycle_id == cycle_id)
    )
    assert dup_count == 1

    pre_ev = (
        await session.execute(
            select(Evidence).where(
                Evidence.delivery_cycle_id == cycle_id,
                Evidence.subject_type == "DEFECT",
                Evidence.subject_id == defect.id,
                Evidence.evidence_type == EvidenceType.REPRODUCTION,
                Evidence.result == EvidenceResult.FAIL,
            )
        )
    ).scalar_one()
    assert pre_ev.details.get("phase") == "PRE_REPAIR"
    assert pre_ev.details.get("reproduced") is True
    assert pre_ev.commit_sha == defect.affected_sha

    pre_repro = (
        await session.execute(
            select(Reproduction).where(
                Reproduction.defect_id == defect.id,
                Reproduction.phase == "PRE_REPAIR",
            )
        )
    ).scalar_one()
    assert pre_repro.outcome == "REPRODUCED"
    assert pre_repro.runs >= 2

    ebr = (
        await session.execute(
            select(ExpectedBehaviorResolution).where(
                ExpectedBehaviorResolution.defect_id == defect.id
            )
        )
    ).scalar_one()
    assert ebr.classification == "SPECIFIED"
    assert ebr.ac_ids
    ac = await session.get(AcceptanceCriterion, uuid.UUID(ebr.ac_ids[0]))
    assert ac is not None and "409" in (ac.statement or ac.then or "")

    trace = (
        await session.execute(
            select(TraceCorrelation).where(TraceCorrelation.reproduction_id == pre_repro.id)
        )
    ).scalar_one_or_none()
    assert trace is not None
    assert trace.candidates

    rca = (
        await session.execute(
            select(RootCauseAnalysis).where(RootCauseAnalysis.defect_id == defect.id)
        )
    ).scalar_one()
    assert rca.knowledge_class == "INFERENCE"
    assert rca.faulty_stable_keys

    repair_impl = (
        await session.execute(
            select(ImplementationSpec).where(
                ImplementationSpec.project_id == project_id,
                ImplementationSpec.kind == "REPAIR",
                ImplementationSpec.status == SpecStatus.APPROVED,
            )
        )
    ).scalar_one()
    body = repair_impl.body if isinstance(repair_impl.body, dict) else {}
    files = body.get("files") or body.get("repair_files") or []
    assert len(files) <= 3 or body.get("regression_test_path")

    repair_tasks = list(
        (
            await session.execute(
                select(Task).where(
                    Task.delivery_cycle_id == cycle_id,
                    Task.origin == TaskOrigin.REPAIR,
                    Task.work_type == WorkType.CODE_CHANGE,
                )
            )
        ).scalars()
    )
    assert repair_tasks
    for task in repair_tasks:
        assert task.current_contract_id is not None
        contract = await session.get(TaskContract, task.current_contract_id)
        assert contract is not None and contract.status.value == "ISSUED"

    repo = await session.get(Repository, cycle.repository_id) if cycle.repository_id else None
    assert repo is not None and repo.canonical_commit == integrated_sha
    pointer = await session.get(RepositoryIndexPointer, repo.id)
    assert pointer is not None and pointer.canonical_index_version_id is not None

    post_ev = (
        await session.execute(
            select(Evidence)
            .where(
                Evidence.integration_candidate_id == ic.id,
                Evidence.evidence_type == EvidenceType.REPRODUCTION,
                Evidence.result == EvidenceResult.PASS,
                Evidence.commit_sha == integrated_sha,
            )
            .order_by(Evidence.created_at.desc())
            .limit(1)
        )
    ).scalar_one_or_none()
    assert post_ev is not None

    reg_rows = (
        await session.execute(
            select(Evidence).where(
                Evidence.integration_candidate_id == ic.id,
                Evidence.evidence_type == EvidenceType.REGRESSION_TEST,
                Evidence.result == EvidenceResult.PASS,
            )
        )
    ).scalars()
    ic_reg = None
    validated_reg = None
    for ev in reg_rows:
        if ev.details.get("regression_test_validated"):
            validated_reg = ev
        elif ic_reg is None:
            ic_reg = ev
    assert ic_reg is not None
    assert validated_reg is not None
    assert validated_reg.details.get("regression_test_validated") is True

    for gt in (
        GateType.REPRODUCTION,
        GateType.REGRESSION,
        GateType.BASELINE,
        GateType.WARDEN,
        GateType.SENTINEL,
        GateType.INTEGRATION,
    ):
        gate = (
            await session.execute(
                select(Gate).where(
                    Gate.integration_candidate_id == ic.id,
                    Gate.gate_type == gt,
                )
            )
        ).scalar_one_or_none()
        assert gate is not None and gate.status == GateStatus.PASS, gt

    assert release.status.value in {"RELEASED", "EXECUTED"}
