from __future__ import annotations

import uuid
from pathlib import Path

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from tests.fixtures.product_model_harness import supportdesk_decomposition

pytestmark = [pytest.mark.integration]


@pytest.mark.asyncio
async def test_upload_inbound_audit_and_guards(api_client, async_engine) -> None:
    project = await api_client.post("/projects", json={"key": "pm-api", "name": "PM API"})
    assert project.status_code == 201
    project_id = project.json()["id"]
    cycle = await api_client.post(
        f"/projects/{project_id}/delivery-cycles",
        json={"type": "GREENFIELD_BUILD", "objective": "product model API"},
    )
    assert cycle.status_code == 201
    cycle_id = cycle.json()["id"]

    blocked = await api_client.post(
        f"/delivery-cycles/{cycle_id}/commands/start_product_modeling",
        json={"expected_state": "DISCOVERY"},
    )
    assert blocked.status_code == 422
    assert "NO_PRODUCT_SOURCE" in blocked.text

    prd = Path(__file__).resolve().parents[2] / "fixtures" / "supportdesk" / "PRD.md"
    upload = await api_client.post(
        f"/projects/{project_id}/sources",
        params={"delivery_cycle_id": cycle_id},
        files={"file": ("PRD.md", prd.read_bytes(), "text/markdown")},
        headers={"Idempotency-Key": f"pm-upload-{uuid.uuid4().hex[:8]}"},
    )
    assert upload.status_code == 200, upload.text
    body = upload.json()
    assert body["status"] == "ACCEPTED"
    assert body["result"]["duplicate"] is False
    source_id = body["result"]["product_source_id"]

    events = await api_client.get("/integrations/inbound-events")
    assert events.status_code == 200
    assert any(e["status"] == "ACCEPTED" for e in events.json())

    event_id = next(e["id"] for e in events.json() if e["status"] == "ACCEPTED")
    audit = await api_client.get(
        "/audit", params={"target_type": "inbound_event", "target_id": event_id}
    )
    assert audit.status_code == 200
    assert any(row["action"] == "inbound_event.accepted" for row in audit.json())

    dup_hash = await api_client.post(
        f"/projects/{project_id}/sources",
        params={"delivery_cycle_id": cycle_id},
        files={"file": ("PRD.md", prd.read_bytes(), "text/markdown")},
        headers={"Idempotency-Key": f"pm-dup-hash-{uuid.uuid4().hex[:8]}"},
    )
    assert dup_hash.status_code == 200
    assert dup_hash.json()["result"]["duplicate"] is True

    advance = await api_client.post(
        f"/delivery-cycles/{cycle_id}/commands/start_product_modeling",
        json={"expected_state": "DISCOVERY"},
    )
    assert advance.status_code == 200, advance.text
    assert advance.json()["to_state"] == "PRODUCT_MODEL"

    factory = async_sessionmaker(bind=async_engine, class_=AsyncSession, expire_on_commit=False)
    async with factory() as session, session.begin():
        from core.commands.context import CommandContext
        from core.domain.actors.models import Actor
        from core.domain.enums import ActorKind, ClarificationStatus
        from core.domain.executions.models import Clarification
        from core.product_model.service import ProductModelService
        from sqlalchemy import select

        actor = (
            await session.execute(select(Actor).where(Actor.kind == ActorKind.HUMAN).limit(1))
        ).scalar_one()
        ctx = CommandContext(actor=actor, correlation_id="pm-seed")
        await ProductModelService().persist_proposal(
            session,
            project_id=uuid.UUID(project_id),
            delivery_cycle_id=uuid.UUID(cycle_id),
            product_source_version_id=uuid.UUID(source_id),
            execution_id=None,
            proposal=supportdesk_decomposition(),
            ctx=ctx,
        )
        session.add(
            Clarification(
                key="CL-BLOCK",
                project_id=uuid.UUID(project_id),
                delivery_cycle_id=uuid.UUID(cycle_id),
                question="blocking?",
                context={},
                options=[],
                blocking=True,
                status=ClarificationStatus.OPEN,
            )
        )

    caps = await api_client.get(f"/projects/{project_id}/capabilities")
    assert caps.status_code == 200
    assert len(caps.json()) >= 1
    features = await api_client.get(f"/projects/{project_id}/features")
    assert len(features.json()) >= 2

    feat_id = features.json()[0]["id"]
    specs = await api_client.get(f"/features/{feat_id}/specs")
    assert specs.status_code == 200
    assert specs.json()[0]["status"] == "PROPOSED"

    arch_blocked = await api_client.post(
        f"/delivery-cycles/{cycle_id}/commands/start_architecture",
        json={"expected_state": "PRODUCT_MODEL"},
    )
    assert arch_blocked.status_code == 422
    assert "BLOCKING_CLARIFICATION_OPEN" in arch_blocked.text or "SCOPE" in arch_blocked.text

    async with factory() as session, session.begin():
        from core.domain.executions.models import Clarification as ClRow
        from sqlalchemy import select

        row = (
            await session.execute(
                select(ClRow).where(ClRow.delivery_cycle_id == uuid.UUID(cycle_id))
            )
        ).scalar_one()
        row.status = ClarificationStatus.ANSWERED
        row.answer = "closed tickets return 409"

    all_specs: list[str] = []
    for feat in features.json():
        spec_list = await api_client.get(f"/features/{feat['id']}/specs")
        all_specs.extend(s["id"] for s in spec_list.json())

    scope_req = await api_client.post(
        f"/delivery-cycles/{cycle_id}/scope/approval-request",
        json={"feature_spec_ids": all_specs},
    )
    assert scope_req.status_code == 200, scope_req.text
    approval_id = scope_req.json()["approval_id"]

    decide = await api_client.post(
        f"/approvals/{approval_id}/decision",
        json={"decision": "APPROVED", "note": "scope OK"},
    )
    assert decide.status_code == 200
    assert decide.json()["status"] == "APPROVED"

    spec_detail = await api_client.get(f"/specs/{all_specs[0]}")
    assert spec_detail.status_code == 200
    assert spec_detail.json()["status"] == "APPROVED"
    assert len(spec_detail.json()["acceptance_criteria"]) >= 1
    assert spec_detail.json()["acceptance_criteria"][0]["mandatory"] is True

    arch = await api_client.post(
        f"/delivery-cycles/{cycle_id}/commands/start_architecture",
        json={"expected_state": "PRODUCT_MODEL"},
    )
    assert arch.status_code == 200, arch.text
    assert arch.json()["to_state"] == "ARCHITECTURE"

    draft = await api_client.post(
        f"/features/{features.json()[0]['id']}/specs",
        json={
            "body": {
                "behavior": "edited",
                "summary": "v2 draft",
                "inputs": ["x"],
                "outputs": ["y"],
                "rules": ["r"],
            }
        },
    )
    assert draft.status_code == 200
    assert int(draft.json()["version"]) >= 2


