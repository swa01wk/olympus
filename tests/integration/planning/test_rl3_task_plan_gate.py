"""RL3.4 — task plans require a human TASK_PLAN approval before acceptance."""

from __future__ import annotations

import json
from collections.abc import AsyncIterator, Awaitable, Callable

import pytest
from apps.control_api.main import create_app
from core.commands.context import CommandContext
from core.commands.handlers import handle_approval_decide
from core.config.settings import OlympusSettings
from core.domain.actors.models import Actor
from core.domain.approvals.models import Approval
from core.domain.canonical_json import sha256_hex
from core.domain.delivery_cycles.models import DeliveryCycle
from core.domain.delivery_cycles.service import DeliveryCycleService
from core.domain.enums import (
    ActorKind,
    ActorRole,
    ApprovalStatus,
    ApprovalType,
    DeliveryCycleType,
    SpecStatus,
    TaskContractStatus,
    TaskOrigin,
)
from core.domain.exceptions import DomainError
from core.domain.projects.models import Project
from core.domain.task_contracts.models import TaskContract
from core.domain.tasks.models import Task
from core.execution.snapshots.planning_context import planning_prompt_fields_for_task
from core.planning.models import ImplementationSpec, TaskPlanRow
from core.planning.task_plans.service import TaskPlanService
from core.review.service import RevisionService
from core.security.tokens import create_api_token
from core.state.guards import guard_registry
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from tests.fixtures.approvals import pending_task_plan_approval
from tests.fixtures.brownfield_phase12_harness import ensure_human_approver
from tests.fixtures.planning_workflow_harness import (
    build_task_plan_for_cycle,
    seed_approved_architecture,
    seed_approved_implementation_specs_for_cycle,
    seed_supportdesk_product_and_approved_scope,
)

pytestmark = [pytest.mark.integration, pytest.mark.asyncio]

GUARD = "task_plan_accepted_contracts_issued"

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


async def _proposed_plan(
    session: AsyncSession,
    project: Project,
    system_ctx: CommandContext,
    operator_ctx: CommandContext,
) -> tuple[DeliveryCycle, TaskPlanRow]:
    cycle = await DeliveryCycleService().create(
        session, project.id, DeliveryCycleType.GREENFIELD_BUILD, "rl3 task plan gate", system_ctx
    )
    await seed_supportdesk_product_and_approved_scope(session, project.id, cycle.id, operator_ctx)
    await seed_approved_architecture(session, project.id, system_ctx)
    cycle.state = "PLANNING"
    await session.flush()
    impl_specs = await seed_approved_implementation_specs_for_cycle(session, cycle.id, system_ctx)
    assert impl_specs
    plan = await build_task_plan_for_cycle(session, cycle.id, impl_specs)
    plan_row = await TaskPlanService().persist_proposed(
        session,
        delivery_cycle_id=cycle.id,
        plan=plan,
        implementation_spec_ids=[s.id for s in impl_specs],
        execution_id=None,
        ctx=system_ctx,
    )
    return cycle, plan_row


async def _plan_tasks(session: AsyncSession, cycle_id) -> list[Task]:
    rows = await session.execute(
        select(Task).where(
            Task.delivery_cycle_id == cycle_id,
            Task.origin == TaskOrigin.IMPLEMENTATION_PLAN,
        )
    )
    return list(rows.scalars())


async def test_persist_proposed_raises_pending_approval_and_blocks_accept(
    db_session, sample_project, system_ctx, operator_ctx
) -> None:
    cycle, plan_row = await _proposed_plan(db_session, sample_project, system_ctx, operator_ctx)

    pending = await pending_task_plan_approval(db_session, plan_row)
    assert pending is not None
    assert pending.approval_type == ApprovalType.TASK_PLAN
    assert pending.subject_type == "task_plan"
    assert pending.subject_hash == sha256_hex(plan_row.body)
    assert pending.delivery_cycle_id == cycle.id

    with pytest.raises(DomainError) as exc:
        await TaskPlanService().accept(db_session, plan_row.id, system_ctx)
    assert exc.value.code == "APPROVAL_REQUIRED"
    assert plan_row.status == "PROPOSED"
    assert await _plan_tasks(db_session, cycle.id) == []

    guard = await guard_registry.evaluate(GUARD, db_session, cycle, None)
    assert not guard.ok
    assert guard.reasons == ("TASK_PLAN_NOT_ACCEPTED",)

    plan_row.status = "ACCEPTED"
    await db_session.flush()
    guard = await guard_registry.evaluate(GUARD, db_session, cycle, None)
    assert not guard.ok
    assert guard.reasons == ("TASK_PLAN_APPROVAL_PENDING",)


