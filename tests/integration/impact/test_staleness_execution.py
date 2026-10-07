from __future__ import annotations

import pytest
from core.domain.canonical_json import sha256_hex
from core.domain.enums import ExecutionStatus, ModelOrigin, SpecStatus
from core.intelligence.impact.staleness import StalenessService
from core.planning.models import Architecture, ImplementationSpec
from core.product_model.models import Feature, FeatureSpec
from core.scheduler.admission import AdmissionService
from tests.fixtures.execution_harness import seed_ready_task
from tests.fixtures.planning_harness import supportdesk_architecture_proposal

pytestmark = [pytest.mark.integration, pytest.mark.asyncio]


async def test_superseded_implementation_spec_marks_queued_execution_stale(
    db_session, system_ctx
) -> None:
    bundle = await seed_ready_task(db_session, key_prefix="p13-impl-stale")
    feat = Feature(
        project_id=bundle.project.id,
        key="F-STALE",
        name="Stale feat",
        description="d",
        origin=ModelOrigin.GREENFIELD,
    )
    db_session.add(feat)
    await db_session.flush()
    fs_body = {"summary": "s", "behavior": "b", "rules": []}
    fs = FeatureSpec(
        project_id=bundle.project.id,
        feature_id=feat.id,
        lineage_key="SPEC-F-STALE",
        version=1,
        status=SpecStatus.APPROVED,
        body=fs_body,
        content_hash=sha256_hex(fs_body),
    )
    db_session.add(fs)
    await db_session.flush()
    arch_body = supportdesk_architecture_proposal().body.model_dump(mode="json")
    arch = Architecture(
        project_id=bundle.project.id,
        lineage_key="ARCH-STALE",
        version=1,
        status=SpecStatus.APPROVED,
        kind="BASELINE",
        body=arch_body,
        content_hash=sha256_hex(arch_body),
    )
    db_session.add(arch)
    await db_session.flush()
    impl_body = {"summary": "i", "components": ["api"], "file_scope": ["app/api/**"]}
    impl = ImplementationSpec(
        project_id=bundle.project.id,
        lineage_key="IMPL-STALE",
        version=1,
        status=SpecStatus.APPROVED,
        kind="FEATURE",
        feature_spec_id=fs.id,
        architecture_id=arch.id,
        body=impl_body,
        content_hash=sha256_hex(impl_body),
    )
    db_session.add(impl)
    await db_session.flush()

    bundle.task.implementation_spec_id = impl.id
    await db_session.flush()
    ex = await AdmissionService().admit_task(db_session, bundle.task.id, bundle.ctx)
    assert ex.status == ExecutionStatus.QUEUED

    report = await StalenessService().on_implementation_spec_superseded(
        db_session,
        superseded_spec_id=impl.id,
        delivery_cycle_id=bundle.cycle.id,
        ctx=bundle.ctx,
    )
    await db_session.refresh(ex)
    assert ex.status == ExecutionStatus.STALE
    assert report.events
    assert report.events[0].cause_type == "IMPLEMENTATION_SPEC_SUPERSEDED"