@pytest.mark.asyncio
@pytest.mark.security
async def test_agent_cannot_approve_spec(agent_client, api_client, async_engine) -> None:
    import uuid

    from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
    from tests.fixtures.product_model_harness import supportdesk_decomposition

    project = await api_client.post("/projects", json={"key": "sec-spec", "name": "Sec"})
    project_id = project.json()["id"]
    cycle = await api_client.post(
        f"/projects/{project_id}/delivery-cycles",
        json={"type": "GREENFIELD_BUILD", "objective": "sec"},
    )
    cycle_id = cycle.json()["id"]
    factory = async_sessionmaker(bind=async_engine, class_=AsyncSession, expire_on_commit=False)
    async with factory() as session, session.begin():
        from core.commands.context import CommandContext
        from core.domain.actors.models import Actor
        from core.domain.enums import ActorKind
        from core.product_model.models import FeatureSpec, ProductSource
        from core.product_model.service import ProductModelService
        from core.product_model.sources.service import ProductSourceService
        from sqlalchemy import select

        actor = (
            await session.execute(select(Actor).where(Actor.kind == ActorKind.HUMAN).limit(1))
        ).scalar_one()
        ctx = CommandContext(actor=actor, correlation_id="sec-spec")
        ingest = await ProductSourceService().ingest(
            session,
            project_id=uuid.UUID(project_id),
            lineage_key="sec",
            source_type="PRD",
            title="t",
            mime_type="text/plain",
            content_hash="sec12345678901234567890123456789012",
            raw_storage_ref="inbound/x",
            text="hello",
            ctx=ctx,
            delivery_cycle_id=uuid.UUID(cycle_id),
        )
        source = await session.get(ProductSource, uuid.UUID(ingest["product_source_id"]))
        assert source is not None
        await ProductModelService().persist_proposal(
            session,
            project_id=uuid.UUID(project_id),
            delivery_cycle_id=uuid.UUID(cycle_id),
            product_source_version_id=source.id,
            execution_id=None,
            proposal=supportdesk_decomposition(),
            ctx=ctx,
        )
        spec = (await session.execute(select(FeatureSpec).limit(1))).scalar_one()

    denied = await agent_client.post(f"/specs/{spec.id}/approve")
    assert denied.status_code in {401, 403, 422}


@pytest.mark.asyncio
@pytest.mark.security
async def test_agent_cannot_request_scope_approval(agent_client, api_client) -> None:
    project = await api_client.post("/projects", json={"key": "sec-pm", "name": "Sec"})
    project_id = project.json()["id"]
    cycle = await api_client.post(
        f"/projects/{project_id}/delivery-cycles",
        json={"type": "GREENFIELD_BUILD", "objective": "sec"},
    )
    cycle_id = cycle.json()["id"]
    denied = await agent_client.post(
        f"/delivery-cycles/{cycle_id}/scope/approval-request",
        json={"feature_spec_ids": [str(uuid.uuid4())]},
    )
    assert denied.status_code in {401, 403, 422}


@pytest.mark.asyncio
async def test_unauthenticated_inbound_rejected(control_app, async_engine) -> None:
    transport = ASGITransport(app=control_app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post(
            "/integrations/inbound/document_upload",
            json={"project_id": str(uuid.uuid4()), "json_body": {"title": "t", "text": "x"}},
        )
    assert resp.status_code in {401, 422}
    factory = async_sessionmaker(bind=async_engine, class_=AsyncSession, expire_on_commit=False)
    async with factory() as session:
        from core.domain.enums import InboundEventStatus
        from core.integrations.inbound.models import InboundEvent
        from sqlalchemy import select

        rejected = await session.execute(
            select(InboundEvent).where(InboundEvent.status == InboundEventStatus.REJECTED)
        )
        assert rejected.scalars().first() is not None or resp.status_code == 401