async def test_invalid_plan_is_rejected_at_proposal_without_an_approval(
    db_session, sample_project, system_ctx, operator_ctx
) -> None:
    cycle = await DeliveryCycleService().create(
        db_session, sample_project.id, DeliveryCycleType.GREENFIELD_BUILD, "rl3 invalid", system_ctx
    )
    await seed_supportdesk_product_and_approved_scope(
        db_session, sample_project.id, cycle.id, operator_ctx
    )
    await seed_approved_architecture(db_session, sample_project.id, system_ctx)
    cycle.state = "PLANNING"
    await db_session.flush()
    impl_specs = await seed_approved_implementation_specs_for_cycle(
        db_session, cycle.id, system_ctx
    )
    plan = await build_task_plan_for_cycle(db_session, cycle.id, impl_specs)
    first = plan.tasks[0]
    versioned = first.model_copy(
        update={"implementation_spec_ref": f"{first.implementation_spec_ref}@v2"}
    )
    plan = plan.model_copy(update={"tasks": [versioned, *plan.tasks[1:]]})

    with pytest.raises(DomainError) as exc:
        await TaskPlanService().persist_proposed(
            db_session,
            delivery_cycle_id=cycle.id,
            plan=plan,
            implementation_spec_ids=[s.id for s in impl_specs],
            execution_id=None,
            ctx=system_ctx,
        )
    assert exc.value.code == "VALIDATION_FAILED"
    assert (
        f"unknown implementation_spec_ref: {versioned.implementation_spec_ref}"
        in exc.value.details["errors"]
    )
    rows = await db_session.execute(
        select(TaskPlanRow).where(TaskPlanRow.delivery_cycle_id == cycle.id)
    )
    assert rows.scalars().first() is None
    approvals = await db_session.execute(
        select(Approval).where(
            Approval.delivery_cycle_id == cycle.id,
            Approval.approval_type == ApprovalType.TASK_PLAN,
        )
    )
    assert approvals.scalars().first() is None


async def test_task_plan_context_lists_latest_approved_version_of_each_spec(
    db_session, sample_project, system_ctx, operator_ctx
) -> None:
    cycle, _plan_row = await _proposed_plan(db_session, sample_project, system_ctx, operator_ctx)
    base = (
        (
            await db_session.execute(
                select(ImplementationSpec).where(ImplementationSpec.project_id == sample_project.id)
            )
        )
        .scalars()
        .first()
    )
    assert base is not None
    delta = ImplementationSpec(
        project_id=base.project_id,
        lineage_key=base.lineage_key,
        version=base.version + 1,
        status=SpecStatus.APPROVED,
        kind="DELTA",
        feature_spec_id=base.feature_spec_id,
        architecture_id=base.architecture_id,
        body={**base.body, "summary": "priority delta"},
        content_hash="rl3-delta",
    )
    db_session.add(delta)
    await db_session.flush()

    specs = await TaskPlanService().implementation_specs_for_cycle(db_session, cycle)
    by_lineage = {s.lineage_key: s for s in specs}
    assert len(by_lineage) == len(specs)
    assert by_lineage[base.lineage_key].id == delta.id

    fields = await planning_prompt_fields_for_task(
        db_session, Task(delivery_cycle_id=cycle.id), agent_profile="kira.task_plan"
    )
    listed = json.loads(str(fields["implementation_specs_json"]))
    assert [e["lineage_key"] for e in listed].count(base.lineage_key) == 1
    assert next(e for e in listed if e["lineage_key"] == base.lineage_key)["summary"] == (
        "priority delta"
    )
    assert all("version" not in e for e in listed)


