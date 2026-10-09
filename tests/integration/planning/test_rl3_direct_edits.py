"""RL3.7 — human direct edits of PROPOSED architecture and implementation specs."""

from __future__ import annotations

import uuid
from collections.abc import AsyncIterator, Awaitable, Callable

import pytest
from apps.control_api.main import create_app
from core.commands.context import CommandContext
from core.config.settings import OlympusSettings
from core.domain.actors.models import Actor
from core.domain.approvals.models import Approval
from core.domain.delivery_cycles.models import DeliveryCycle
from core.domain.enums import (
    ApprovalStatus,
    ApprovalType,
    DeliveryCycleType,
    KnowledgeClass,
    SpecStatus,
)
from core.domain.events.models import DomainEvent
from core.domain.exceptions import DomainError
from core.domain.projects.models import Project
from core.planning.architecture.service import ArchitectureService
from core.planning.implementation_specs.service import ImplementationSpecService
from core.planning.models import Architecture, ArchitectureContract, ImplementationSpec
from core.planning.schemas import ImplementationSpecBody
from core.product_model.models import FeatureSpec, KnowledgeItem
from core.security.tokens import create_api_token
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from tests.fixtures.planning_harness import (
    create_ticket_implementation_spec,
    supportdesk_architecture_proposal,
)
from tests.fixtures.planning_workflow_harness import (
    seed_approved_architecture,
    seed_supportdesk_product_and_approved_scope,
)

pytestmark = [pytest.mark.integration, pytest.mark.asyncio]

ClientFactory = Callable[..., Awaitable[AsyncClient]]


@pytest.fixture
async def api_as(db_session: AsyncSession, postgres_url: str, tmp_path) -> AsyncIterator:
    app = create_app(
        settings=OlympusSettings(
            database_url=postgres_url,
            olympus_workspace_root=tmp_path / "ws",
            olympus_storage_root=tmp_path / "storage",
            olympus_env="test",
        )
    )
    app.state.session_factory = async_sessionmaker(
        bind=await db_session.connection(),
        class_=AsyncSession,
        expire_on_commit=False,
        join_transaction_mode="create_savepoint",
    )
    clients: list[AsyncClient] = []

    async def _make(actor: Actor, scopes: list[str] | None = None) -> AsyncClient:
        raw, _ = await create_api_token(db_session, actor_id=actor.id, scopes=scopes)
        client = AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
            headers={"Authorization": f"Bearer {raw}"},
        )
        clients.append(client)
        return client

    yield _make
    for client in clients:
        await client.aclose()


async def _cycle(
    session: AsyncSession, project: Project, state: str, ctx: CommandContext
) -> DeliveryCycle:
    cycle = DeliveryCycle(
        project_id=project.id,
        key=f"RL3-{uuid.uuid4().hex[:6]}",
        type=DeliveryCycleType.GREENFIELD_BUILD,
        objective="rl3 direct edits",
        state=state,
        state_version=0,
        opened_by_actor_id=ctx.actor.id,
    )
    session.add(cycle)
    await session.flush()
    return cycle


async def _pending(
    session: AsyncSession, approval_type: ApprovalType, subject_id: uuid.UUID
) -> list[Approval]:
    rows = await session.execute(
        select(Approval).where(
            Approval.approval_type == approval_type,
            Approval.subject_id == subject_id,
        )
    )
    return list(rows.scalars())


async def _proposed_architecture(
    session: AsyncSession, project: Project, cycle: DeliveryCycle, ctx: CommandContext
) -> Architecture:
    return await ArchitectureService().persist_proposal(
        session,
        project_id=project.id,
        proposal=supportdesk_architecture_proposal(),
        execution_id=None,
        ctx=ctx,
        delivery_cycle_id=cycle.id,
    )


async def _proposed_implementation_spec(
    session: AsyncSession,
    project: Project,
    cycle: DeliveryCycle,
    system_ctx: CommandContext,
    operator_ctx: CommandContext,
) -> ImplementationSpec:
    await seed_supportdesk_product_and_approved_scope(session, project.id, cycle.id, operator_ctx)
    await seed_approved_architecture(session, project.id, system_ctx)
    feature_spec = (
        await session.execute(
            select(FeatureSpec).where(FeatureSpec.project_id == project.id).limit(1)
        )
    ).scalar_one()
    return await ImplementationSpecService().persist_draft(
        session,
        feature_spec_id=feature_spec.id,
        draft=create_ticket_implementation_spec(),
        execution_id=None,
        ctx=system_ctx,
        delivery_cycle_id=cycle.id,
    )


