from __future__ import annotations

from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from core.domain.delivery_cycles.models import DeliveryCycle
from core.domain.enums import DeliveryCycleType  # noqa: TC001 — used in effect guards
from core.domain.repositories.models import Repository


async def pin_base_sha(
    session: AsyncSession,
    cycle: DeliveryCycle,
    _ctx: Any,
) -> None:
    if cycle.repository_id is None:
        return
    repo = await session.get(Repository, cycle.repository_id)
    if repo is None or repo.canonical_commit is None:
        return
    cycle.base_sha = repo.canonical_commit


async def declare_ready_project(
    session: AsyncSession,
    cycle: DeliveryCycle,
    ctx: Any,
) -> None:
    if cycle.type != DeliveryCycleType.BROWNFIELD_ONBOARDING:
        return
    from core.intelligence.baselines.sets import BaselineSetService

    await BaselineSetService().declare_ready(session, cycle.id, ctx)


async def create_integration_candidate(
    session: AsyncSession,
    cycle: DeliveryCycle,
    ctx: Any,
) -> None:
    if cycle.state != "INTEGRATION":
        return
    from core.integration.service import IntegrationService

    await IntegrationService().create(session, cycle.id, ctx)


async def brownfield_code_index_stage(
    session: AsyncSession,
    cycle: DeliveryCycle,
    ctx: Any,
) -> None:
    if cycle.type != DeliveryCycleType.BROWNFIELD_ONBOARDING:
        return
    from core.intelligence.recovered_specs.orchestrator import BrownfieldOrchestrator

    await BrownfieldOrchestrator().run_code_index_stage(session, cycle.id, ctx)


async def brownfield_baseline_stage(
    session: AsyncSession,
    cycle: DeliveryCycle,
    ctx: Any,
) -> None:
    if cycle.type != DeliveryCycleType.BROWNFIELD_ONBOARDING:
        return
    from core.intelligence.baselines.orchestrator import BaselineOrchestrator

    await BaselineOrchestrator().run_baseline_stage(session, cycle.id, ctx)


async def brownfield_readiness_assess(
    session: AsyncSession,
    cycle: DeliveryCycle,
    ctx: Any,
) -> None:
    if cycle.type != DeliveryCycleType.BROWNFIELD_ONBOARDING:
        return
    from core.intelligence.baselines.readiness import ReadinessService

    await ReadinessService().assess(session, cycle.id, ctx, recompute=True)


async def brownfield_remediation_draft(
    session: AsyncSession,
    cycle: DeliveryCycle,
    ctx: Any,
) -> None:
    if cycle.type != DeliveryCycleType.BROWNFIELD_ONBOARDING:
        return
    from core.intelligence.baselines.remediation import BrownfieldRemediationService

    await BrownfieldRemediationService().draft_for_cycle(session, cycle.id, ctx)


async def brownfield_remediation_reassess(
    session: AsyncSession,
    cycle: DeliveryCycle,
    ctx: Any,
) -> None:
    if cycle.type != DeliveryCycleType.BROWNFIELD_ONBOARDING:
        return
    from core.intelligence.baselines.remediation import BrownfieldRemediationService

    await BrownfieldRemediationService().after_reintegration(session, cycle.id, ctx)


async def brownfield_spec_recovery_stage(
    session: AsyncSession,
    cycle: DeliveryCycle,
    ctx: Any,
) -> None:
    if cycle.type != DeliveryCycleType.BROWNFIELD_ONBOARDING:
        return
    from core.intelligence.recovered_specs.orchestrator import BrownfieldOrchestrator

    await BrownfieldOrchestrator().run_spec_recovery_stage(session, cycle.id, ctx)


async def feature_change_schedule_interpret(
    session: AsyncSession,
    cycle: DeliveryCycle,
    ctx: Any,
) -> None:
    if cycle.type != DeliveryCycleType.FEATURE_CHANGE:
        return
    from core.product_model.changes.orchestrator import FeatureChangeOrchestrator

    await FeatureChangeOrchestrator().schedule_change_interpret(session, cycle.id, ctx)


