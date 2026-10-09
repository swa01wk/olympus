"""Helpers for Feature Change journey (worker drain, approvals)."""

from __future__ import annotations

import asyncio
import uuid

from core.commands.context import CommandContext
from core.domain.delivery_cycles.models import DeliveryCycle
from core.domain.delivery_cycles.service import DeliveryCycleService
from core.domain.enums import ApprovalStatus, SpecStatus, TaskStatus, WorkType
from core.domain.tasks.models import Task
from core.execution.worker import ExecutionWorker
from core.intelligence.impact.models import ImpactAssessment, ImpactItem
from core.planning.implementation_specs.service import ImplementationSpecService
from core.planning.models import ImplementationSpec, TaskPlanRow
from core.product_model.changes.models import ChangeRequest
from core.scheduler.admission import AdmissionService
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from tests.journey.helpers import wait_for


async def drain_workers(
    session: AsyncSession,
    ctx: CommandContext,
    *,
    rounds: int = 40,
) -> None:
    worker = ExecutionWorker(worker_id=f"fc-journey-{uuid.uuid4().hex[:6]}")
    admission = AdmissionService()
    for _ in range(rounds):
        await admission.admit_batch(session, 12, ctx)
        progressed = False
        for _ in range(12):
            if await worker.run_once(session, ctx):
                progressed = True
        if not progressed:
            break


async def drain_workers_factory(
    factory: async_sessionmaker[AsyncSession],
    *,
    correlation_prefix: str = "fc-journey",
    rounds: int = 50,
) -> None:
    from tests.fixtures.planning_workflow_harness import ensure_system_actor

    for i in range(rounds):
        async with factory() as session, session.begin():
            actor = await ensure_system_actor(session)
            ctx = CommandContext(actor=actor, correlation_id=f"{correlation_prefix}-{i}")
            await drain_workers(session, ctx, rounds=3)


async def wait_for_change_interpreted(
    factory: async_sessionmaker[AsyncSession],
    cycle_id: uuid.UUID,
    *,
    timeout: float = 900.0,
) -> ChangeRequest:
    async def _ok() -> bool:
        async with factory() as session:
            cr = (
                await session.execute(
                    select(ChangeRequest).where(ChangeRequest.delivery_cycle_id == cycle_id)
                )
            ).scalar_one_or_none()
            return cr is not None and cr.status in {"INTERPRETED", "SPEC_APPROVED", "IN_DELIVERY"}

    await wait_for(_ok, timeout=timeout, interval=3.0)
    async with factory() as session:
        cr = (
            await session.execute(
                select(ChangeRequest).where(ChangeRequest.delivery_cycle_id == cycle_id)
            )
        ).scalar_one()
        return cr


async def approve_spec_delta_for_cycle(
    session: AsyncSession,
    cycle_id: uuid.UUID,
    human_ctx: CommandContext,
) -> None:
    from core.commands.handlers import handle_approval_decide
    from core.intelligence.impact.models import SpecDelta

    cr = (
        await session.execute(
            select(ChangeRequest).where(ChangeRequest.delivery_cycle_id == cycle_id)
        )
    ).scalar_one_or_none()
    assert cr is not None and cr.spec_delta_id is not None
    delta = await session.get(SpecDelta, cr.spec_delta_id)
    assert delta is not None and delta.approval_id is not None
    await handle_approval_decide(
        session,
        human_ctx,
        {
            "approval_id": str(delta.approval_id),
            "decision": ApprovalStatus.APPROVED.value,
            "note": "journey spec delta",
        },
    )


async def approve_implementation_specs_for_cycle(
    session: AsyncSession,
    cycle_id: uuid.UUID,
    human_ctx: CommandContext,
) -> None:
    cycle = await session.get(DeliveryCycle, cycle_id)
    assert cycle is not None
    specs = (
        await session.execute(
            select(ImplementationSpec).where(
                ImplementationSpec.project_id == cycle.project_id,
                ImplementationSpec.status == SpecStatus.PROPOSED,
            )
        )
    ).scalars()
    svc = ImplementationSpecService()
    for impl in specs:
        if impl.kind != "DELTA":
            continue
        from core.commands.handlers import handle_approval_decide

        approval_id = await svc.request_approval(session, impl.id, cycle_id, human_ctx)
        await handle_approval_decide(
            session,
            human_ctx,
            {
                "approval_id": str(approval_id),
                "decision": ApprovalStatus.APPROVED.value,
                "note": "journey impl delta",
            },
        )


