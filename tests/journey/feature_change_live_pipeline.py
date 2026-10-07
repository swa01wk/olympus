"""Shared live Feature Change worker pipeline (Phase 14 / 16 journeys)."""

from __future__ import annotations

import os
import uuid
from unittest.mock import patch

from core.commands.context import CommandContext
from core.domain.delivery_cycles.models import DeliveryCycle
from core.domain.enums import SpecStatus, TaskStatus, WorkType
from core.domain.projects.models import Project
from core.domain.repositories.models import Repository
from core.domain.tasks.models import Task
from core.integration.models import IntegrationCandidate
from core.product_model.models import FeatureSpec
from core.release.models import Release
from core.runtime.model_router import build_providers
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from tests.fixtures.brownfield_phase12_harness import ensure_human_approver
from tests.fixtures.planning_workflow_harness import ensure_system_actor
from tests.fixtures.release_harness import (
    finish_assurance_and_release_for_cycle,
    seed_approved_scope_for_feature_spec,
)
from tests.journey.chained.worker_drain import drain_until_code_change_tasks_terminal
from tests.journey.feature_change_helpers import (
    accept_task_plan_if_proposed,
    approve_implementation_specs_for_cycle,
    approve_spec_delta_for_cycle,
    drain_workers_factory,
    resolve_architecture_delta_for_planning,
    run_cycle_command,
    wait_for_change_interpreted,
    wait_for_impact_assessment_complete,
    wait_for_task_plan_accepted,
    wait_for_task_plan_proposed,
)
from tests.journey.greenfield_dev import complete_feature_change_implementation_tasks


