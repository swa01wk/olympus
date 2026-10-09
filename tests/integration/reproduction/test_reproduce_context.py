"""sentinel.reproduce contracts carry the triage plan plus index summary and code excerpts."""

from __future__ import annotations

from pathlib import Path

import pytest
from core.commands.context import CommandContext
from core.domain.delivery_cycles.models import DeliveryCycle
from core.domain.task_contracts.models import TaskContract
from core.domain.tasks.models import Task
from core.product_model.defects.service import DefectService
from sqlalchemy import select
from tests.journey.bug_fix_helpers import maybe_apply_triage_fallback
from tests.journey.seed import seed_trusted_project

pytestmark = [pytest.mark.integration, pytest.mark.asyncio]

DEFECT_REPO = (
    Path(__file__).resolve().parents[2] / "fixtures" / "repos" / "supportdesk_defect_closed_update"
)
TRUSTED_SEED_DEFECT = (
    Path(__file__).resolve().parents[2] / "fixtures" / "supportdesk" / "trusted_seed_defect.yaml"
)


async def test_reproduce_contract_snapshot_has_code_context(
    db_session, system_ctx: CommandContext
) -> None:
    trusted = await seed_trusted_project(db_session, DEFECT_REPO, TRUSTED_SEED_DEFECT, system_ctx)
    defect = await DefectService().intake(
        db_session,
        project_id=trusted.project_id,
        title="CLOSED ticket 500",
        description="PATCH on CLOSED ticket returns 500 not 409",
        source_type="test",
        external_ref="repro-context-1",
        inbound_event_id=None,
        ctx=system_ctx,
    )
    cycle_id = defect.delivery_cycle_id
    assert cycle_id is not None
    assert await maybe_apply_triage_fallback(db_session, cycle_id, system_ctx)
    cycle = await db_session.get(DeliveryCycle, cycle_id)
    assert cycle is not None and cycle.state == "REPRODUCTION"

    task = (
        await db_session.execute(
            select(Task).where(
                Task.delivery_cycle_id == cycle_id, Task.title == "Author reproduction test"
            )
        )
    ).scalar_one()
    contract = await db_session.get(TaskContract, task.current_contract_id)
    assert contract is not None
    snap = contract.body["_snapshot"]

    assert '"observed_symptom_signature"' in snap["triage_json"]
    assert snap["defect_description"] == "PATCH on CLOSED ticket returns 500 not 409"
    # The triage step says /tickets/{id}; the index route is /tickets/{ticket_id}.
    assert snap["index_summary"].splitlines()[0].startswith("ROUTE PATCH /tickets/{ticket_id}")
    excerpt = snap["code_excerpt"]
    assert "# --- app/api/tickets.py ---" in excerpt, "the reproduced route's handler"
    assert "# --- app/main.py ---" in excerpt, "the app entry point shows the import path"
    assert "TestClient" in excerpt, "an existing test shows client and setup conventions"