async def accept_task_plan_if_proposed(
    session: AsyncSession,
    cycle_id: uuid.UUID,
    ctx: CommandContext,
) -> None:
    plan = (
        await session.execute(
            select(TaskPlanRow)
            .where(TaskPlanRow.delivery_cycle_id == cycle_id, TaskPlanRow.status == "PROPOSED")
            .order_by(TaskPlanRow.created_at.desc())
            .limit(1)
        )
    ).scalar_one_or_none()
    del ctx
    if plan is not None:
        from tests.fixtures.approvals import approve_task_plan

        await approve_task_plan(session, plan.id, note="journey task plan accept")


async def wait_for_task_plan_proposed(
    factory: async_sessionmaker[AsyncSession],
    cycle_id: uuid.UUID,
) -> None:
    async def _ok() -> bool:
        async with factory() as session:
            plan = (
                await session.execute(
                    select(TaskPlanRow).where(
                        TaskPlanRow.delivery_cycle_id == cycle_id,
                        TaskPlanRow.status == "PROPOSED",
                    )
                )
            ).scalar_one_or_none()
            if plan is not None:
                return True
            task = (
                await session.execute(
                    select(Task).where(
                        Task.delivery_cycle_id == cycle_id,
                        Task.title.ilike("%task plan%"),
                    )
                )
            ).scalar_one_or_none()
            return task is not None

    try:
        await wait_for(_ok, timeout=600.0, interval=3.0)
    except TimeoutError as exc:
        raise TimeoutError(
            f"no task plan for cycle {cycle_id}: {await cycle_diagnostics(factory, cycle_id)}"
        ) from exc


async def cycle_diagnostics(
    factory: async_sessionmaker[AsyncSession],
    cycle_id: uuid.UUID,
) -> str:
    from core.domain.executions.models import Execution

    async with factory() as session:
        cycle = await session.get(DeliveryCycle, cycle_id)
        assert cycle is not None
        tasks = list(
            (
                await session.execute(
                    select(Task).where(Task.delivery_cycle_id == cycle_id).order_by(Task.key)
                )
            ).scalars()
        )
        last_exec = {
            e.task_id: e
            for e in (
                await session.execute(
                    select(Execution)
                    .where(Execution.delivery_cycle_id == cycle_id)
                    .order_by(Execution.created_at)
                )
            ).scalars()
        }
        impls = list(
            (
                await session.execute(
                    select(ImplementationSpec).where(
                        ImplementationSpec.project_id == cycle.project_id
                    )
                )
            ).scalars()
        )
    task_lines = []
    for t in tasks:
        line = f"{t.key} {t.title!r} {t.status.value}"
        if t.blocked_reason:
            line += f" blocked_reason={t.blocked_reason!r}"
        e = last_exec.get(t.id)
        if e is not None:
            line += f" exec={e.agent_profile}:{e.status.value}"
            if e.failure_class:
                line += f" failure={e.failure_class}: {e.failure_detail}"
        task_lines.append(line)
    impl_lines = [f"{i.lineage_key} v{i.version} {i.kind} {i.status.value}" for i in impls]
    return f"state={cycle.state}; tasks=[{'; '.join(task_lines)}]; impl_specs={impl_lines}"


async def wait_for_task_plan_accepted(
    factory: async_sessionmaker[AsyncSession],
    cycle_id: uuid.UUID,
) -> None:
    async def _ok() -> bool:
        async with factory() as session:
            plan = (
                await session.execute(
                    select(TaskPlanRow).where(
                        TaskPlanRow.delivery_cycle_id == cycle_id,
                        TaskPlanRow.status == "ACCEPTED",
                    )
                )
            ).scalar_one_or_none()
            return plan is not None

    await wait_for(_ok, timeout=600.0, interval=3.0)


async def wait_for_cycle_state(
    factory: async_sessionmaker[AsyncSession],
    cycle_id: uuid.UUID,
    state: str,
) -> None:
    async def _ok() -> bool:
        async with factory() as session:
            cycle = await session.get(DeliveryCycle, cycle_id)
            return cycle is not None and cycle.state == state

    await wait_for(_ok, timeout=600.0, interval=2.0)


