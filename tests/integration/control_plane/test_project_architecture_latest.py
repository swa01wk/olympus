from __future__ import annotations

import uuid
from uuid import uuid4

import pytest


@pytest.mark.integration
@pytest.mark.asyncio
async def test_project_architecture_latest_returns_version_under_review(
    api_client, async_engine
) -> None:
    from core.domain.enums import SpecStatus
    from core.planning.models import Architecture
    from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

    key = f"arl-{uuid4().hex[:6]}"
    project = await api_client.post("/projects", json={"key": key, "name": "Arch latest"})
    project_id = uuid.UUID(project.json()["id"])

    none_approved = await api_client.get(f"/projects/{project_id}/architecture")
    none_latest = await api_client.get(f"/projects/{project_id}/architecture?latest=true")
    assert none_approved.status_code == 404
    assert none_latest.status_code == 404

    factory = async_sessionmaker(bind=async_engine, class_=AsyncSession, expire_on_commit=False)
    async with factory() as session, session.begin():
        for version, status in ((1, SpecStatus.APPROVED), (2, SpecStatus.PROPOSED)):
            session.add(
                Architecture(
                    project_id=project_id,
                    version=version,
                    status=status,
                    kind="GREENFIELD",
                    body={"v": version},
                    content_hash=f"{key}-{version}",
                )
            )

    approved = await api_client.get(f"/projects/{project_id}/architecture")
    latest = await api_client.get(f"/projects/{project_id}/architecture?latest=true")

    assert approved.status_code == 200
    assert (approved.json()["version"], approved.json()["status"]) == (1, "APPROVED")
    assert latest.status_code == 200
    assert (latest.json()["version"], latest.json()["status"]) == (2, "PROPOSED")
