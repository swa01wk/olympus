from __future__ import annotations

import uuid
from pathlib import Path

from core.commands.context import CommandContext
from core.domain.actors.models import Actor
from core.domain.canonical_json import sha256_hex
from core.domain.delivery_cycles.models import DeliveryCycle
from core.domain.delivery_cycles.service import DeliveryCycleService
from core.domain.enums import SpecStatus
from core.planning.architecture.service import ArchitectureService
from core.planning.implementation_specs.service import ImplementationSpecService
from core.planning.models import Architecture, ImplementationSpec
from core.planning.schemas import TaskDraft, TaskPlan
from core.product_model.models import AcceptanceCriterion, FeatureSpec, ScopeSet, ScopeSetItem
from core.repositories.materialization import RepositoryMaterializationService
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker
from tests.fixtures.planning_harness import (
    create_ticket_implementation_spec,
    supportdesk_architecture_proposal,
)
from tests.fixtures.product_model_harness import supportdesk_decomposition


async def seed_supportdesk_product_and_approved_scope(
    session: AsyncSession,
    project_id: uuid.UUID,
    cycle_id: uuid.UUID,
    ctx: CommandContext,
) -> None:
    from core.domain.approvals.service import ApprovalService
    from core.domain.enums import ApprovalStatus
    from core.product_model.models import ProductSource
    from core.product_model.service import ProductModelService
    from core.product_model.sources.service import ProductSourceService
    from core.product_model.specifications.scope import ScopeService

    ingest = await ProductSourceService().ingest(
        session,
        project_id=project_id,
        lineage_key="plan-seed",
        source_type="PRD",
        title="Plan seed",
        mime_type="text/markdown",
        content_hash=f"plan-seed-{cycle_id}",
        raw_storage_ref=f"inbound/plan-seed/{cycle_id}",
        text="supportdesk seed",
        ctx=ctx,
        delivery_cycle_id=cycle_id,
    )
    source = await session.get(ProductSource, ingest["product_source_id"])
    assert source is not None
    await ProductModelService().persist_proposal(
        session,
        project_id=project_id,
        delivery_cycle_id=cycle_id,
        product_source_version_id=source.id,
        execution_id=None,
        proposal=supportdesk_decomposition(),
        ctx=ctx,
    )
    specs = await session.execute(select(FeatureSpec).where(FeatureSpec.project_id == project_id))
    spec_ids = [s.id for s in specs.scalars()]
    _scope_set, approval_id = await ScopeService().request_scope_approval(
        session,
        cycle_id,
        spec_ids,
        project_id,
        ctx,
    )
    await ApprovalService().decide(
        session,
        approval_id,
        ApprovalStatus.APPROVED,
        "planning-test",
        ctx,
    )


async def seed_approved_architecture(
    session: AsyncSession,
    project_id: uuid.UUID,
    ctx: CommandContext,
) -> Architecture:
    proposal = supportdesk_architecture_proposal()
    arch = await ArchitectureService().persist_proposal(
        session,
        project_id=project_id,
        proposal=proposal,
        execution_id=None,
        ctx=ctx,
    )
    arch.status = SpecStatus.APPROVED
    await session.flush()
    return arch


async def provision_greenfield_repository(
    session: AsyncSession,
    cycle: DeliveryCycle,
    ctx: CommandContext,
) -> None:
    assert cycle.repository_id is not None
    await RepositoryMaterializationService().provision_managed(session, cycle.repository_id, ctx)


async def approve_implementation_spec(
    session: AsyncSession,
    impl_id: uuid.UUID,
    ctx: CommandContext,
) -> None:
    row = await session.get(ImplementationSpec, impl_id)
    assert row is not None
    row.status = SpecStatus.APPROVED
    await session.flush()


