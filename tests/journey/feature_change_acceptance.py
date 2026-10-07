"""Phase 14 acceptance assertions for Feature Change journey."""

from __future__ import annotations

import uuid

from core.assurance.enums import EvidenceResult, GateStatus, GateType, ObligationStatus
from core.assurance.models import Evidence, Gate, VerificationObligation
from core.domain.delivery_cycles.models import DeliveryCycle
from core.domain.enums import SpecStatus, WorkType
from core.domain.task_contracts.models import TaskContract
from core.domain.task_contracts.schemas import TaskContractBody
from core.domain.tasks.models import Task
from core.integration.models import IntegrationCandidate
from core.intelligence.baselines.models import BaselineSet
from core.intelligence.impact.enums import SpecDeltaStatus
from core.intelligence.impact.guards import architecture_delta_resolved
from core.intelligence.impact.models import ImpactAssessment, ImpactItem, SpecDelta
from core.planning.models import ImplementationSpec
from core.product_model.changes.models import ChangeRequest
from core.product_model.models import AcceptanceCriterion, FeatureSpec
from core.release.models import Release
from core.traceability.lineage.factory import build_lineage_service
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession


async def assert_feature_change_phase14_acceptance(
    session: AsyncSession,
    *,
    project_id: uuid.UUID,
    cycle_id: uuid.UUID,
    ic: IntegrationCandidate,
    release: Release,
) -> None:
    """Assert plan §14 acceptance criteria covered by the journey run."""
    assert ic.integrated_sha is not None
    integrated_sha = ic.integrated_sha

    cr = (
        await session.execute(
            select(ChangeRequest).where(ChangeRequest.delivery_cycle_id == cycle_id)
        )
    ).scalar_one()
    cr_count = await session.scalar(
        select(func.count())
        .select_from(ChangeRequest)
        .where(ChangeRequest.delivery_cycle_id == cycle_id)
    )
    assert cr_count == 1
    assert cr.status == "DONE"

    cycle = await session.get(DeliveryCycle, cycle_id)
    assert cycle is not None
    assert cycle.base_sha is not None
    assert cycle.type.value == "FEATURE_CHANGE"

    delta = (
        await session.execute(
            select(SpecDelta).where(
                SpecDelta.delivery_cycle_id == cycle_id,
                SpecDelta.status == SpecDeltaStatus.APPROVED.value,
            )
        )
    ).scalar_one()
    assert delta.content_hash
    assert delta.from_spec_id is not None
    parent = await session.get(FeatureSpec, delta.from_spec_id)
    to_spec = await session.get(FeatureSpec, delta.to_spec_id)
    assert parent is not None and to_spec is not None
    assert to_spec.version > parent.version
    assert to_spec.status in (SpecStatus.APPROVED, SpecStatus.SUPERSEDED)
    assert parent.status == SpecStatus.SUPERSEDED

    ia = (
        await session.execute(
            select(ImpactAssessment)
            .where(ImpactAssessment.delivery_cycle_id == cycle_id)
            .order_by(ImpactAssessment.created_at.desc())
            .limit(1)
        )
    ).scalar_one()
    items = list(
        (
            await session.execute(
                select(ImpactItem).where(ImpactItem.impact_assessment_id == ia.id)
            )
        ).scalars()
    )
    assert items
    assert any(i.path for i in items if i.path)
    arch_guard = await architecture_delta_resolved(session, cycle, None)
    assert arch_guard.ok, arch_guard.message or "architecture delta not resolved"

    impl_delta = (
        await session.execute(
            select(ImplementationSpec).where(
                ImplementationSpec.project_id == project_id,
                ImplementationSpec.kind == "DELTA",
                ImplementationSpec.status == SpecStatus.APPROVED,
            )
        )
    ).scalar_one()
    impl_scope = set(impl_delta.body.get("file_scope") or [])
    contracts = list(
        (
            await session.execute(
                select(TaskContract)
                .join(Task, TaskContract.task_id == Task.id)
                .where(
                    Task.delivery_cycle_id == cycle_id,
                    Task.work_type == WorkType.CODE_CHANGE,
                )
            )
        ).scalars()
    )
    assert contracts
    for contract in contracts:
        body = TaskContractBody.model_validate(contract.body)
        scope = body.allowed_scope or []
        assert scope
        if impl_scope:
            import fnmatch

            for pattern in scope:
                assert (
                    any(
                        fnmatch.fnmatch(path, pattern) or fnmatch.fnmatch(pattern, path)
                        for path in impl_scope
                    )
                    or pattern == "**"
                )

    repo = cycle.repository_id
    assert repo is not None
    from core.domain.repositories.models import Repository

    repository = await session.get(Repository, repo)
    assert repository is not None
    assert repository.canonical_commit == integrated_sha

    priority_acs = list(
        (
            await session.execute(
                select(AcceptanceCriterion).where(
                    AcceptanceCriterion.lineage_key.ilike("%PRIORITY%"),
                    AcceptanceCriterion.mandatory.is_(True),
                )
            )
        ).scalars()
    )
    assert priority_acs
    for ac in priority_acs:
        obl = (
            await session.execute(
                select(VerificationObligation).where(
                    VerificationObligation.integration_candidate_id == ic.id,
                    VerificationObligation.subject_id == ac.id,
                )
            )
        ).scalar_one_or_none()
        if obl is None:
            obl = (
                await session.execute(
                    select(VerificationObligation).where(
                        VerificationObligation.integration_candidate_id == ic.id,
                        VerificationObligation.subject_key == ac.lineage_key,
                    )
                )
            ).scalar_one_or_none()
        assert obl is not None, f"no obligation for AC {ac.lineage_key}"
        assert obl.status == ObligationStatus.SATISFIED, f"AC {ac.lineage_key} not satisfied"
        ev_rows = (
            await session.execute(
                select(Evidence)
                .where(
                    Evidence.obligation_id == obl.id,
                    Evidence.commit_sha == integrated_sha,
                    Evidence.result == EvidenceResult.PASS,
                )
                .limit(1)
            )
        ).scalars()
        assert ev_rows.first() is not None, f"missing PASS evidence for {ac.lineage_key}"

    for gate_type in (
        GateType.INTEGRATION,
        GateType.WARDEN,
        GateType.SENTINEL,
        GateType.BASELINE,
    ):
        gate = (
            await session.execute(
                select(Gate).where(
                    Gate.integration_candidate_id == ic.id,
                    Gate.gate_type == gate_type,
                )
            )
        ).scalar_one()
        assert gate.status == GateStatus.PASS, f"{gate_type.value} gate not PASS"

    assert release.status.value == "RELEASED"
    assert release.integrated_sha == integrated_sha

    bset = (
        (
            await session.execute(
                select(BaselineSet)
                .where(
                    BaselineSet.project_id == project_id,
                    BaselineSet.commit_sha == integrated_sha,
                )
                .order_by(BaselineSet.created_at.desc())
                .limit(1)
            )
        )
        .scalars()
        .first()
    )
    assert bset is not None
    bset_count = await session.scalar(
        select(func.count()).select_from(BaselineSet).where(BaselineSet.project_id == project_id)
    )
    assert bset_count is not None and bset_count >= 2

    graph = await build_lineage_service().forward(session, "FEATURE", str(to_spec.feature_id))
    assert graph.nodes, "expected forward lineage from feature"
    assert graph.edges, "expected lineage edges to code/tests"

    open_obligations = (
        await session.execute(
            select(VerificationObligation).where(
                VerificationObligation.integration_candidate_id == ic.id,
                VerificationObligation.required.is_(True),
                VerificationObligation.status != ObligationStatus.SATISFIED,
            )
        )
    ).scalars()
    assert not list(open_obligations), "required obligations must be satisfied at release"
