from __future__ import annotations

import uuid

import pytest
from core.domain.audit.append import append_audit
from core.domain.enums import ActorKind
from core.security.audit_chain import verify_project_chain

pytestmark = pytest.mark.persistence


@pytest.mark.asyncio
async def test_audit_chain_links(db_session, system_actor) -> None:
    from core.domain.projects.models import Project

    project = Project(key="audit-chain", name="Audit Chain")
    db_session.add(project)
    await db_session.flush()
    pid = project.id
    for i in range(3):
        await append_audit(
            db_session,
            actor_id=system_actor.id,
            actor_kind=ActorKind.SYSTEM,
            action=f"act-{i}",
            target_type="t",
            target_id=str(uuid.uuid4()),
            correlation_id="c",
            project_id=pid,
        )
    report = await verify_project_chain(db_session, pid)
    assert report.valid
    assert report.rows_checked == 3