async def test_human_approval_accepts_plan_and_issues_contracts(
    db_session, sample_project, system_ctx, operator_ctx
) -> None:
    cycle, plan_row = await _proposed_plan(db_session, sample_project, system_ctx, operator_ctx)
    pending = await pending_task_plan_approval(db_session, plan_row)
    assert pending is not None

    _human, human_ctx = await ensure_human_approver(db_session)
    await handle_approval_decide(
        db_session,
        human_ctx,
        {"approval_id": str(pending.id), "decision": ApprovalStatus.APPROVED.value, "note": ""},
    )

    await db_session.refresh(plan_row)
    await db_session.refresh(pending)
    assert pending.status == ApprovalStatus.APPROVED
    assert plan_row.status == "ACCEPTED"

    tasks = await _plan_tasks(db_session, cycle.id)
    assert len(tasks) == len(plan_row.body["tasks"])
    for task in tasks:
        contract = await db_session.get(TaskContract, task.current_contract_id)
        assert contract is not None
        assert contract.status == TaskContractStatus.ISSUED
        assert (contract.compiled_by or "").startswith("compiler:")

    guard = await guard_registry.evaluate(GUARD, db_session, cycle, None)
    assert guard.ok, guard.reasons


async def test_changes_requested_reruns_task_plan_with_note(
    db_session, sample_project, system_ctx, operator_ctx
) -> None:
    cycle, plan_row = await _proposed_plan(db_session, sample_project, system_ctx, operator_ctx)
    pending = await pending_task_plan_approval(db_session, plan_row)
    assert pending is not None
    note = "Split the ticket work into API and persistence tasks."

    _human, human_ctx = await ensure_human_approver(db_session)
    await handle_approval_decide(
        db_session,
        human_ctx,
        {
            "approval_id": str(pending.id),
            "decision": ApprovalStatus.CHANGES_REQUESTED.value,
            "note": note,
        },
    )

    await db_session.refresh(plan_row)
    assert plan_row.status == "PROPOSED"
    assert await _plan_tasks(db_session, cycle.id) == []

    task_id = await RevisionService().find_revision_task_id(db_session, pending.id, cycle.id)
    assert task_id is not None
    task = await db_session.get(Task, task_id)
    assert task is not None
    contract = await db_session.get(TaskContract, task.current_contract_id)
    assert contract is not None
    assert contract.body.get("agent_profile") == "kira.task_plan"
    snap = contract.body.get("_snapshot") or {}
    assert snap.get("revision_feedback") == note
    assert snap.get("revision_of_approval_id") == str(pending.id)
    assert '"tasks"' in (snap.get("previous_output_json") or "")


async def test_accept_endpoint_requires_human_approver(
    db_session, sample_project, system_ctx, operator_ctx, api_as: ClientFactory
) -> None:
    _cycle, plan_row = await _proposed_plan(db_session, sample_project, system_ctx, operator_ctx)
    plan_id = plan_row.id
    url = f"/task-plans/{plan_id}/commands/accept"

    operator_only = Actor(
        kind=ActorKind.HUMAN, name="rl3-operator-only", roles=[ActorRole.OPERATOR.value]
    )
    db_session.add(operator_only)
    await db_session.flush()
    approver_id = operator_ctx.actor.id
    approver = await api_as(operator_ctx.actor, scopes=["read", "operate", "approve"])
    resp = await (await api_as(operator_only, scopes=["read", "operate", "approve"])).post(url)
    assert resp.status_code == 403, resp.text
    assert "HUMAN approver" in resp.json()["message"]
    for client in (
        await api_as(system_ctx.actor, scopes=["read", "operate"]),
        await api_as(operator_ctx.actor, scopes=["read", "operate"]),
    ):
        resp = await client.post(url)
        assert resp.status_code == 403, resp.text

    db_session.expire_all()
    plan_row = await db_session.get(TaskPlanRow, plan_id)
    assert plan_row is not None
    assert plan_row.status == "PROPOSED"
    pending = await pending_task_plan_approval(db_session, plan_row)
    assert pending is not None
    pending_id = pending.id

    resp = await approver.post(url)
    assert resp.status_code == 200, resp.text
    assert resp.json() == {"id": str(plan_id), "status": "ACCEPTED"}

    db_session.expire_all()
    approval = await db_session.get(Approval, pending_id)
    assert approval is not None
    assert approval.status == ApprovalStatus.APPROVED
    assert approval.decided_by_actor_id == approver_id