def _arch_body(**updates: object) -> dict[str, object]:
    body = supportdesk_architecture_proposal().body.model_dump(mode="json")
    body.update(updates)
    return body


def _impl_body(**updates: object) -> dict[str, object]:
    body = create_ticket_implementation_spec().body.model_dump(mode="json")
    body.update(updates)
    return body


async def test_architecture_edit_creates_new_proposed_version(
    db_session, sample_project, system_ctx, operator_ctx, api_as: ClientFactory
) -> None:
    cycle = await _cycle(db_session, sample_project, "ARCHITECTURE", system_ctx)
    v1 = await _proposed_architecture(db_session, sample_project, cycle, system_ctx)
    v1_id, v1_version, cycle_id = v1.id, v1.version, cycle.id
    [old_approval] = await _pending(db_session, ApprovalType.ARCHITECTURE, v1_id)
    assert old_approval.status == ApprovalStatus.PENDING
    old_approval_id = old_approval.id
    client = await api_as(operator_ctx.actor)
    note = "Collapse service guards into one ProjectGuard."

    resp = await client.post(
        f"/architectures/{v1_id}/versions",
        json={
            "body": _arch_body(summary="SupportDesk with a single ProjectGuard"),
            "note": note,
            "delivery_cycle_id": str(cycle_id),
        },
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["version"] == v1_version + 1
    assert data["status"] == "PROPOSED"
    v2_id = uuid.UUID(data["id"])

    db_session.expire_all()
    v1 = await db_session.get(Architecture, v1_id)
    v2 = await db_session.get(Architecture, v2_id)
    assert v1 is not None and v2 is not None
    assert v1.status == SpecStatus.SUPERSEDED
    assert v2.status == SpecStatus.PROPOSED
    assert v2.supersedes_id == v1_id
    assert v2.body["summary"] == "SupportDesk with a single ProjectGuard"
    contracts = (
        await db_session.execute(
            select(ArchitectureContract).where(ArchitectureContract.architecture_id == v2_id)
        )
    ).scalars()
    assert {c.key for c in contracts} == {"create-ticket"}

    old = await db_session.get(Approval, old_approval_id)
    assert old is not None and old.status == ApprovalStatus.CANCELLED
    [new_approval] = await _pending(db_session, ApprovalType.ARCHITECTURE, v2_id)
    assert new_approval.status == ApprovalStatus.PENDING
    assert new_approval.subject_hash == v2.content_hash
    assert new_approval.delivery_cycle_id == cycle_id

    event = (
        await db_session.execute(
            select(DomainEvent).where(
                DomainEvent.aggregate_id == v2_id,
                DomainEvent.event_type == "architecture.edited",
            )
        )
    ).scalar_one()
    assert event.payload["note"] == note
    decisions = (
        await db_session.execute(
            select(KnowledgeItem).where(
                KnowledgeItem.delivery_cycle_id == cycle_id,
                KnowledgeItem.knowledge_class == KnowledgeClass.DECISION,
            )
        )
    ).scalars()
    assert any(note in d.statement for d in decisions)


async def test_architecture_edit_invalid_body_returns_422(
    db_session, sample_project, system_ctx, operator_ctx, api_as: ClientFactory
) -> None:
    cycle = await _cycle(db_session, sample_project, "ARCHITECTURE", system_ctx)
    v1 = await _proposed_architecture(db_session, sample_project, cycle, system_ctx)
    v1_id, cycle_id = v1.id, cycle.id
    client = await api_as(operator_ctx.actor)
    url = f"/architectures/{v1_id}/versions"

    missing_summary = _arch_body()
    del missing_summary["summary"]
    resp = await client.post(
        url, json={"body": missing_summary, "delivery_cycle_id": str(cycle_id)}
    )
    assert resp.status_code == 422, resp.text
    assert "summary: Field required" in resp.json()["detail"]["errors"]

    components = _arch_body()["components"]
    assert isinstance(components, list)
    resp = await client.post(
        url,
        json={
            "body": _arch_body(
                components=[*components, components[0]],
                dependency_rules=["api -> nowhere"],
            ),
            "delivery_cycle_id": str(cycle_id),
        },
    )
    assert resp.status_code == 422, resp.text
    errors = resp.json()["detail"]["errors"]
    assert "duplicate component names" in errors
    assert "dependency rule references unknown layer: api -> nowhere" in errors

    db_session.expire_all()
    v1 = await db_session.get(Architecture, v1_id)
    assert v1 is not None and v1.status == SpecStatus.PROPOSED
    [approval] = await _pending(db_session, ApprovalType.ARCHITECTURE, v1_id)
    assert approval.status == ApprovalStatus.PENDING


async def test_architecture_edit_refused_outside_architecture_stage(
    db_session, sample_project, system_ctx, operator_ctx, api_as: ClientFactory
) -> None:
    cycle = await _cycle(db_session, sample_project, "ARCHITECTURE", system_ctx)
    v1 = await _proposed_architecture(db_session, sample_project, cycle, system_ctx)
    v1_id = v1.id
    cycle.state = "PLANNING"
    other_project = Project(key=f"rl3-other-{uuid.uuid4().hex[:6]}", name="Other")
    db_session.add(other_project)
    await db_session.flush()
    foreign_cycle = await _cycle(db_session, other_project, "ARCHITECTURE", system_ctx)
    cycle_id, foreign_cycle_id = cycle.id, foreign_cycle.id
    client = await api_as(operator_ctx.actor)
    url = f"/architectures/{v1_id}/versions"

    resp = await client.post(url, json={"body": _arch_body(), "delivery_cycle_id": str(cycle_id)})
    assert resp.status_code == 400, resp.text
    assert resp.json()["code"] == "INVALID_STATE"

    resp = await client.post(
        url, json={"body": _arch_body(), "delivery_cycle_id": str(foreign_cycle_id)}
    )
    assert resp.status_code == 404, resp.text

    db_session.expire_all()
    v1 = await db_session.get(Architecture, v1_id)
    assert v1 is not None and v1.status == SpecStatus.PROPOSED


async def test_implementation_spec_edit_creates_new_proposed_version(
    db_session, sample_project, system_ctx, operator_ctx, api_as: ClientFactory
) -> None:
    cycle = await _cycle(db_session, sample_project, "PLANNING", system_ctx)
    v1 = await _proposed_implementation_spec(
        db_session, sample_project, cycle, system_ctx, operator_ctx
    )
    v1_id, v1_version, cycle_id = v1.id, v1.version, cycle.id
    [old_approval] = await _pending(db_session, ApprovalType.IMPLEMENTATION_SPEC, v1_id)
    assert old_approval.status == ApprovalStatus.PENDING
    old_approval_id = old_approval.id
    client = await api_as(operator_ctx.actor)
    note = "Keep ticket validation in the service layer."

    resp = await client.post(
        f"/implementation-specs/{v1_id}/versions",
        json={
            "body": _impl_body(summary="Create ticket with service-layer validation"),
            "note": note,
            "delivery_cycle_id": str(cycle_id),
        },
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["version"] == v1_version + 1
    assert data["status"] == "PROPOSED"
    v2_id = uuid.UUID(data["id"])

    db_session.expire_all()
    v1 = await db_session.get(ImplementationSpec, v1_id)
    v2 = await db_session.get(ImplementationSpec, v2_id)
    assert v1 is not None and v2 is not None
    assert v1.status == SpecStatus.SUPERSEDED
    assert v2.status == SpecStatus.PROPOSED
    assert v2.kind == v1.kind
    assert v2.body["summary"] == "Create ticket with service-layer validation"

    old = await db_session.get(Approval, old_approval_id)
    assert old is not None and old.status == ApprovalStatus.CANCELLED
    [new_approval] = await _pending(db_session, ApprovalType.IMPLEMENTATION_SPEC, v2_id)
    assert new_approval.status == ApprovalStatus.PENDING
    assert new_approval.subject_hash == v2.content_hash

    event = (
        await db_session.execute(
            select(DomainEvent).where(
                DomainEvent.aggregate_id == v2_id,
                DomainEvent.event_type == "implementation_spec.edited",
            )
        )
    ).scalar_one()
    assert event.payload["note"] == note
    decisions = (
        await db_session.execute(
            select(KnowledgeItem).where(
                KnowledgeItem.delivery_cycle_id == cycle_id,
                KnowledgeItem.knowledge_class == KnowledgeClass.DECISION,
            )
        )
    ).scalars()
    assert any(note in d.statement for d in decisions)


async def test_implementation_spec_edit_rejections(
    db_session, sample_project, system_ctx, operator_ctx, api_as: ClientFactory
) -> None:
    cycle = await _cycle(db_session, sample_project, "PLANNING", system_ctx)
    v1 = await _proposed_implementation_spec(
        db_session, sample_project, cycle, system_ctx, operator_ctx
    )
    v1_id, cycle_id = v1.id, cycle.id
    client = await api_as(operator_ctx.actor)
    url = f"/implementation-specs/{v1_id}/versions"

    resp = await client.post(
        url,
        json={"body": _impl_body(components=["billing"]), "delivery_cycle_id": str(cycle_id)},
    )
    assert resp.status_code == 422, resp.text
    assert "unknown component: billing" in resp.json()["detail"]["violations"]

    resp = await client.post(
        url, json={"body": {"summary": "no scope"}, "delivery_cycle_id": str(cycle_id)}
    )
    assert resp.status_code == 422, resp.text
    assert "file_scope: Field required" in resp.json()["detail"]["errors"]

    cycle.state = "ARCHITECTURE"
    await db_session.flush()
    resp = await client.post(url, json={"body": _impl_body(), "delivery_cycle_id": str(cycle_id)})
    assert resp.status_code == 400, resp.text
    assert resp.json()["code"] == "INVALID_STATE"

    db_session.expire_all()
    v1 = await db_session.get(ImplementationSpec, v1_id)
    assert v1 is not None and v1.status == SpecStatus.PROPOSED
    [approval] = await _pending(db_session, ApprovalType.IMPLEMENTATION_SPEC, v1_id)
    assert approval.status == ApprovalStatus.PENDING


async def test_nonconforming_edit_leaves_current_version_untouched(
    db_session, sample_project, system_ctx, operator_ctx
) -> None:
    cycle = await _cycle(db_session, sample_project, "PLANNING", system_ctx)
    v1 = await _proposed_implementation_spec(
        db_session, sample_project, cycle, system_ctx, operator_ctx
    )

    with pytest.raises(DomainError) as exc:
        await ImplementationSpecService().create_edited_version(
            db_session,
            spec_id=v1.id,
            body=ImplementationSpecBody.model_validate(_impl_body(components=["billing"])),
            note="add billing",
            delivery_cycle_id=cycle.id,
            ctx=operator_ctx,
        )

    assert exc.value.code == "ARCHITECTURE_DELTA_REQUIRED"
    await db_session.refresh(v1)
    assert v1.status == SpecStatus.PROPOSED
    [approval] = await _pending(db_session, ApprovalType.IMPLEMENTATION_SPEC, v1.id)
    assert approval.status == ApprovalStatus.PENDING


async def test_direct_edits_require_human_actor(
    db_session, sample_project, system_ctx, operator_ctx, api_as: ClientFactory
) -> None:
    arch_cycle = await _cycle(db_session, sample_project, "ARCHITECTURE", system_ctx)
    arch = await _proposed_architecture(db_session, sample_project, arch_cycle, system_ctx)
    arch_id, arch_cycle_id = arch.id, arch_cycle.id
    impl_project = Project(key=f"rl3-impl-{uuid.uuid4().hex[:6]}", name="Impl")
    db_session.add(impl_project)
    await db_session.flush()
    impl_cycle = await _cycle(db_session, impl_project, "PLANNING", system_ctx)
    impl = await _proposed_implementation_spec(
        db_session, impl_project, impl_cycle, system_ctx, operator_ctx
    )
    impl_id, impl_cycle_id = impl.id, impl_cycle.id
    client = await api_as(system_ctx.actor, scopes=["read", "operate"])

    resp = await client.post(
        f"/architectures/{arch_id}/versions",
        json={"body": _arch_body(summary="system edit"), "delivery_cycle_id": str(arch_cycle_id)},
    )
    assert resp.status_code == 403, resp.text
    assert "human" in resp.json()["message"]
    resp = await client.post(
        f"/implementation-specs/{impl_id}/versions",
        json={"body": _impl_body(summary="system edit"), "delivery_cycle_id": str(impl_cycle_id)},
    )
    assert resp.status_code == 403, resp.text
    assert "human" in resp.json()["message"]

    db_session.expire_all()
    arch = await db_session.get(Architecture, arch_id)
    impl = await db_session.get(ImplementationSpec, impl_id)
    assert arch is not None and arch.status == SpecStatus.PROPOSED
    assert impl is not None and impl.status == SpecStatus.PROPOSED
