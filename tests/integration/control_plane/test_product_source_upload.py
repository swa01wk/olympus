from __future__ import annotations

from pathlib import Path
from uuid import uuid4

import pytest
from httpx import ASGITransport, AsyncClient


@pytest.mark.integration
async def test_upload_prd_creates_source_and_inbound_event(
    control_app,
    operator_token,
    async_engine,
) -> None:
    from core.domain.actors.models import Actor
    from core.domain.enums import ActorKind, ActorRole
    from core.domain.projects.models import Project
    from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

    factory = async_sessionmaker(bind=async_engine, class_=AsyncSession, expire_on_commit=False)
    async with factory() as session, session.begin():
        actor = Actor(kind=ActorKind.HUMAN, name="op", roles=[ActorRole.OPERATOR.value])
        session.add(actor)
        project = Project(key=f"prd-{uuid4().hex[:6]}", name="PRD Test")
        session.add(project)
        await session.flush()
        project_id = project.id

    prd = Path(__file__).resolve().parents[2] / "fixtures" / "supportdesk" / "PRD.md"
    transport = ASGITransport(app=control_app)
    async with AsyncClient(
        transport=transport,
        base_url="http://test",
        headers={"Authorization": f"Bearer {operator_token}"},
    ) as client:
        r1 = await client.post(
            f"/projects/{project_id}/sources",
            files={"file": ("PRD.md", prd.read_bytes(), "text/markdown")},
            headers={"Idempotency-Key": "upload-1"},
        )
        assert r1.status_code == 200, r1.text
        data = r1.json()
        assert data["status"] == "ACCEPTED"
        source_id = data["result"]["product_source_id"]

        r2 = await client.post(
            f"/projects/{project_id}/sources",
            files={"file": ("PRD.md", prd.read_bytes(), "text/markdown")},
            headers={"Idempotency-Key": "upload-1"},
        )
        assert r2.json()["status"] == "DUPLICATE"

        listed = await client.get(f"/projects/{project_id}/sources")
        assert len(listed.json()) == 1

        changed = prd.read_text() + "\n<!-- v2 -->\n"
        r3 = await client.post(
            f"/projects/{project_id}/sources",
            files={"file": ("PRD.md", changed.encode(), "text/markdown")},
            headers={"Idempotency-Key": "upload-2"},
        )
        assert r3.status_code == 200
        assert r3.json()["result"]["version"] == 2

        content = await client.get(f"/projects/{project_id}/sources/{source_id}/content")
        assert "SupportDesk" in content.json()["text"]
