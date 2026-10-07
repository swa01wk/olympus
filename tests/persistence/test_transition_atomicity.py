from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest
from core.domain.delivery_cycles.service import DeliveryCycleService
from core.domain.enums import DeliveryCycleType
from core.state.transition_service import TransitionService

pytestmark = pytest.mark.persistence


@pytest.mark.asyncio
async def test_transition_rolls_back_on_event_failure(
    db_session, sample_project, operator_ctx
) -> None:
    cycle = await DeliveryCycleService().create(
        db_session,
        sample_project.id,
        DeliveryCycleType.GREENFIELD_BUILD,
        "obj",
        operator_ctx,
    )
    before_state = cycle.state
    with (
        patch(
            "core.state.transition_service.append_domain_event",
            new_callable=AsyncMock,
            side_effect=RuntimeError("inject"),
        ),
        pytest.raises(RuntimeError),
    ):
        await TransitionService().transition(
            db_session,
            "delivery_cycle",
            cycle.id,
            before_state,
            "cancel",
            operator_ctx,
        )
    await db_session.refresh(cycle)
    assert cycle.state == before_state
