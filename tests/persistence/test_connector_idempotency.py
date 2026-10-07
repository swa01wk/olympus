from __future__ import annotations

import pytest
from core.domain.connectors.models import ConnectorActionRecord
from core.integrations.connectors.base import ConnectorAction
from core.integrations.connectors.registry import get_connector_registry
from sqlalchemy import func, select

pytestmark = pytest.mark.persistence


@pytest.mark.asyncio
async def test_connector_idempotency_single_effect(db_session, system_ctx) -> None:
    from core.domain.projects.models import Project
    from core.repositories.materialization import RepositoryMaterializationService
    from core.repositories.service import RepositoryService

    project = Project(key="idem-proj", name="Idem")
    db_session.add(project)
    await db_session.flush()
    repo = await RepositoryService().declare_managed(db_session, project.id, system_ctx)
    await RepositoryMaterializationService().provision_managed(db_session, repo.id, system_ctx)
    registry = get_connector_registry()
    logical = f"projects/{project.id}/repo"
    action = ConnectorAction(
        connector="git_local",
        action="resolve_head",
        target_resource=logical,
        inputs={"logical_location": logical, "branch": repo.default_branch},
        idempotency_key=f"head-idem:{repo.id}",
        correlation_id="idem",
        expected_result_schema="HeadResult",
    )
    first, _ = await registry.execute_with_persistence(
        db_session, action, actor_id=system_ctx.actor.id
    )
    second, _ = await registry.execute_with_persistence(
        db_session, action, actor_id=system_ctx.actor.id
    )
    assert first.normalized_result == second.normalized_result
    count = await db_session.scalar(
        select(func.count())
        .select_from(ConnectorActionRecord)
        .where(ConnectorActionRecord.idempotency_key == action.idempotency_key)
    )
    assert count == 1
