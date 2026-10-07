from __future__ import annotations

import pytest
from core.domain.exceptions import DomainError
from core.release.service import ReleaseService
from tests.fixtures.release_harness import ready_eligible_release

pytestmark = [pytest.mark.persistence, pytest.mark.git]


@pytest.mark.asyncio
async def test_approve_release_rejects_when_manifest_hash_drifted(
    db_session,
    system_ctx,
    operator_ctx,
) -> None:
    _, _, release = await ready_eligible_release(
        db_session, system_ctx, operator_ctx, project_key="rel-hash"
    )
    from core.domain.approvals.models import Approval

    approval = await db_session.get(Approval, release.approval_id)
    assert approval is not None
    approval.subject_hash = "0" * 64
    await db_session.flush()
    with pytest.raises(DomainError) as exc:
        await ReleaseService().approve_release(db_session, release.id, operator_ctx)
    assert exc.value.code == "MANIFEST_CHANGED"
