from __future__ import annotations

import pytest
from core.domain.canonical_json import sha256_hex
from core.domain.enums import EntityStatus, ModelOrigin, SpecKind, SpecStatus
from core.integration.enums import SpecCodeLinkOrigin, SpecCodeLinkRelation, SpecCodeLinkStatus
from core.intelligence.recovered_specs.reconciliation import RecoveryReconciliationService
from core.product_model.models import Feature, FeatureSpec
from core.traceability.models import SpecCodeLink

pytestmark = [pytest.mark.integration, pytest.mark.asyncio]


@pytest.mark.asyncio
async def test_reconciliation_matched_new_missing(db_session, system_ctx) -> None:
    from tests.fixtures.brownfield_harness import brownfield_cycle_at_code_index

    cycle, sha, repo_id = await brownfield_cycle_at_code_index(db_session, system_ctx)
    from core.traceability.models import RepositoryIndexPointer

    pointer = await db_session.get(RepositoryIndexPointer, repo_id)
    assert pointer and pointer.canonical_index_version_id
    index_version_id = pointer.canonical_index_version_id
    route_key = "ROUTE:POST /tickets"

    feat = Feature(
        project_id=cycle.project_id,
        key="FEAT-CAN",
        name="Canonical tickets",
        description="",
        status=EntityStatus.APPROVED,
        origin=ModelOrigin.GREENFIELD,
    )
    db_session.add(feat)
    await db_session.flush()
    body = {"summary": "canonical ticket create"}
    canonical_spec = FeatureSpec(
        project_id=cycle.project_id,
        feature_id=feat.id,
        lineage_key="SPEC-FEAT-CAN",
        version=1,
        status=SpecStatus.APPROVED,
        spec_kind=SpecKind.CANONICAL,
        body=body,
        content_hash=sha256_hex(body),
    )
    db_session.add(canonical_spec)
    await db_session.flush()
    from core.domain.enums import ExecutionStatus, TaskOrigin, WorkType
    from core.domain.executions.models import Execution
    from core.domain.task_contracts.models import TaskContract
    from core.domain.tasks.service import TaskService

    task_row = await TaskService().create_task(
        db_session,
        cycle.id,
        "Reconciliation fixture",
        WorkType.ANALYSIS,
        TaskOrigin.CONTROL_PLANE,
        system_ctx,
    )
    contract = TaskContract(
        task_id=task_row.id,
        key="v1",
        version=1,
        status="ISSUED",
        body={"objective": "fixture"},
        content_hash="recon-fixture",
        compiled_by="test",
    )
    db_session.add(contract)
    await db_session.flush()
    exec_row = Execution(
        key="recon-exec",
        task_id=task_row.id,
        delivery_cycle_id=cycle.id,
        task_contract_id=contract.id,
        attempt_number=1,
        status=ExecutionStatus.COMPLETED,
        executor_kind="DETERMINISTIC",
    )
    db_session.add(exec_row)
    await db_session.flush()
    db_session.add(
        SpecCodeLink(
            project_id=cycle.project_id,
            repository_id=repo_id,
            spec_type="FEATURE_SPEC",
            spec_id=canonical_spec.id,
            spec_lineage_key=canonical_spec.lineage_key,
            code_stable_key=route_key,
            relation=SpecCodeLinkRelation.IMPLEMENTS,
            origin=SpecCodeLinkOrigin.GENERATED_LINEAGE,
            status=SpecCodeLinkStatus.ACTIVE,
            confidence=1.0,
            task_id=task_row.id,
            execution_id=exec_row.id,
            evidence_refs=[],
            established_index_version_id=index_version_id,
            last_confirmed_index_version_id=index_version_id,
            commit_sha=sha,
        )
    )

    recovered_feat = Feature(
        project_id=cycle.project_id,
        key="FEAT-REC",
        name="Recovered tickets",
        description="",
        status=EntityStatus.PROPOSED,
        origin=ModelOrigin.RECOVERED,
    )
    db_session.add(recovered_feat)
    await db_session.flush()
    rec_body = {"summary": "recovered ticket create"}
    recovered_spec = FeatureSpec(
        project_id=cycle.project_id,
        feature_id=recovered_feat.id,
        lineage_key="SPEC-FEAT-REC",
        version=1,
        status=SpecStatus.PROPOSED,
        spec_kind=SpecKind.RECOVERED,
        body=rec_body,
        content_hash=sha256_hex(rec_body),
    )
    db_session.add(recovered_spec)
    await db_session.flush()
    db_session.add(
        SpecCodeLink(
            project_id=cycle.project_id,
            repository_id=repo_id,
            spec_type="FEATURE_SPEC",
            spec_id=recovered_spec.id,
            spec_lineage_key=recovered_spec.lineage_key,
            code_stable_key=route_key,
            relation=SpecCodeLinkRelation.IMPLEMENTS,
            origin=SpecCodeLinkOrigin.DISCOVERED,
            status=SpecCodeLinkStatus.ACTIVE,
            confidence=0.8,
            evidence_refs=[],
            established_index_version_id=index_version_id,
            last_confirmed_index_version_id=index_version_id,
            commit_sha=sha,
        )
    )
    await db_session.flush()

    report = await RecoveryReconciliationService().compare(
        db_session,
        cycle.project_id,
        [recovered_spec.id],
    )
    assert str(recovered_spec.id) in report["MATCHED"]
    assert report["MISSING"] == []
