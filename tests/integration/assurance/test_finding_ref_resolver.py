"""Scheduler ref resolver coverage for remediation contract inputs."""

from __future__ import annotations

import pytest
from core.assurance.findings import FindingService
from core.domain.delivery_cycles.service import DeliveryCycleService
from core.domain.enums import DeliveryCycleType
from core.domain.task_contracts.schemas import VersionedRef
from core.integration.enums import FindingSeverity, FindingSource
from core.scheduler.refs import build_default_registry

pytestmark = pytest.mark.integration


@pytest.mark.asyncio
async def test_finding_ref_resolves_for_eligibility(
    db_session,
    sample_project,
    operator_ctx,
) -> None:
    cycle = await DeliveryCycleService().create(
        db_session,
        sample_project.id,
        DeliveryCycleType.GREENFIELD_BUILD,
        "finding-ref",
        operator_ctx,
    )
    finding = await FindingService().create(
        db_session,
        project_id=sample_project.id,
        delivery_cycle_id=cycle.id,
        source=FindingSource.SENTINEL,
        category="CORRECTNESS",
        severity=FindingSeverity.BLOCKER,
        title="Test failure",
        detail={"detail": "assert failed"},
        ctx=operator_ctx,
    )
    ref = VersionedRef(ref_type="FINDING", ref_id=finding.id)
    registry = build_default_registry()
    exists, current = await registry.resolve_checks(db_session, [ref])
    key = (ref.ref_type, ref.ref_id, ref.version)
    assert exists[key] is True
    assert current[key] is True