async def seed_approved_implementation_specs_for_cycle(
    session: AsyncSession,
    cycle_id: uuid.UUID,
    ctx: CommandContext,
) -> list[ImplementationSpec]:
    scope = await session.execute(
        select(ScopeSet)
        .where(ScopeSet.delivery_cycle_id == cycle_id)
        .order_by(ScopeSet.created_at.desc())
        .limit(1)
    )
    scope_set = scope.scalar_one_or_none()
    if scope_set is None:
        return []
    items = await session.execute(
        select(ScopeSetItem).where(ScopeSetItem.scope_set_id == scope_set.id)
    )
    out: list[ImplementationSpec] = []
    draft = create_ticket_implementation_spec()
    for item in items.scalars():
        try:
            row = await ImplementationSpecService().persist_draft(
                session,
                feature_spec_id=item.feature_spec_id,
                draft=draft,
                execution_id=None,
                ctx=ctx,
            )
        except Exception:
            body = draft.body.model_copy(update={"summary": f"impl-{item.feature_spec_id}"})
            from agents.kira.schemas import ImplementationSpecDraft

            row = await ImplementationSpecService().persist_draft(
                session,
                feature_spec_id=item.feature_spec_id,
                draft=ImplementationSpecDraft(body=body),
                execution_id=None,
                ctx=ctx,
            )
        await approve_implementation_spec(session, row.id, ctx)
        out.append(row)
    return out


async def build_task_plan_for_cycle(
    session: AsyncSession,
    cycle_id: uuid.UUID,
    impl_specs: list[ImplementationSpec],
) -> TaskPlan:
    scope = await session.execute(
        select(ScopeSet)
        .where(ScopeSet.delivery_cycle_id == cycle_id)
        .order_by(ScopeSet.created_at.desc())
        .limit(1)
    )
    scope_set = scope.scalar_one_or_none()
    assert scope_set is not None
    items = await session.execute(
        select(ScopeSetItem).where(ScopeSetItem.scope_set_id == scope_set.id)
    )
    spec_ids = {i.feature_spec_id for i in items.scalars()}
    impl_by_feature = {s.feature_spec_id: s for s in impl_specs}
    impl_svc = ImplementationSpecService()
    tasks: list[TaskDraft] = []
    for idx, fs_id in enumerate(sorted(spec_ids, key=str), start=1):
        impl = impl_by_feature.get(fs_id)
        if impl is None:
            continue
        spec_body = impl_svc.parse_body(impl)
        allowed_scope = (
            list(spec_body.file_scope) if spec_body.file_scope else ["app/**", "tests/**"]
        )
        acs = await session.execute(
            select(AcceptanceCriterion).where(
                AcceptanceCriterion.feature_spec_id == fs_id,
                AcceptanceCriterion.mandatory.is_(True),
            )
        )
        ac_keys = [a.lineage_key for a in acs.scalars()]
        if not ac_keys:
            continue
        tasks.append(
            TaskDraft(
                ref=f"T-{idx}",
                title=f"Implement {impl.lineage_key}",
                objective=f"Deliver {impl.lineage_key}",
                implementation_spec_ref=impl.lineage_key,
                ac_refs=ac_keys,
                allowed_scope=allowed_scope,
                required_outputs=["candidate_commit", "changed_files", "test_results"],
                verification_requirements=["Run pytest for scoped changes"],
                estimated_size="M",
            )
        )
    from core.planning.schemas import DependencyDraft

    dependencies = [
        DependencyDraft(
            task_ref=f"T-{i}",
            depends_on_ref=f"T-{i - 1}",
            reason="sequential implementation",
        )
        for i in range(2, len(tasks) + 1)
    ]
    return TaskPlan(tasks=tasks, dependencies=dependencies)


async def ensure_system_actor(session: AsyncSession) -> Actor:
    from core.domain.enums import ActorKind, ActorRole

    actor = (
        await session.execute(select(Actor).where(Actor.kind == ActorKind.SYSTEM).limit(1))
    ).scalar_one_or_none()
    if actor is None:
        actor = Actor(kind=ActorKind.SYSTEM, name="planning-worker", roles=[ActorRole.SYSTEM.value])
        session.add(actor)
        await session.flush()
    return actor


async def create_greenfield_planning_cycle(
    client: AsyncClient,
    *,
    idempotency_suffix: str,
) -> tuple[str, str]:
    project = await client.post(
        "/projects",
        json={"key": f"plan-{idempotency_suffix}", "name": "Live Planning"},
    )
    assert project.status_code == 201, project.text
    project_id = project.json()["id"]
    cycle = await client.post(
        f"/projects/{project_id}/delivery-cycles",
        json={"type": "GREENFIELD_BUILD", "objective": "planning"},
    )
    assert cycle.status_code == 201, cycle.text
    return project_id, cycle.json()["id"]


