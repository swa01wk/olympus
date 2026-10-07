from __future__ import annotations

import pytest
from core.commands.context import CommandContext
from core.domain.actors.models import Actor
from core.domain.approvals.models import Approval
from core.domain.enums import (
    ActorKind,
    ApprovalStatus,
    ExecutionStatus,
    TaskStatus,
)
from core.domain.exceptions import DomainError
from core.domain.tasks.service import TaskService
from core.execution.service import ExecutionService
from core.execution.snapshots.base_commit import BaseCommitResolver
from core.scheduler.admission import AdmissionService
from core.scheduler.context_loader import load_eligibility_context, load_task_view
from core.scheduler.eligibility import evaluate
from core.scheduler.refs import build_default_registry
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from tests.fixtures.execution_harness import seed_ready_task

pytestmark = [pytest.mark.workflow, pytest.mark.integration]


@pytest.mark.asyncio
async def test_blocked_dependency_not_admitted(async_engine) -> None:
    factory = async_sessionmaker(bind=async_engine, class_=AsyncSession, expire_on_commit=False)
    async with factory() as session, session.begin():
        bundle = await seed_ready_task(session, key_prefix="dep-block")
        blocker = await seed_ready_task(session, key_prefix="dep-parent", actor=bundle.actor)
        await TaskService().add_dependency(session, bundle.task.id, blocker.task.id)
        bundle.task.status = TaskStatus.READY
        ctx = CommandContext(actor=bundle.actor, correlation_id="dep")
        with pytest.raises(DomainError) as exc:
            await AdmissionService().admit_task(session, bundle.task.id, ctx)
        assert exc.value.code == "NOT_ELIGIBLE"


@pytest.mark.asyncio
async def test_unblocks_after_dependency_completes(async_engine) -> None:
    factory = async_sessionmaker(bind=async_engine, class_=AsyncSession, expire_on_commit=False)
    async with factory() as session, session.begin():
        bundle = await seed_ready_task(session, key_prefix="dep-child")
        parent = await seed_ready_task(session, key_prefix="dep-done", actor=bundle.actor)
        await TaskService().add_dependency(session, bundle.task.id, parent.task.id)
        parent.task.status = TaskStatus.COMPLETED
        bundle.task.status = TaskStatus.READY
        ctx = CommandContext(actor=bundle.actor, correlation_id="dep2")
        ex = await AdmissionService().admit_task(session, bundle.task.id, ctx)
        assert ex.task_id == bundle.task.id


@pytest.mark.asyncio
async def test_approval_required(async_engine) -> None:
    factory = async_sessionmaker(bind=async_engine, class_=AsyncSession, expire_on_commit=False)
    async with factory() as session, session.begin():
        bundle = await seed_ready_task(
            session, key_prefix="appr", with_pending_required_approval=True
        )
        elig_ctx = await load_eligibility_context(
            session,
            bundle.task,
            ref_registry=build_default_registry(),
            base_resolver=BaseCommitResolver(),
        )
        view = await load_task_view(session, bundle.task)
        assert not evaluate(view, elig_ctx).eligible

        approval = (
            await session.execute(select(Approval).where(Approval.subject_id == bundle.task.id))
        ).scalar_one()
        approval.status = ApprovalStatus.APPROVED
        elig_ctx = await load_eligibility_context(
            session,
            bundle.task,
            ref_registry=build_default_registry(),
            base_resolver=BaseCommitResolver(),
        )
        assert evaluate(view, elig_ctx).eligible


@pytest.mark.asyncio
async def test_cancel_execution(async_engine) -> None:
    factory = async_sessionmaker(bind=async_engine, class_=AsyncSession, expire_on_commit=False)
    async with factory() as session, session.begin():
        human = Actor(kind=ActorKind.HUMAN, name="cancel-human", roles=["OPERATOR"])
        system = Actor(kind=ActorKind.SYSTEM, name="cancel-sys", roles=["SYSTEM"])
        session.add_all([human, system])
        await session.flush()
        bundle = await seed_ready_task(session, key_prefix="cancel", actor=system)
        sys_ctx = CommandContext(actor=system, correlation_id="cancel-adm")
        ex = await AdmissionService().admit_task(session, bundle.task.id, sys_ctx)
        human_ctx = CommandContext(actor=human, correlation_id="cancel")
        await ExecutionService().transition(session, ex.id, "cancel", human_ctx)
        await session.refresh(ex)
        assert ex.status == ExecutionStatus.CANCELLED
