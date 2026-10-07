"""Live sentinel.reproduce authors a reproduction test (Phase 15 §11)."""

from __future__ import annotations

import os
import uuid
from pathlib import Path
from unittest.mock import patch

import pytest
from core.domain.delivery_cycles.service import DeliveryCycleService
from core.domain.enums import ExecutionStatus
from core.domain.executions.models import Execution
from core.execution.worker import ExecutionWorker
from core.runtime.model_router import build_providers
from core.scheduler.admission import AdmissionService
from sqlalchemy import select
from tests.journey.bug_fix_helpers import maybe_apply_triage_fallback
from tests.journey.seed import seed_trusted_project
from tests.live_credentials import any_live_provider_configured

pytestmark = [
    pytest.mark.live_llm,
    pytest.mark.asyncio,
    pytest.mark.skipif(
        os.environ.get("LLM_LIVE_TESTS") != "1",
        reason="Set LLM_LIVE_TESTS=1 for live sentinel.reproduce test",
    ),
]

DEFECT_REPO = (
    Path(__file__).resolve().parents[3] / "fixtures" / "repos" / "supportdesk_defect_closed_update"
)
TRUSTED_SEED_DEFECT = (
    Path(__file__).resolve().parents[3] / "fixtures" / "supportdesk" / "trusted_seed_defect.yaml"
)


@pytest.mark.asyncio
async def test_sentinel_reproduce_live(db_session, system_ctx) -> None:
    if not any_live_provider_configured():
        pytest.skip("No live provider API key configured")

    os.environ.setdefault("MODEL_VERIFICATION_PLANNING", os.environ.get("MODEL_DEFAULT", ""))
    from core.config.settings import clear_settings_cache
    from core.runtime.model_policy import clear_models_config_cache

    clear_settings_cache()
    clear_models_config_cache()

    from core.domain.delivery_cycles.models import DeliveryCycle
    from core.product_model.defects.service import DefectService

    trusted = await seed_trusted_project(db_session, DEFECT_REPO, TRUSTED_SEED_DEFECT, system_ctx)
    defect = await DefectService().intake(
        db_session,
        project_id=trusted.project_id,
        title="CLOSED ticket 500",
        description="PATCH on CLOSED ticket returns HTTP 500",
        source_type="test",
        external_ref=f"live-repro-{uuid.uuid4().hex[:12]}",
        inbound_event_id=None,
        ctx=system_ctx,
    )
    cycle_id = defect.delivery_cycle_id
    assert cycle_id is not None
    await maybe_apply_triage_fallback(db_session, cycle_id, system_ctx)
    cycle = await db_session.get(DeliveryCycle, cycle_id)
    assert cycle is not None
    if cycle.state == "TRIAGE":
        await DeliveryCycleService().run_command(
            db_session, cycle_id, "start_reproduction", "TRIAGE", system_ctx
        )

    worker = ExecutionWorker(worker_id="live-sentinel-repro")
    admission = AdmissionService()
    with patch("core.runtime.model_router.build_providers", side_effect=build_providers):
        for _ in range(100):
            await admission.admit_batch(db_session, 6, system_ctx)
            for _ in range(6):
                await worker.run_once(db_session, system_ctx)
            done = (
                await db_session.execute(
                    select(Execution).where(
                        Execution.delivery_cycle_id == cycle_id,
                        Execution.agent_profile == "sentinel.reproduce",
                        Execution.status == ExecutionStatus.COMPLETED,
                    )
                )
            ).scalar_one_or_none()
            if done is not None and done.output:
                break
    exec_row = (
        await db_session.execute(
            select(Execution).where(
                Execution.delivery_cycle_id == cycle_id,
                Execution.agent_profile == "sentinel.reproduce",
            )
        )
    ).scalar_one_or_none()
    assert exec_row is not None, "expected sentinel.reproduce execution"
    assert exec_row.status == ExecutionStatus.COMPLETED, exec_row.failure_detail
    out = exec_row.output or {}
    assert out.get("relative_path") or out.get("test_source")