async def seed_supportdesk_product_model_for_cycle(
    async_engine: AsyncEngine,
    project_id: str,
    cycle_id: str,
) -> None:
    from core.domain.actors.models import Actor
    from core.domain.enums import ActorKind

    factory = async_sessionmaker(bind=async_engine, class_=AsyncSession, expire_on_commit=False)
    async with factory() as session, session.begin():
        from core.domain.enums import ActorRole

        operator = (
            await session.execute(select(Actor).where(Actor.kind == ActorKind.HUMAN).limit(1))
        ).scalar_one_or_none()
        if operator is None:
            operator = Actor(
                kind=ActorKind.HUMAN,
                name="live-planning-approver",
                roles=[ActorRole.OPERATOR.value, ActorRole.APPROVER.value],
            )
            session.add(operator)
            await session.flush()
        ctx = CommandContext(actor=operator, correlation_id="live-pm-seed")
        await seed_supportdesk_product_and_approved_scope(
            session, uuid.UUID(project_id), uuid.UUID(cycle_id), ctx
        )


async def supportdesk_upload_and_decompose_task(
    client: AsyncClient,
    *,
    idempotency_suffix: str,
) -> tuple[str, str, str, str]:
    """Upload PRD and enqueue Kira decompose (run worker before scope approval)."""
    project = await client.post(
        "/projects",
        json={"key": f"plan-{idempotency_suffix}", "name": "Plan"},
    )
    assert project.status_code == 201, project.text
    project_id = project.json()["id"]
    cycle = await client.post(
        f"/projects/{project_id}/delivery-cycles",
        json={"type": "GREENFIELD_BUILD", "objective": "planning"},
    )
    assert cycle.status_code == 201, cycle.text
    cycle_id = cycle.json()["id"]
    repo_id = cycle.json()["repository_id"]
    prd = Path(__file__).resolve().parents[1] / "fixtures" / "supportdesk" / "PRD.md"
    up = await client.post(
        f"/projects/{project_id}/sources",
        params={"delivery_cycle_id": cycle_id},
        files={"file": ("PRD.md", prd.read_bytes(), "text/markdown")},
        headers={"Idempotency-Key": f"plan-{idempotency_suffix}"},
    )
    assert up.status_code == 200, up.text
    source_id = up.json()["result"]["product_source_id"]
    decompose = await client.post(
        f"/sources/{source_id}/decompose",
        json={"delivery_cycle_id": cycle_id},
    )
    assert decompose.status_code == 200, decompose.text
    task_id = decompose.json()["task_id"]
    return project_id, cycle_id, str(repo_id), task_id


async def resolve_blocking_clarifications_for_cycle(
    session: AsyncSession,
    cycle_id: uuid.UUID,
) -> None:
    """Close blocking clarifications so start_architecture guard passes (live decompose setup)."""
    from core.domain.enums import ClarificationStatus
    from core.domain.executions.models import Clarification

    rows = await session.execute(
        select(Clarification).where(
            Clarification.delivery_cycle_id == cycle_id,
            Clarification.status == ClarificationStatus.OPEN,
            Clarification.blocking.is_(True),
        )
    )
    for row in rows.scalars():
        row.status = ClarificationStatus.ANSWERED
        row.answer = row.answer or (
            "Default: closed tickets cannot be modified; updates return 409 (SupportDesk PRD)."
        )
    await session.flush()