async def run_feature_change_live_journey(
    factory: async_sessionmaker[AsyncSession],
    *,
    project_id: uuid.UUID,
    fc_cycle_id: uuid.UUID,
    correlation_prefix: str = "fc",
) -> tuple[IntegrationCandidate, Release]:
    async with factory() as session, session.begin():
        actor = await ensure_system_actor(session)
        ctx = CommandContext(actor=actor, correlation_id=f"{correlation_prefix}-intake")
        await run_cycle_command(session, fc_cycle_id, "start_spec_delta", "INTAKE", ctx)

    with patch("core.runtime.model_router.build_providers", side_effect=build_providers):
        await drain_workers_factory(factory, correlation_prefix=f"{correlation_prefix}-interpret")
        await wait_for_change_interpreted(factory, fc_cycle_id)

        async with factory() as session, session.begin():
            _human, human_ctx = await ensure_human_approver(session)
            await approve_spec_delta_for_cycle(session, fc_cycle_id, human_ctx)

        await wait_for_impact_assessment_complete(factory, fc_cycle_id)

        async with factory() as session, session.begin():
            _human, human_ctx = await ensure_human_approver(session)
            await resolve_architecture_delta_for_planning(session, fc_cycle_id, human_ctx)

        async with factory() as session, session.begin():
            actor = await ensure_system_actor(session)
            ctx = CommandContext(actor=actor, correlation_id=f"{correlation_prefix}-planning")
            cycle = await session.get(DeliveryCycle, fc_cycle_id)
            assert cycle is not None
            latest_spec = (
                await session.execute(
                    select(FeatureSpec)
                    .where(
                        FeatureSpec.project_id == cycle.project_id,
                        FeatureSpec.status.in_((SpecStatus.APPROVED, SpecStatus.PROPOSED)),
                    )
                    .order_by(FeatureSpec.version.desc())
                    .limit(1)
                )
            ).scalar_one()
            _human, human_ctx = await ensure_human_approver(session)
            await seed_approved_scope_for_feature_spec(session, cycle, latest_spec.id, human_ctx)
            await run_cycle_command(session, fc_cycle_id, "start_planning", "IMPACT_ANALYSIS", ctx)

        await drain_workers_factory(
            factory, correlation_prefix=f"{correlation_prefix}-impl-plan", rounds=80
        )
        async with factory() as session, session.begin():
            _human, human_ctx = await ensure_human_approver(session)
            await approve_implementation_specs_for_cycle(session, fc_cycle_id, human_ctx)
            from core.product_model.changes.completion import FeatureChangeCompletionService

            actor = await ensure_system_actor(session)
            await FeatureChangeCompletionService().maybe_start_task_plan_after_impl_approval(
                session,
                fc_cycle_id,
                CommandContext(actor=actor, correlation_id=f"{correlation_prefix}-task-plan-kick"),
            )

        await drain_workers_factory(
            factory, correlation_prefix=f"{correlation_prefix}-task-plan", rounds=40
        )
        await wait_for_task_plan_proposed(factory, fc_cycle_id)
        await drain_workers_factory(factory, correlation_prefix=f"{correlation_prefix}-task-plan")
        async with factory() as session, session.begin():
            actor = await ensure_system_actor(session)
            ctx = CommandContext(actor=actor, correlation_id=f"{correlation_prefix}-accept-plan")
            await accept_task_plan_if_proposed(session, fc_cycle_id, ctx)
        await wait_for_task_plan_accepted(factory, fc_cycle_id)

        async with factory() as session, session.begin():
            actor = await ensure_system_actor(session)
            ctx = CommandContext(actor=actor, correlation_id=f"{correlation_prefix}-dev")
            await run_cycle_command(session, fc_cycle_id, "start_development", "PLANNING", ctx)

        terminal = {TaskStatus.COMPLETED, TaskStatus.FAILED, TaskStatus.CANCELLED}
        await drain_until_code_change_tasks_terminal(
            factory,
            fc_cycle_id,
            correlation_prefix=f"{correlation_prefix}-forge",
            max_outer_rounds=60,
            rounds_per_drain=15,
            inject_chaos=os.environ.get("MVP_CHAOS") == "1",
        )

        async with factory() as session:
            dev_tasks = list(
                (
                    await session.execute(
                        select(Task).where(
                            Task.delivery_cycle_id == fc_cycle_id,
                            Task.work_type == WorkType.CODE_CHANGE,
                        )
                    )
                ).scalars()
            )
        assert dev_tasks, "expected CODE_CHANGE tasks after start_development"
        if any(t.status not in terminal for t in dev_tasks):
            async with factory() as session, session.begin():
                actor = await ensure_system_actor(session)
                ctx = CommandContext(
                    actor=actor, correlation_id=f"{correlation_prefix}-dev-fallback"
                )
                cycle_row = await session.get(DeliveryCycle, fc_cycle_id)
                repo_row = (
                    await session.get(Repository, cycle_row.repository_id)
                    if cycle_row and cycle_row.repository_id
                    else None
                )
                project_row = await session.get(Project, project_id)
                assert (
                    cycle_row is not None
                    and repo_row is not None
                    and project_row is not None
                    and cycle_row.base_sha
                )
                await complete_feature_change_implementation_tasks(
                    session,
                    ctx,
                    project=project_row,
                    repository=repo_row,
                    cycle=cycle_row,
                    base_sha=cycle_row.base_sha,
                )

        async with factory() as session, session.begin():
            from core.domain.actors.models import Actor
            from core.domain.enums import ActorKind, ActorRole

            actor = await ensure_system_actor(session)
            system_ctx = CommandContext(
                actor=actor, correlation_id=f"{correlation_prefix}-assurance"
            )
            human = Actor(
                kind=ActorKind.HUMAN,
                name=f"{correlation_prefix}-journey-approver",
                roles=[ActorRole.APPROVER.value, ActorRole.OPERATOR.value],
            )
            session.add(human)
            await session.flush()
            human_ctx = CommandContext(
                actor=human, correlation_id=f"{correlation_prefix}-assurance-human"
            )
            ic, release = await finish_assurance_and_release_for_cycle(
                session,
                system_ctx,
                human_ctx,
                fc_cycle_id,
                live_assurance=False,
            )
        await drain_workers_factory(
            factory, correlation_prefix=f"{correlation_prefix}-assurance", rounds=80
        )
    return ic, release
