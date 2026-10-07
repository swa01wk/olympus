from __future__ import annotations

import uuid

import pytest
from core.assurance.enums import EvidenceProducer, EvidenceResult, EvidenceType
from core.assurance.models import Evidence
from sqlalchemy.exc import DBAPIError

pytestmark = pytest.mark.persistence


@pytest.mark.asyncio
async def test_evidence_immutable(db_session, sample_project, operator_ctx) -> None:
    from core.domain.delivery_cycles.service import DeliveryCycleService
    from core.domain.enums import DeliveryCycleType

    cycle = await DeliveryCycleService().create(
        db_session,
        sample_project.id,
        DeliveryCycleType.GREENFIELD_BUILD,
        "ev immutability",
        operator_ctx,
    )
    row = Evidence(
        key="EV-TEST-1",
        project_id=sample_project.id,
        delivery_cycle_id=cycle.id,
        integration_candidate_id=None,
        commit_sha="abc123",
        evidence_type=EvidenceType.UNIT_TEST,
        result=EvidenceResult.PASS,
        subject_type="BASELINE",
        subject_id=uuid.uuid4(),
        check_ref="test",
        producer=EvidenceProducer.SENTINEL,
    )
    db_session.add(row)
    await db_session.flush()
    row.result = EvidenceResult.FAIL
    with pytest.raises(DBAPIError):
        await db_session.flush()
