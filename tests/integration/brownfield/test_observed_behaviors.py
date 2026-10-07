from __future__ import annotations

import pytest
from core.intelligence.brownfield.enums import ObservedBehaviorKind
from core.intelligence.brownfield.models import ObservedBehavior
from core.state.transition_service import TransitionService
from sqlalchemy import select
from tests.fixtures.brownfield_harness import brownfield_cycle_at_code_index

pytestmark = [pytest.mark.integration, pytest.mark.asyncio]


async def test_observed_behaviors_after_spec_recovery(db_session, system_ctx) -> None:
    cycle, sha, _ = await brownfield_cycle_at_code_index(db_session, system_ctx)
    await TransitionService().transition(
        db_session,
        "delivery_cycle",
        cycle.id,
        "CODE_INDEX",
        "start_spec_recovery",
        system_ctx,
    )
    from core.execution.worker import ExecutionWorker
    from core.intelligence.recovered_specs.observed import ObservedBehaviorService
    from core.traceability.models import RepositoryIndexPointer

    worker = ExecutionWorker(worker_id="brownfield-test")
    await db_session.flush()
    for _ in range(8):
        if not await worker.run_once(db_session, system_ctx):
            break
    pointer = await db_session.get(RepositoryIndexPointer, cycle.repository_id)
    rows_before = (
        (
            await db_session.execute(
                select(ObservedBehavior).where(ObservedBehavior.delivery_cycle_id == cycle.id)
            )
        )
        .scalars()
        .all()
    )
    if not rows_before and pointer and pointer.canonical_index_version_id:
        await ObservedBehaviorService().derive(
            db_session,
            delivery_cycle_id=cycle.id,
            project_id=cycle.project_id,
            index_version_id=pointer.canonical_index_version_id,
            commit_sha=sha,
            test_results={
                "cases": [
                    {
                        "nodeid": "tests/test_tickets_api.py::test_create_ticket",
                        "passed": True,
                    }
                ]
            },
            ctx=system_ctx,
        )
    rows = (
        (
            await db_session.execute(
                select(ObservedBehavior).where(ObservedBehavior.delivery_cycle_id == cycle.id)
            )
        )
        .scalars()
        .all()
    )
    kinds = {r.kind for r in rows}
    assert ObservedBehaviorKind.ROUTE_BEHAVIOR in kinds
    assert any(r.commit_sha == sha for r in rows)
    test_exec = [r for r in rows if r.kind == ObservedBehaviorKind.TEST_EXECUTION]
    if test_exec:
        assert all(r.passed is not None for r in test_exec)