async def assert_impact_includes_ticket_surface(
    session: AsyncSession,
    cycle_id: uuid.UUID,
) -> ImpactAssessment:
    ia = (
        await session.execute(
            select(ImpactAssessment)
            .where(ImpactAssessment.delivery_cycle_id == cycle_id)
            .order_by(ImpactAssessment.created_at.desc())
            .limit(1)
        )
    ).scalar_one_or_none()
    assert ia is not None
    items = list(
        (
            await session.execute(
                select(ImpactItem).where(ImpactItem.impact_assessment_id == ia.id)
            )
        ).scalars()
    )
    refs = {i.ref for i in items}
    assert "ROUTE:POST /tickets" in refs
    assert any("Ticket" in r or "ticket" in r.lower() for r in refs)
    baseline_items = [i for i in items if i.item_type == "BASELINE"]
    assert baseline_items, "expected at least one impacted baseline"
    return ia


async def run_cycle_command(
    session: AsyncSession,
    cycle_id: uuid.UUID,
    command: str,
    expected_state: str,
    ctx: CommandContext,
) -> None:
    from core.domain.exceptions import GuardFailed

    try:
        await DeliveryCycleService().run_command(session, cycle_id, command, expected_state, ctx)
    except GuardFailed as exc:
        raise AssertionError(f"{command} guard failed: {exc.reasons}") from exc


async def wait_for_development_tasks_complete(
    factory: async_sessionmaker[AsyncSession],
    cycle_id: uuid.UUID,
    *,
    timeout: float = 1800.0,
) -> None:
    terminal = {TaskStatus.COMPLETED, TaskStatus.FAILED, TaskStatus.CANCELLED}

    async def _ok() -> bool:
        async with factory() as session:
            tasks = list(
                (
                    await session.execute(
                        select(Task).where(
                            Task.delivery_cycle_id == cycle_id,
                            Task.work_type == WorkType.CODE_CHANGE,
                        )
                    )
                ).scalars()
            )
            if not tasks:
                return False
            return all(t.status in terminal for t in tasks)

    deadline = asyncio.get_event_loop().time() + timeout
    while asyncio.get_event_loop().time() < deadline:
        if await _ok():
            return
        await asyncio.sleep(5.0)
    async with factory() as session:
        tasks = list(
            (
                await session.execute(
                    select(Task).where(
                        Task.delivery_cycle_id == cycle_id,
                        Task.work_type == WorkType.CODE_CHANGE,
                    )
                )
            ).scalars()
        )
        detail = (
            "no CODE_CHANGE tasks"
            if not tasks
            else ", ".join(f"{t.key}:{t.status.value}" for t in tasks)
        )
    raise TimeoutError(f"development tasks incomplete: {detail}")


async def wait_for_impact_assessment_complete(
    factory: async_sessionmaker[AsyncSession],
    cycle_id: uuid.UUID,
) -> None:
    from core.intelligence.impact.guards import impact_assessment_complete

    async def _ok() -> bool:
        async with factory() as session:
            cycle = await session.get(DeliveryCycle, cycle_id)
            if cycle is None:
                return False
            return (await impact_assessment_complete(session, cycle, None)).ok

    await wait_for(_ok, timeout=600.0, interval=2.0)


async def resolve_architecture_delta_for_planning(
    session: AsyncSession,
    cycle_id: uuid.UUID,
    human_ctx: CommandContext,
) -> None:
    from core.commands.handlers import handle_approval_decide
    from core.intelligence.impact.guards import architecture_delta_resolved
    from core.product_model.changes.service import ChangeRequestService

    cycle = await session.get(DeliveryCycle, cycle_id)
    assert cycle is not None
    if (await architecture_delta_resolved(session, cycle, None)).ok:
        return
    approval_id = await ChangeRequestService().decline_architecture_delta(
        session,
        cycle_id,
        "Journey: no architecture change required for ticket priority.",
        human_ctx,
    )
    await handle_approval_decide(
        session,
        human_ctx,
        {
            "approval_id": str(approval_id),
            "decision": ApprovalStatus.APPROVED.value,
            "note": "decline architecture delta",
        },
    )
