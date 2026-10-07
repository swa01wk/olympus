"""Phase 09 §12 live workflow: remediate finding → live Forge → IC → gates PASS.

Uses real ``sentinel.execute`` (``live_llm`` disables the integration assurance stub).
"""

from __future__ import annotations

import os
import uuid

import pytest
from core.assurance.enums import GateStatus, GateType
from core.assurance.findings import FindingService
from core.assurance.models import Finding
from core.assurance.remediation import RemediationService
from core.commands.context import CommandContext
from core.domain.enums import ExecutionStatus, TaskOrigin, TaskStatus
from core.domain.executions.models import Execution
from core.domain.tasks.models import Task
from core.execution.worker import ExecutionWorker
from core.integration.enums import FindingSeverity, FindingSource, ICStatus
from core.integration.models import IntegrationCandidate
from core.intelligence.code_index.enums import EntityType
from core.scheduler.admission import AdmissionService
from sqlalchemy import select
from tests.fixtures.assurance_harness import (
    DEFAULT_TEST_PATH,
    add_warden_review_evidence,
    finalize_all_pending_gates,
    gate_by_type,
    human_finalize_ctx,
    patch_agentless_assurance,
    ready_ic_with_sentinel_evidence,
)
from tests.fixtures.integration_harness import create_and_run_integration
from tests.live_credentials import any_live_provider_configured

pytestmark = [
    pytest.mark.workflow,
    pytest.mark.live_llm,
    pytest.mark.integration,
    pytest.mark.git,
]


async def _run_remediation_task_live(
    db_session,
    ctx: CommandContext,
    task_id: uuid.UUID,
    *,
    attempts: int = 3,
) -> None:
    last_error: AssertionError | None = None
    for _attempt in range(attempts):
        task = await db_session.get(Task, task_id)
        assert task is not None
        if task.status == TaskStatus.COMPLETED:
            return
        if task.status not in {TaskStatus.READY, TaskStatus.RUNNING, TaskStatus.QUEUED}:
            task.status = TaskStatus.READY
            await db_session.flush()
        execution = await AdmissionService().admit_task(db_session, task_id, ctx)
        execution_id = execution.id
        worker = ExecutionWorker(worker_id=f"rem-live-{uuid.uuid4().hex[:6]}")
        for _ in range(120):
            await worker.run_once(db_session, ctx)
            execution = await db_session.get(Execution, execution_id)
            assert execution is not None
            if execution.status in {ExecutionStatus.COMPLETED, ExecutionStatus.FAILED}:
                break
        task = await db_session.get(Task, task_id)
        assert task is not None
        if task.status == TaskStatus.COMPLETED:
            return
        detail = execution.failure_detail if execution else ""
        last_error = AssertionError(f"remediation task not completed: {task.status} {detail}")
    assert last_error is not None
    raise last_error


async def _ensure_ic_verifies_ac_test_link(
    db_session,
    ic: IntegrationCandidate,
    project_id: uuid.UUID,
    ac_lineage_key: str,
) -> None:
    """Ensure deterministic sentinel plan can cover AC obligations on this IC."""
    from core.integration.enums import SpecCodeLinkOrigin, SpecCodeLinkRelation, SpecCodeLinkStatus
    from core.intelligence.code_index.models import CodeEntity
    from core.product_model.models import AcceptanceCriterion, FeatureSpec
    from core.traceability.models import SpecCodeLink

    if ic.canonical_index_version_id is None:
        return
    ac = (
        await db_session.execute(
            select(AcceptanceCriterion)
            .join(FeatureSpec, AcceptanceCriterion.feature_spec_id == FeatureSpec.id)
            .where(
                FeatureSpec.project_id == project_id,
                AcceptanceCriterion.lineage_key == ac_lineage_key,
            )
        )
    ).scalar_one_or_none()
    if ac is None:
        return
    existing = (
        await db_session.execute(
            select(SpecCodeLink).where(
                SpecCodeLink.spec_id == ac.id,
                SpecCodeLink.repository_id == ic.repository_id,
                SpecCodeLink.established_index_version_id == ic.canonical_index_version_id,
                SpecCodeLink.relation == SpecCodeLinkRelation.VERIFIES,
            )
        )
    ).scalar_one_or_none()
    if existing is not None:
        return
    entities = (
        (
            await db_session.execute(
                select(CodeEntity).where(
                    CodeEntity.index_version_id == ic.canonical_index_version_id,
                    CodeEntity.file_path == DEFAULT_TEST_PATH,
                    CodeEntity.type == EntityType.TEST,
                )
            )
        )
        .scalars()
        .all()
    )
    if not entities:
        return
    test_entity = next(
        (e for e in entities if (e.entity_metadata or {}).get("name") == "test_ac_assurance"),
        entities[0],
    )
    db_session.add(
        SpecCodeLink(
            project_id=project_id,
            repository_id=ic.repository_id,
            spec_type="ACCEPTANCE_CRITERION",
            spec_id=ac.id,
            spec_lineage_key=ac.lineage_key,
            code_stable_key=test_entity.stable_key,
            relation=SpecCodeLinkRelation.VERIFIES,
            origin=SpecCodeLinkOrigin.HUMAN_CONFIRMED,
            confidence=1.0,
            established_index_version_id=ic.canonical_index_version_id,
            last_confirmed_index_version_id=ic.canonical_index_version_id,
            status=SpecCodeLinkStatus.ACTIVE,
        )
    )
    await db_session.flush()


