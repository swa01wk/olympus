"""Live kira.defect_triage on SupportDesk defect fixture (Phase 15 §11)."""

from __future__ import annotations

import os
import uuid
from pathlib import Path
from unittest.mock import patch

import pytest
from core.domain.enums import ExecutionStatus
from core.domain.executions.models import Execution
from core.execution.worker import ExecutionWorker
from core.product_model.defects.models import Defect
from core.runtime.model_router import build_providers
from core.scheduler.admission import AdmissionService
from sqlalchemy import select
from tests.journey.seed import seed_trusted_project
from tests.live_credentials import any_live_provider_configured

pytestmark = [
    pytest.mark.live_llm,
    pytest.mark.asyncio,
    pytest.mark.skipif(
        os.environ.get("LLM_LIVE_TESTS") != "1",
        reason="Set LLM_LIVE_TESTS=1 for live defect triage test",
    ),
]

DEFECT_REPO = (
    Path(__file__).resolve().parents[3] / "fixtures" / "repos" / "supportdesk_defect_closed_update"
)
TRUSTED_SEED_DEFECT = (
    Path(__file__).resolve().parents[3] / "fixtures" / "supportdesk" / "trusted_seed_defect.yaml"
)


@pytest.mark.asyncio
async def test_kira_defect_triage_live(db_session, system_ctx) -> None:
    if not any_live_provider_configured():
        pytest.skip("No live provider API key configured")

    os.environ.setdefault("MODEL_PRODUCT_DECOMPOSITION", os.environ.get("MODEL_DEFAULT", ""))
    from core.config.settings import clear_settings_cache
    from core.runtime.model_policy import clear_models_config_cache

    clear_settings_cache()
    clear_models_config_cache()

    from core.product_model.defects.service import DefectService

    trusted = await seed_trusted_project(db_session, DEFECT_REPO, TRUSTED_SEED_DEFECT, system_ctx)
    defect = await DefectService().intake(
        db_session,
        project_id=trusted.project_id,
        title="CLOSED ticket 500",
        description="PATCH on CLOSED ticket returns HTTP 500 instead of 409",
        source_type="test",
        external_ref=f"live-triage-{uuid.uuid4().hex[:12]}",
        inbound_event_id=None,
        ctx=system_ctx,
    )
    assert defect.delivery_cycle_id is not None
    worker = ExecutionWorker(worker_id="live-defect-triage")
    admission = AdmissionService()
    with patch("core.runtime.model_router.build_providers", side_effect=build_providers):
        for _ in range(80):
            await admission.admit_batch(db_session, 4, system_ctx)
            for _ in range(4):
                await worker.run_once(db_session, system_ctx)
            row = (
                await db_session.execute(select(Defect).where(Defect.id == defect.id))
            ).scalar_one()
            if row.status == "TRIAGED":
                break
            live = (
                await db_session.execute(
                    select(Execution).where(
                        Execution.delivery_cycle_id == defect.delivery_cycle_id,
                        Execution.agent_profile == "kira.defect_triage",
                        Execution.status == ExecutionStatus.COMPLETED,
                    )
                )
            ).scalar_one_or_none()
            if live is not None and row.triage:
                break
    await db_session.refresh(defect)
    assert defect.status == "TRIAGED", defect.status
    assert defect.triage
    assert defect.severity