async def feature_change_run_impact(
    session: AsyncSession,
    cycle: DeliveryCycle,
    ctx: Any,
) -> None:
    if cycle.type != DeliveryCycleType.FEATURE_CHANGE:
        return
    from core.intelligence.impact.engine import ImpactEngine
    from core.product_model.specifications.delta import SpecDeltaService
    from core.traceability.models import RepositoryIndexPointer

    delta = await SpecDeltaService().latest_approved_for_cycle(session, cycle.id)
    if delta is None or cycle.repository_id is None:
        return
    pointer = await session.get(RepositoryIndexPointer, cycle.repository_id)
    if pointer is None or pointer.canonical_index_version_id is None:
        return
    await ImpactEngine().assess(
        session,
        cycle.id,
        spec_delta_id=delta.id,
        index_version_id=pointer.canonical_index_version_id,
        ctx=ctx,
    )


async def bug_fix_schedule_triage(
    session: AsyncSession,
    cycle: DeliveryCycle,
    ctx: Any,
) -> None:
    if cycle.type != DeliveryCycleType.BUG_FIX:
        return
    from core.product_model.defects.orchestrator import BugFixOrchestrator

    await BugFixOrchestrator().schedule_defect_triage(session, cycle.id, ctx)


async def bug_fix_schedule_reproduce(
    session: AsyncSession,
    cycle: DeliveryCycle,
    ctx: Any,
) -> None:
    if cycle.type != DeliveryCycleType.BUG_FIX:
        return
    from core.product_model.defects.orchestrator import BugFixOrchestrator

    await BugFixOrchestrator().schedule_reproduce(session, cycle.id, ctx)


async def bug_fix_schedule_expected_behavior(
    session: AsyncSession,
    cycle: DeliveryCycle,
    ctx: Any,
) -> None:
    if cycle.type != DeliveryCycleType.BUG_FIX:
        return
    from core.product_model.defects.orchestrator import BugFixOrchestrator

    await BugFixOrchestrator().schedule_expected_behavior(session, cycle.id, ctx)


async def bug_fix_schedule_root_cause(
    session: AsyncSession,
    cycle: DeliveryCycle,
    ctx: Any,
) -> None:
    if cycle.type != DeliveryCycleType.BUG_FIX:
        return
    from core.product_model.defects.orchestrator import BugFixOrchestrator

    await BugFixOrchestrator().schedule_root_cause(session, cycle.id, ctx)


async def bug_fix_run_regression_stage(
    session: AsyncSession,
    cycle: DeliveryCycle,
    ctx: Any,
) -> None:
    if cycle.type != DeliveryCycleType.BUG_FIX:
        return
    from core.product_model.defects.orchestrator import BugFixOrchestrator

    await BugFixOrchestrator().run_regression_stage(session, cycle.id, ctx)


async def feature_change_schedule_impl_spec_delta(
    session: AsyncSession,
    cycle: DeliveryCycle,
    ctx: Any,
) -> None:
    if cycle.type != DeliveryCycleType.FEATURE_CHANGE:
        return
    from core.product_model.changes.orchestrator import FeatureChangeOrchestrator

    await FeatureChangeOrchestrator().schedule_implementation_spec_delta(session, cycle.id, ctx)


EFFECT_HANDLERS: dict[str, Any] = {
    "pin_base_sha": pin_base_sha,
    "bug_fix_schedule_triage": bug_fix_schedule_triage,
    "bug_fix_schedule_reproduce": bug_fix_schedule_reproduce,
    "bug_fix_schedule_expected_behavior": bug_fix_schedule_expected_behavior,
    "bug_fix_schedule_root_cause": bug_fix_schedule_root_cause,
    "bug_fix_run_regression_stage": bug_fix_run_regression_stage,
    "feature_change_schedule_interpret": feature_change_schedule_interpret,
    "feature_change_run_impact": feature_change_run_impact,
    "feature_change_schedule_impl_spec_delta": feature_change_schedule_impl_spec_delta,
    "declare_ready_project": declare_ready_project,
    "create_integration_candidate": create_integration_candidate,
    "brownfield_code_index_stage": brownfield_code_index_stage,
    "brownfield_spec_recovery_stage": brownfield_spec_recovery_stage,
    "brownfield_baseline_stage": brownfield_baseline_stage,
    "brownfield_readiness_assess": brownfield_readiness_assess,
    "brownfield_remediation_draft": brownfield_remediation_draft,
    "brownfield_remediation_reassess": brownfield_remediation_reassess,
}


async def run_effect(
    effect_id: str,
    session: AsyncSession,
    row: Any,
    ctx: Any,
) -> None:
    handler = EFFECT_HANDLERS.get(effect_id)
    if handler is None:
        return
    await handler(session, row, ctx)
