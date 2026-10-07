from __future__ import annotations

import pytest
from core.domain.projects.service import ProjectService
from core.product_model.changes.service import ChangeRequestService
from core.repositories.service import RepositoryService
from sqlalchemy import func, select


@pytest.mark.asyncio
async def test_change_request_idempotent_external_ref(db_session, system_ctx) -> None:
    project = await ProjectService().create(db_session, "CR-IDEM", "CR Idem", None, system_ctx)
    repo = await RepositoryService().declare_managed(db_session, project.id, system_ctx)
    await RepositoryService().record_materialization(
        db_session, repo.id, "0" * 40, "main", system_ctx
    )
    svc = ChangeRequestService()
    first = await svc.intake(
        db_session,
        project_id=project.id,
        title="Priority",
        description="Add ticket priority",
        source_type="change_request_api",
        external_ref="JIRA-42",
        inbound_event_id=None,
        ctx=system_ctx,
    )
    second = await svc.intake(
        db_session,
        project_id=project.id,
        title="Priority",
        description="Add ticket priority",
        source_type="change_request_api",
        external_ref="JIRA-42",
        inbound_event_id=None,
        ctx=system_ctx,
    )
    assert first.id == second.id
    from core.product_model.changes.models import ChangeRequest

    count = await db_session.scalar(select(func.count()).select_from(ChangeRequest))
    assert count == 1
