from __future__ import annotations

import pytest
from core.policy.policy_service import ensure_policy_version
from core.release.models import DeliveryOutcome, ReleaseEligibilityEvaluation
from sqlalchemy.exc import DBAPIError

pytestmark = pytest.mark.persistence


@pytest.mark.asyncio
async def test_release_eligibility_evaluation_immutable(
    db_session, sample_project, operator_ctx
) -> None:
    from core.domain.delivery_cycles.service import DeliveryCycleService
    from core.domain.enums import DeliveryCycleType

    policy = await ensure_policy_version(db_session)
    assert policy.version_row is not None
    cycle = await DeliveryCycleService().create(
        db_session,
        sample_project.id,
        DeliveryCycleType.GREENFIELD_BUILD,
        "eligibility immutability",
        operator_ctx,
    )
    row = ReleaseEligibilityEvaluation(
        delivery_cycle_id=cycle.id,
        integration_candidate_id=None,
        eligible=False,
        conditions=[{"name": "manifest_valid", "ok": False, "reasons": [], "inputs_hash": "x"}],
        policy_version_id=policy.version_row.id,
    )
    db_session.add(row)
    await db_session.flush()
    row.eligible = True
    with pytest.raises(DBAPIError):
        await db_session.flush()


@pytest.mark.asyncio
async def test_delivery_outcome_immutable(db_session, sample_project, operator_ctx) -> None:
    from core.domain.delivery_cycles.service import DeliveryCycleService
    from core.domain.enums import DeliveryCycleType

    cycle = await DeliveryCycleService().create(
        db_session,
        sample_project.id,
        DeliveryCycleType.GREENFIELD_BUILD,
        "outcome immutability",
        operator_ctx,
    )
    row = DeliveryOutcome(
        delivery_cycle_id=cycle.id,
        content={"result": "RELEASED"},
        result="RELEASED",
    )
    db_session.add(row)
    await db_session.flush()
    row.result = "FAILED"
    with pytest.raises(DBAPIError):
        await db_session.flush()
