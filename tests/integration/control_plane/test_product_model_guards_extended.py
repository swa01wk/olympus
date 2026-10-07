from __future__ import annotations

import uuid
from pathlib import Path
from uuid import uuid4

import pytest


@pytest.mark.integration
@pytest.mark.asyncio
async def test_start_product_modeling_succeeds_after_upload(api_client) -> None:
    key = f"pm-{uuid4().hex[:6]}"
    project = await api_client.post("/projects", json={"key": key, "name": "PM"})
    project_id = project.json()["id"]
    cycle = await api_client.post(
        f"/projects/{project_id}/delivery-cycles",
        json={"type": "GREENFIELD_BUILD", "objective": "pm"},
    )
    cycle_id = cycle.json()["id"]
    prd = Path(__file__).resolve().parents[2] / "fixtures" / "supportdesk" / "PRD.md"
    up = await api_client.post(
        f"/projects/{project_id}/sources",
        params={"delivery_cycle_id": cycle_id},
        files={"file": ("PRD.md", prd.read_bytes(), "text/markdown")},
        headers={"Idempotency-Key": f"pm-{uuid4().hex[:8]}"},
    )
    assert up.status_code == 200
    cmd = await api_client.post(
        f"/delivery-cycles/{cycle_id}/commands/start_product_modeling",
        json={"expected_state": "DISCOVERY"},
    )
    assert cmd.status_code == 200, cmd.text
    assert cmd.json()["to_state"] == "PRODUCT_MODEL"


@pytest.mark.integration
@pytest.mark.asyncio
async def test_start_architecture_fails_on_scope_hash_mismatch(api_client, async_engine) -> None:
    from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

    hkey = f"hash-{uuid4().hex[:6]}"
    project = await api_client.post("/projects", json={"key": hkey, "name": "H"})
    project_id = project.json()["id"]
    cycle = await api_client.post(
        f"/projects/{project_id}/delivery-cycles",
        json={"type": "GREENFIELD_BUILD", "objective": "hash"},
    )
    cycle_id = cycle.json()["id"]
    prd = Path(__file__).resolve().parents[2] / "fixtures" / "supportdesk" / "PRD.md"
    await api_client.post(
        f"/projects/{project_id}/sources",
        params={"delivery_cycle_id": cycle_id},
        files={"file": ("PRD.md", prd.read_bytes(), "text/markdown")},
        headers={"Idempotency-Key": f"h-{uuid4().hex[:8]}"},
    )
    await api_client.post(
        f"/delivery-cycles/{cycle_id}/commands/start_product_modeling",
        json={"expected_state": "DISCOVERY"},
    )

    factory = async_sessionmaker(bind=async_engine, class_=AsyncSession, expire_on_commit=False)
    async with factory() as session, session.begin():
        from core.commands.context import CommandContext
        from core.domain.actors.models import Actor
        from core.domain.enums import ActorKind
        from core.product_model.models import FeatureSpec
        from core.product_model.service import ProductModelService
        from sqlalchemy import select
        from tests.fixtures.product_model_harness import supportdesk_decomposition

        actor = (
            await session.execute(select(Actor).where(Actor.kind == ActorKind.HUMAN).limit(1))
        ).scalar_one()
        ctx = CommandContext(actor=actor, correlation_id="hash-test")
        from core.product_model.models import ProductSource

        source = (
            await session.execute(
                select(ProductSource)
                .where(ProductSource.project_id == uuid.UUID(project_id))
                .limit(1)
            )
        ).scalar_one()
        await ProductModelService().persist_proposal(
            session,
            project_id=uuid.UUID(project_id),
            delivery_cycle_id=uuid.UUID(cycle_id),
            product_source_version_id=source.id,
            execution_id=None,
            proposal=supportdesk_decomposition(),
            ctx=ctx,
        )
        specs = (
            (
                await session.execute(
                    select(FeatureSpec).where(FeatureSpec.project_id == uuid.UUID(project_id))
                )
            )
            .scalars()
            .all()
        )
        spec_ids = [s.id for s in specs]

    scope_req = await api_client.post(
        f"/delivery-cycles/{cycle_id}/scope/approval-request",
        json={"feature_spec_ids": [str(i) for i in spec_ids]},
    )
    assert scope_req.status_code == 200, scope_req.text
    approval_id = scope_req.json()["approval_id"]
    decide = await api_client.post(
        f"/approvals/{approval_id}/decision",
        json={"decision": "APPROVED", "note": "ok"},
    )
    assert decide.status_code == 200

    async with factory() as session, session.begin():
        from core.domain.approvals.models import Approval
        from core.product_model.models import ScopeSet

        scope = (
            await session.execute(
                select(ScopeSet).where(ScopeSet.delivery_cycle_id == uuid.UUID(cycle_id))
            )
        ).scalar_one()
        scope.content_hash = "tampered"
        appr = await session.get(Approval, approval_id)
        assert appr is not None

    arch = await api_client.post(
        f"/delivery-cycles/{cycle_id}/commands/start_architecture",
        json={"expected_state": "PRODUCT_MODEL"},
    )
    assert arch.status_code == 422
    assert "SCOPE_HASH_MISMATCH" in arch.text