@pytest.mark.asyncio
async def test_live_forge_remediation_loop_ic_and_sentinel_gate_pass(
    db_session,
    system_actor,
) -> None:
    if os.getenv("LLM_LIVE_TESTS") != "1":
        pytest.skip("LLM_LIVE_TESTS=1 required")
    if not any_live_provider_configured():
        pytest.skip("No live provider API key configured")

    ctx = CommandContext(actor=system_actor, correlation_id="p9-rem-live")
    ic1, lineage, fixture = await ready_ic_with_sentinel_evidence(
        db_session, ctx, project_key="p9-rem-live", passing=False
    )
    fin_ctx = await human_finalize_ctx(db_session)
    gates1 = await finalize_all_pending_gates(db_session, ic1.id, fin_ctx)
    assert gate_by_type(gates1, GateType.SENTINEL).status == GateStatus.FAIL

    finding = await FindingService().create(
        db_session,
        project_id=fixture.project.id,
        delivery_cycle_id=fixture.cycle.id,
        source=FindingSource.SENTINEL,
        category="CORRECTNESS",
        severity=FindingSeverity.BLOCKER,
        title=f"Fix failing test in {DEFAULT_TEST_PATH}",
        detail={"obligation": lineage.ac_lineage_key},
        ctx=ctx,
        integration_candidate_id=ic1.id,
        commit_sha=ic1.integrated_sha,
        code_refs=[{"file_path": DEFAULT_TEST_PATH}],
    )
    rem_task_id = await RemediationService().remediate_finding(db_session, finding.id, fin_ctx)
    rem_task = await db_session.get(Task, rem_task_id)
    assert rem_task is not None and rem_task.origin == TaskOrigin.REMEDIATION

    await _run_remediation_task_live(db_session, ctx, rem_task_id)

    with patch_agentless_assurance():
        ic2 = await create_and_run_integration(db_session, ctx, fixture.cycle.id)
    if ic2.status != ICStatus.READY:
        finding = (
            await db_session.execute(
                select(Finding)
                .where(Finding.integration_candidate_id == ic2.id)
                .order_by(Finding.created_at.desc())
                .limit(1)
            )
        ).scalar_one_or_none()
        raise AssertionError(
            f"remediation IC not READY: {ic2.status} ({finding.title if finding else 'no finding'})"
        )
    assert ic2.supersedes_id == ic1.id
    await _ensure_ic_verifies_ac_test_link(
        db_session, ic2, fixture.project.id, lineage.ac_lineage_key
    )

    await add_warden_review_evidence(db_session, ic2, ctx)
    with patch_agentless_assurance():
        from tests.fixtures.assurance_harness import _refresh_sentinel_plan_and_execute

        await _refresh_sentinel_plan_and_execute(db_session, ctx, ic2.id)
    gates2 = await finalize_all_pending_gates(db_session, ic2.id, fin_ctx)
    assert gate_by_type(gates2, GateType.SENTINEL).status == GateStatus.PASS
