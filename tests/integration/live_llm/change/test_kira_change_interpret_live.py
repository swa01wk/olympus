"""Live Kira change_interpret against trusted SupportDesk seed."""

from __future__ import annotations

import os
from unittest.mock import patch

import pytest
from core.execution.worker import ExecutionWorker
from core.product_model.changes.models import ChangeRequest
from core.runtime.model_router import build_providers
from core.scheduler.admission import AdmissionService
from core.state.transition_service import TransitionService
from sqlalchemy import select
from tests.fixtures.code_index_harness import SUPPORTDESK_R1
from tests.journey.seed import TRUSTED_SEED, seed_trusted_project
from tests.live_credentials import any_live_provider_configured

pytestmark = [
    pytest.mark.live_llm,
    pytest.mark.asyncio,
    pytest.mark.skipif(
        os.environ.get("LLM_LIVE_TESTS") != "1",
        reason="Set LLM_LIVE_TESTS=1 for live change interpret test",
    ),
]


CHANGE_PRIORITY_TEXT = "Add ticket priority: LOW, MEDIUM, HIGH. Default MEDIUM for existing rows."


@pytest.mark.asyncio
async def test_kira_change_interpret_priority_live(db_session, system_ctx) -> None:
    if not any_live_provider_configured():
        pytest.skip("No live provider API key configured")

    os.environ.setdefault("MODEL_PRODUCT_DECOMPOSITION", os.environ.get("MODEL_DEFAULT", ""))
    from core.config.settings import clear_settings_cache
    from core.runtime.model_policy import clear_models_config_cache

    clear_settings_cache()
    clear_models_config_cache()

    trusted = await seed_trusted_project(db_session, SUPPORTDESK_R1, TRUSTED_SEED, system_ctx)
    from core.product_model.changes.service import ChangeRequestService

    cr = await ChangeRequestService().intake(
        db_session,
        project_id=trusted.project_id,
        title="Priority",
        description=CHANGE_PRIORITY_TEXT,
        source_type="change_request_api",
        external_ref="live-interpret-1",
        inbound_event_id=None,
        ctx=system_ctx,
    )
    assert cr.delivery_cycle_id is not None
    cycle_id = cr.delivery_cycle_id
    await TransitionService().transition(
        db_session,
        "delivery_cycle",
        cycle_id,
        "INTAKE",
        "start_spec_delta",
        system_ctx,
    )

    worker = ExecutionWorker(worker_id="live-change-interpret")
    admission = AdmissionService()
    with patch("core.runtime.model_router.build_providers", side_effect=build_providers):
        for _ in range(120):
            await admission.admit_batch(db_session, 8, system_ctx)
            for _ in range(8):
                await worker.run_once(db_session, system_ctx)
            cr_check = (
                await db_session.execute(
                    select(ChangeRequest).where(ChangeRequest.delivery_cycle_id == cycle_id)
                )
            ).scalar_one()
            if cr_check.interpretation is not None:
                break

    row = (
        await db_session.execute(
            select(ChangeRequest).where(ChangeRequest.delivery_cycle_id == cycle_id)
        )
    ).scalar_one()
    assert row.interpretation is not None
    ac_changes = row.interpretation.get("acceptance_criteria_changes") or []
    assert row.interpretation.get("resolution") == "EXISTING_FEATURE"
    assert row.interpretation.get("feature_key") == "FEAT-TICKETS"
    assert any(
        c.get("op") == "ADD" and "priority" in str(c.get("statement", "")).lower()
        for c in ac_changes
    )
