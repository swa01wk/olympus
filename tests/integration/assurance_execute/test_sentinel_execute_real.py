"""Phase 09 §12 — real pytest via ``sentinel.execute`` in verification worktree."""

from __future__ import annotations

import pytest
from core.assurance.enums import EvidenceProducer, EvidenceResult
from core.assurance.models import Evidence
from sqlalchemy import select
from tests.fixtures.assurance_harness import ready_ic_with_sentinel_evidence

pytestmark = [pytest.mark.integration, pytest.mark.git]


@pytest.mark.asyncio
async def test_sentinel_execute_runs_pytest_and_records_pass_evidence(
    db_session,
    system_ctx,
) -> None:
    ic, _, _ = await ready_ic_with_sentinel_evidence(
        db_session, system_ctx, project_key="p9-real-exec", passing=True
    )
    rows = (
        (
            await db_session.execute(
                select(Evidence).where(
                    Evidence.integration_candidate_id == ic.id,
                    Evidence.producer == EvidenceProducer.SENTINEL,
                )
            )
        )
        .scalars()
        .all()
    )
    assert rows, "sentinel.execute should persist evidence"
    assert all(r.result == EvidenceResult.PASS for r in rows)
    assert all(r.commit_sha == ic.integrated_sha for r in rows)
    assert all(not (r.details or {}).get("stub") for r in rows)