async def run_supportdesk_decompose_worker(
    async_engine: AsyncEngine,
    decompose_task_id: str,
    *,
    correlation_id: str,
    worker_id: str,
    deterministic: bool = False,
) -> None:
    """Run Kira decompose worker; use deterministic=True for stable product model setup."""
    from unittest.mock import patch

    from core.domain.actors.models import Actor
    from core.domain.enums import ActorKind, ActorRole, ExecutionStatus
    from core.domain.executions.models import Execution
    from core.execution.worker import ExecutionWorker
    from core.runtime.model_router import build_providers as real_build_providers
    from core.runtime.providers.fake_provider import FakeProvider, FakeScriptStep
    from core.scheduler.admission import AdmissionService

    factory = async_sessionmaker(bind=async_engine, class_=AsyncSession, expire_on_commit=False)
    decompose_fake: FakeProvider | None = None
    if deterministic:
        decompose_fake = FakeProvider()
        decompose_fake.set_script([FakeScriptStep(structured=supportdesk_decompose_script())])

    def _providers(*, fake=None):
        if fake is not None:
            return {"anthropic": fake, "openai": fake}
        return real_build_providers()

    async with factory() as session, session.begin():
        actor = (
            await session.execute(select(Actor).where(Actor.kind == ActorKind.SYSTEM).limit(1))
        ).scalar_one_or_none()
        if actor is None:
            actor = Actor(kind=ActorKind.SYSTEM, name=worker_id, roles=[ActorRole.SYSTEM.value])
            session.add(actor)
            await session.flush()
        ctx = CommandContext(actor=actor, correlation_id=correlation_id)
        execution = await AdmissionService().admit_task(session, uuid.UUID(decompose_task_id), ctx)
        execution_id = execution.id

    patch_fn = (
        (
            lambda: patch(
                "core.runtime.model_router.build_providers",
                side_effect=lambda **kw: _providers(fake=decompose_fake),
            )
        )
        if deterministic
        else (lambda: patch("core.runtime.model_router.build_providers", side_effect=_providers))
    )
    with patch_fn():
        async with factory() as session, session.begin():
            actor = (
                await session.execute(select(Actor).where(Actor.kind == ActorKind.SYSTEM).limit(1))
            ).scalar_one()
            ctx = CommandContext(actor=actor, correlation_id=f"{correlation_id}-run")
            worker = ExecutionWorker(worker_id=worker_id)
            for _ in range(30):
                await worker.run_once(session, ctx)
                ex = await session.get(Execution, execution_id)
                assert ex is not None
                if ex.status in {ExecutionStatus.COMPLETED, ExecutionStatus.FAILED}:
                    break
            assert ex.status == ExecutionStatus.COMPLETED, ex.failure_detail


async def approve_scope_and_enter_architecture(
    client: AsyncClient,
    project_id: str,
    cycle_id: str,
    *,
    async_engine: AsyncEngine | None = None,
) -> None:
    advance = await client.post(
        f"/delivery-cycles/{cycle_id}/commands/start_product_modeling",
        json={"expected_state": "DISCOVERY"},
    )
    if advance.status_code not in (200, 409):
        assert advance.status_code == 200, advance.text

    features = await client.get(f"/projects/{project_id}/features")
    all_specs: list[str] = []
    for feat in features.json():
        spec_list = await client.get(f"/features/{feat['id']}/specs")
        for s in spec_list.json():
            if s.get("status") in ("PROPOSED", "DRAFT"):
                all_specs.append(s["id"])
    assert all_specs, "decompose worker must run before scope approval"
    scope_req = await client.post(
        f"/delivery-cycles/{cycle_id}/scope/approval-request",
        json={"feature_spec_ids": all_specs},
    )
    assert scope_req.status_code == 200, scope_req.text
    approval_id = scope_req.json()["approval_id"]
    await client.post(
        f"/approvals/{approval_id}/decision",
        json={"decision": "APPROVED", "note": "planning-test"},
    )
    if async_engine is not None:
        factory = async_sessionmaker(bind=async_engine, class_=AsyncSession, expire_on_commit=False)
        async with factory() as session, session.begin():
            await resolve_blocking_clarifications_for_cycle(session, uuid.UUID(cycle_id))
    arch_cmd = await client.post(
        f"/delivery-cycles/{cycle_id}/commands/start_architecture",
        json={"expected_state": "PRODUCT_MODEL"},
    )
    assert arch_cmd.status_code == 200, arch_cmd.text


async def supportdesk_cycle_at_architecture(
    client: AsyncClient,
    *,
    idempotency_suffix: str,
) -> tuple[str, str, str, str]:
    """Legacy helper: upload + decompose only.

    Run worker then approve_scope_and_enter_architecture separately.
    """
    return await supportdesk_upload_and_decompose_task(
        client, idempotency_suffix=idempotency_suffix
    )


def supportdesk_decompose_script():
    return supportdesk_decomposition().model_dump(mode="json")


async def transition_cycle(
    session: AsyncSession,
    cycle_id: uuid.UUID,
    command: str,
    expected_state: str,
    ctx: CommandContext,
) -> None:
    await DeliveryCycleService().run_command(session, cycle_id, command, expected_state, ctx)


def architecture_content_hash() -> str:
    return sha256_hex(supportdesk_architecture_proposal().body.model_dump(mode="json"))
