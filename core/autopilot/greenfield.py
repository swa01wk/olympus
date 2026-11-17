"""Autopilot planner for GREENFIELD_BUILD: PRD to released app.

Order of checks on every tick:
1. Terminal cycle -> DONE.
2. Anything waiting on the person (blocking question, pending approval) -> NEEDS_YOU.
3. An allowed forward transition -> run it.
4. Stage-specific work: start the agent step that produces what the next transition
   needs, report it while it runs, or stop with a readable reason when it failed.
"""

from __future__ import annotations

import uuid
from collections.abc import Iterable

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.autopilot.common import agent_step, forward, guard_reasons, human_gate
from core.autopilot.facts import AgentTask, cycle_tasks, failure_reason, open_tasks
from core.autopilot.models import AutopilotState
from core.autopilot.types import Decision, act, blocked, done, needs_you, working
from core.commands.context import CommandContext
from core.domain.approvals.models import Approval
from core.domain.delivery_cycles.models import DeliveryCycle
from core.domain.enums import ApprovalStatus, RepositoryStatus, SpecStatus, WorkType
from core.domain.repositories.models import Repository
from core.integration.models import IntegrationCandidate
from core.planning.models import Architecture, TaskPlanRow
from core.planning.orchestrator import PlanningOrchestrator
from core.product_model.models import (
    FeatureSpec,
    ProductDecomposition,
    ProductSource,
    ScopeSet,
)

FORWARD = (
    "start_product_modeling",
    "start_architecture",
    "start_planning",
    "start_development",
    "start_integration",
    "start_assurance",
    "return_to_development",
    "start_release",
    "complete",
)

FORWARD_MESSAGES = {
    "start_product_modeling": "Reading your PRD",
    "start_architecture": "Scope approved. Designing the app",
    "start_planning": "Design approved. Planning the work",
    "start_development": "Plan approved. Writing code",
    "start_integration": "All tasks done. Merging the code",
    "start_assurance": "Code merged. Testing and reviewing it",
    "return_to_development": "Fixing problems found in checks",
    "start_release": "All checks passed. Preparing the release",
    "complete": "Released",
}


async def plan_greenfield(
    session: AsyncSession,
    cycle: DeliveryCycle,
    ctx: CommandContext,
    state: AutopilotState,
) -> Decision:
    if cycle.state == "COMPLETE":
        return await _delivered_or_deliver(session, cycle)
    if cycle.state == "CANCELLED":
        return done("cancelled", "This run was cancelled")
    if cycle.state == "FAILED":
        return done("failed", f"This run failed: {cycle.terminal_reason or 'unknown reason'}")

    gate = await human_gate(session, cycle)
    if gate is not None:
        return gate

    step = await forward(session, cycle, ctx, FORWARD, FORWARD_MESSAGES)
    if step is not None:
        return step

    tasks = await cycle_tasks(session, cycle.id)
    handler = _STAGES.get(cycle.state)
    if handler is None:
        return blocked("unknown_stage", f"Autopilot does not know the stage {cycle.state}")
    return await handler(session, cycle, ctx, state, tasks)


# --- stages -----------------------------------------------------------------------------


async def _delivered_or_deliver(session: AsyncSession, cycle: DeliveryCycle) -> Decision:
    """After release, push the code into the person's folder as an `olympus/...` branch."""
    from core.autopilot.delivery import branch_for, deliver, pending_delivery
    from core.domain.projects.models import Project
    from core.release.models import Release

    delivery = await pending_delivery(session, cycle)
    if delivery is not None:

        async def _deliver(s: AsyncSession, c: CommandContext) -> None:
            await deliver(delivery)

        return act(
            "deliver",
            f"Released. Putting the code in your folder on branch {delivery.branch}",
            _deliver,
            branch=delivery.branch,
            folder=str(delivery.target),
        )
    project = await session.get(Project, cycle.project_id)
    if project is not None and project.local_path:
        release = (
            await session.execute(
                select(Release)
                .where(Release.delivery_cycle_id == cycle.id)
                .order_by(Release.created_at.desc())
                .limit(1)
            )
        ).scalar_one_or_none()
        if release is not None:
            branch = branch_for(release.key)
            return done(
                "complete",
                f"Released. The code is on branch {branch} in your folder",
                branch=branch,
                folder=project.local_path,
            )
    return done("complete", "Released")


async def _discovery(
    session: AsyncSession,
    cycle: DeliveryCycle,
    ctx: CommandContext,
    state: AutopilotState,
    tasks: list[AgentTask],
) -> Decision:
    if await _latest_source(session, cycle.id) is None:
        return needs_you("add_prd", "Add your PRD to get started")
    reasons = await guard_reasons(session, cycle, ctx, "start_product_modeling")
    return blocked("start_product_modeling", _join("Could not start reading the PRD", reasons))


async def _product_model(
    session: AsyncSession,
    cycle: DeliveryCycle,
    ctx: CommandContext,
    state: AutopilotState,
    tasks: list[AgentTask],
) -> Decision:
    source = await _latest_source(session, cycle.id)
    if source is None:
        return needs_you("add_prd", "Add your PRD to get started")

    async def _decompose(s: AsyncSession, c: CommandContext) -> None:
        from core.product_model.decomposition import DecompositionOrchestrator

        await DecompositionOrchestrator().start_decomposition(
            s, source=source, delivery_cycle_id=cycle.id, ctx=c
        )

    step = await agent_step(
        session,
        state,
        tasks,
        step="decompose",
        profile="kira.decompose",
        start=_decompose,
        starting="Breaking your PRD into features",
        busy="Breaking your PRD into features",
        failed="Breaking down the PRD failed",
    )
    if step is not None:
        return step

    specs = await _cycle_feature_specs(session, cycle.id)
    if not specs:
        return blocked(
            "decompose",
            "No features were found in your PRD. Edit it or try again.",
            retryable=True,
        )

    scope_set = await _latest_scope_set(session, cycle.id)
    decomposed_at = max(t.task.created_at for t in tasks if t.profile == "kira.decompose")
    if scope_set is None or scope_set.created_at < decomposed_at:
        candidates = [s.id for s in specs if s.status in (SpecStatus.PROPOSED, SpecStatus.DRAFT)]
        if not candidates:
            return blocked("scope", "The features from your PRD could not be put up for review")

        async def _request_scope(s: AsyncSession, c: CommandContext) -> None:
            from core.product_model.specifications.scope import ScopeService

            await ScopeService().request_scope_approval(
                s, cycle.id, candidates, cycle.project_id, c
            )

        return act("scope", "Putting the feature list up for your review", _request_scope)

    decision = await _scope_decision(session, scope_set.id)
    if decision in (ApprovalStatus.REJECTED, ApprovalStatus.CHANGES_REQUESTED):
        return blocked(
            "decompose",
            "You asked for changes to the feature list. Edit your PRD or try again "
            "to break it down again.",
            retryable=True,
        )
    reasons = await guard_reasons(session, cycle, ctx, "start_architecture")
    return blocked("start_architecture", _join("Could not start the design", reasons))


async def _architecture(
    session: AsyncSession,
    cycle: DeliveryCycle,
    ctx: CommandContext,
    state: AutopilotState,
    tasks: list[AgentTask],
) -> Decision:
    arch = await _latest_architecture(session, cycle.project_id)
    if arch is not None and arch.status == SpecStatus.APPROVED:
        repo = await _repository(session, cycle)
        if repo is not None and repo.status != RepositoryStatus.READY:
            if repo.status == RepositoryStatus.ERROR:
                return blocked("repository", "Setting up the project repository failed")
            return working("repository", "Setting up the project repository")
        reasons = await guard_reasons(session, cycle, ctx, "start_planning")
        return blocked("start_planning", _join("Could not start planning", reasons))

    # A PROPOSED design requests its own approval (caught by the human gate); a revision
    # the person asked for runs as another atlas task (reported as busy by agent_step).
    async def _propose(s: AsyncSession, c: CommandContext) -> None:
        await PlanningOrchestrator().start_architecture_proposal(s, cycle.id, c)

    step = await agent_step(
        session,
        state,
        tasks,
        step="design",
        profile="atlas.propose_architecture",
        start=_propose,
        starting="Designing the app",
        busy="Designing the app",
        failed="Designing the app failed",
    )
    if step is not None:
        return step
    return blocked(
        "design", "The design was not accepted. Try again for a new one.", retryable=True
    )


async def _planning(
    session: AsyncSession,
    cycle: DeliveryCycle,
    ctx: CommandContext,
    state: AutopilotState,
    tasks: list[AgentTask],
) -> Decision:
    spec_tasks = _latest_per_feature(t for t in tasks if t.profile == "kira.implementation_spec")
    if not spec_tasks:

        async def _generate(s: AsyncSession, c: CommandContext) -> None:
            started = await PlanningOrchestrator().start_implementation_spec_generation(
                s, cycle.id, c
            )
            if not started:
                raise ValueError("There are no approved features to plan")

        return act("specs", "Writing a detailed plan for each feature", _generate)

    failed_specs = [t for t in spec_tasks if t.failed]
    if failed_specs and state.retry_step == "specs":
        feature_spec_ids = [t.task.governing_ref_id for t in failed_specs]

        async def _regenerate(s: AsyncSession, c: CommandContext) -> None:
            for feature_spec_id in feature_spec_ids:
                await PlanningOrchestrator().start_implementation_spec_generation(
                    s, cycle.id, c, feature_spec_id=feature_spec_id
                )

        return act("specs", "Writing a detailed plan for each feature", _regenerate)

    open_specs = [t for t in spec_tasks if t.is_open]
    if open_specs:
        finished = len(spec_tasks) - len(open_specs)
        return working(
            "specs",
            f"Writing a detailed plan for each feature ({finished} of {len(spec_tasks)} done)",
            done=finished,
            total=len(spec_tasks),
        )
    failed = [t for t in spec_tasks if t.failed]
    if failed:
        reason = await failure_reason(session, failed[-1].task)
        return blocked(
            "specs",
            f"Planning a feature failed: {reason}",
            retryable=True,
            task_ids=[str(t.task.id) for t in failed],
        )

    async def _plan(s: AsyncSession, c: CommandContext) -> None:
        await PlanningOrchestrator().start_task_plan_generation(s, cycle.id, c)

    step = await agent_step(
        session,
        state,
        tasks,
        step="task_plan",
        profile="kira.task_plan",
        start=_plan,
        starting="Breaking the work into tasks",
        busy="Breaking the work into tasks",
        failed="Breaking the work into tasks failed",
    )
    if step is not None:
        return step

    plan = await _latest_task_plan(session, cycle.id)
    if plan is None or plan.status not in ("PROPOSED", "ACCEPTED"):
        return blocked(
            "task_plan",
            "The task list did not pass validation. Try again for a new one.",
            retryable=True,
        )
    reasons = await guard_reasons(session, cycle, ctx, "start_development")
    return blocked("start_development", _join("Could not start coding", reasons))


async def _development(
    session: AsyncSession,
    cycle: DeliveryCycle,
    ctx: CommandContext,
    state: AutopilotState,
    tasks: list[AgentTask],
) -> Decision:
    code = [t for t in tasks if t.task.work_type == WorkType.CODE_CHANGE]
    failed = [t for t in code if t.failed]
    if failed:
        reason = await failure_reason(session, failed[0].task)
        title = failed[0].task.title
        return blocked(
            "development",
            f"The task “{title}” failed: {reason}",
            retryable=True,
            task_ids=[str(t.task.id) for t in failed],
        )
    if open_tasks(code):
        finished = sum(1 for t in code if not t.is_open)
        return working(
            "development",
            f"Writing code ({finished} of {len(code)} tasks done)",
            done=finished,
            total=len(code),
        )
    reasons = await guard_reasons(session, cycle, ctx, "start_integration")
    return blocked("start_integration", _join("Could not start merging the code", reasons))


async def _integration(
    session: AsyncSession,
    cycle: DeliveryCycle,
    ctx: CommandContext,
    state: AutopilotState,
    tasks: list[AgentTask],
) -> Decision:
    from core.integration.enums import ICStatus

    ic = await _latest_ic(session, cycle.id)
    if ic is None or ic.status in (ICStatus.CREATED, ICStatus.INTEGRATING, ICStatus.VALIDATING):
        return working("integration", "Merging the code and running checks")
    if ic.status == ICStatus.READY:
        if open_tasks(tasks):
            return working("integration", "Indexing the merged code")
        reasons = await guard_reasons(session, cycle, ctx, "start_assurance")
        return blocked("start_assurance", _join("Could not start testing", reasons))
    return await _integration_failed(session, cycle, state, ic)


async def _integration_failed(
    session: AsyncSession,
    cycle: DeliveryCycle,
    state: AutopilotState,
    ic: IntegrationCandidate,
) -> Decision:
    """The merge or its checks failed and no fix task is running (one would have moved the
    cycle back to development). Failed checks get fix tasks automatically a few times; after
    that, or for failures with no automatic fix, Try again sends them to be fixed."""
    from core.assurance.models import Finding
    from core.integration.enums import FindingStatus
    from core.integration.remediation import MAX_AUTO_CHECK_FIXES

    problems = list(
        (
            await session.execute(
                select(Finding)
                .where(
                    Finding.integration_candidate_id == ic.id,
                    Finding.blocking.is_(True),
                    Finding.status == FindingStatus.OPEN,
                )
                .order_by(Finding.created_at)
            )
        ).scalars()
    )
    if state.retry_step == "integration":
        ic_id = ic.id
        if problems:
            finding_ids = [f.id for f in problems]

            async def _fix(s: AsyncSession, c: CommandContext) -> None:
                from core.assurance.remediation import RemediationService
                from core.integration.remediation import create_check_failure_remediation

                candidate = await s.get(IntegrationCandidate, ic_id)
                for finding_id in finding_ids:
                    finding = await s.get(Finding, finding_id)
                    if finding is None or candidate is None:
                        continue
                    if finding.category == "INTEGRATION_CHECK_FAILED":
                        await create_check_failure_remediation(s, candidate, finding, c, auto=False)
                    else:
                        await RemediationService().remediate_finding(s, finding_id, c)

            return act("integration", "Fixing the problems found while merging", _fix)

        # Nothing to fix (e.g. git itself failed): merge again on a fresh candidate.
        async def _remerge(s: AsyncSession, c: CommandContext) -> None:
            from core.integration.service import IntegrationService

            await IntegrationService().create(s, cycle.id, c)

        return act("integration", "Merging the code again", _remerge)

    checks_failed = any(p.category == "INTEGRATION_CHECK_FAILED" for p in problems)
    if checks_failed:
        message = (
            f"The merged code still fails its checks after {MAX_AUTO_CHECK_FIXES} automatic "
            "fixes. Open Inspect to see what fails, or try again for another round of fixes."
        )
    elif problems:
        message = (
            "Merging the code failed. Open Inspect for details, or try again to have it fixed."
        )
    else:
        message = "Merging the code failed. Try again to merge it again."
    return blocked(
        "integration",
        message,
        retryable=True,
        integration_candidate_id=str(ic.id),
    )


async def _assurance(
    session: AsyncSession,
    cycle: DeliveryCycle,
    ctx: CommandContext,
    state: AutopilotState,
    tasks: list[AgentTask],
) -> Decision:
    from core.assurance.enums import GateStatus
    from core.assurance.models import Gate

    if open_tasks(tasks):
        return working("assurance", "Testing and reviewing the code")
    ic = await _latest_ic(session, cycle.id)
    if ic is None:
        return blocked("assurance", "There is no merged code to test")
    from core.integration.enums import ICStatus

    if ic.status != ICStatus.READY:
        # Only a re-check creates a candidate in this step; if its merge failed, say so.
        return blocked(
            "assurance",
            "Merging the code again for the re-check failed. Open Inspect for details.",
            retryable=True,
            integration_candidate_id=str(ic.id),
        )
    gates = list(
        (
            await session.execute(select(Gate).where(Gate.integration_candidate_id == ic.id))
        ).scalars()
    )
    if any(g.status == GateStatus.PENDING for g in gates):
        ic_id = ic.id

        async def _finalize(s: AsyncSession, c: CommandContext) -> None:
            from core.assurance.coverage import CoverageService
            from core.assurance.gates import GateFinalizerService

            await CoverageService().recompute_for_ic(s, ic_id, c)
            for gate in gates:
                if gate.status == GateStatus.PENDING:
                    await GateFinalizerService().finalize(s, gate.id, c)

        return act("assurance", "Collecting the test and review results", _finalize)
    failing = sorted({str(g.gate_type) for g in gates if g.status == GateStatus.FAIL})
    if failing:
        from core.assurance.models import Finding
        from core.integration.enums import FindingStatus

        problems = list(
            (
                await session.execute(
                    select(Finding)
                    .where(
                        Finding.integration_candidate_id == ic.id,
                        Finding.blocking.is_(True),
                        Finding.status == FindingStatus.OPEN,
                    )
                    .order_by(Finding.created_at)
                )
            ).scalars()
        )
        if state.retry_step == "assurance":
            if problems:
                # Re-running the checks cannot change their verdict on the same code: fix the
                # blocking findings instead. Each fix is a coding task; once they exist the cycle
                # returns to development, and the fixes are merged and checked again.
                finding_ids = [f.id for f in problems]

                async def _fix(s: AsyncSession, c: CommandContext) -> None:
                    from core.assurance.remediation import RemediationService

                    for finding_id in finding_ids:
                        await RemediationService().remediate_finding(s, finding_id, c)

                return act("assurance", f"Fixing {len(problems)} problems the checks found", _fix)

            # No finding to fix (e.g. a check failed to run): finalized gates are immutable, so
            # re-check on a fresh candidate built from the same commits.
            async def _recheck(s: AsyncSession, c: CommandContext) -> None:
                from core.integration.service import IntegrationService

                await IntegrationService().create(s, cycle.id, c)

            return act("assurance", "Running the checks again", _recheck)
        if problems:
            return blocked(
                "assurance",
                f"The checks found {len(problems)} problems in the code. Try again to have "
                "them fixed, or open Inspect to waive some first.",
                retryable=True,
                integration_candidate_id=str(ic.id),
            )
        return blocked(
            "assurance",
            f"Some checks failed ({', '.join(failing).lower()}). Open Inspect for details, "
            "or try again to re-run the checks.",
            retryable=True,
            integration_candidate_id=str(ic.id),
        )
    reasons = await guard_reasons(session, cycle, ctx, "start_release")
    return blocked("start_release", _join("Could not prepare the release", reasons))


async def _release(
    session: AsyncSession,
    cycle: DeliveryCycle,
    ctx: CommandContext,
    state: AutopilotState,
    tasks: list[AgentTask],
) -> Decision:
    from core.release.enums import ReleaseStatus
    from core.release.models import Release
    from core.release.service import ReleaseService

    release = (
        await session.execute(
            select(Release)
            .where(Release.delivery_cycle_id == cycle.id)
            .order_by(Release.created_at.desc())
            .limit(1)
        )
    ).scalar_one_or_none()
    if release is None or (
        release.status in (ReleaseStatus.NOT_ELIGIBLE, ReleaseStatus.FAILED)
        and state.retry_step == "release"
    ):

        async def _create(s: AsyncSession, c: CommandContext) -> None:
            await ReleaseService().create_release(s, cycle.id, c)

        return act("release", "Preparing the release", _create)
    if release.status == ReleaseStatus.APPROVED:
        release_id = release.id

        async def _execute(s: AsyncSession, c: CommandContext) -> None:
            await ReleaseService().execute_release(s, release_id, c)

        return act("release", "Releasing", _execute)
    if release.status in (ReleaseStatus.EXECUTING, ReleaseStatus.DRAFT, ReleaseStatus.RELEASED):
        return working("release", "Releasing")
    if release.status == ReleaseStatus.NOT_ELIGIBLE:
        return blocked(
            "release", "The release is not ready yet. Open Inspect for details.", retryable=True
        )
    if release.status == ReleaseStatus.FAILED:
        return blocked("release", "The release failed. Try again.", retryable=True)
    return blocked("release", f"The release is {release.status.value.lower()}")


_STAGES = {
    "DISCOVERY": _discovery,
    "PRODUCT_MODEL": _product_model,
    "ARCHITECTURE": _architecture,
    "PLANNING": _planning,
    "DEVELOPMENT": _development,
    "INTEGRATION": _integration,
    "ASSURANCE": _assurance,
    "RELEASE": _release,
}


# --- queries ----------------------------------------------------------------------------


def _latest_per_feature(tasks: Iterable[AgentTask]) -> list[AgentTask]:
    """Latest implementation-spec task per feature spec (retries replace earlier runs)."""
    latest: dict[uuid.UUID | None, AgentTask] = {}
    for t in tasks:
        latest[t.task.governing_ref_id] = t
    return list(latest.values())


def _join(prefix: str, reasons: list[str]) -> str:
    return f"{prefix}: {'; '.join(reasons)}" if reasons else prefix


async def _latest_source(session: AsyncSession, cycle_id: uuid.UUID) -> ProductSource | None:
    return (
        await session.execute(
            select(ProductSource)
            .where(ProductSource.delivery_cycle_id == cycle_id)
            .order_by(ProductSource.created_at.desc())
            .limit(1)
        )
    ).scalar_one_or_none()


async def _cycle_feature_specs(session: AsyncSession, cycle_id: uuid.UUID) -> list[FeatureSpec]:
    decompositions = select(ProductDecomposition.id).where(
        ProductDecomposition.delivery_cycle_id == cycle_id
    )
    rows = await session.execute(
        select(FeatureSpec).where(FeatureSpec.decomposition_id.in_(decompositions))
    )
    return list(rows.scalars())


async def _latest_scope_set(session: AsyncSession, cycle_id: uuid.UUID) -> ScopeSet | None:
    return (
        await session.execute(
            select(ScopeSet)
            .where(ScopeSet.delivery_cycle_id == cycle_id)
            .order_by(ScopeSet.created_at.desc())
            .limit(1)
        )
    ).scalar_one_or_none()


async def _scope_decision(session: AsyncSession, scope_set_id: uuid.UUID) -> ApprovalStatus | None:
    approval = (
        await session.execute(
            select(Approval)
            .where(Approval.subject_type == "scope_set", Approval.subject_id == scope_set_id)
            .order_by(Approval.created_at.desc())
            .limit(1)
        )
    ).scalar_one_or_none()
    return approval.status if approval is not None else None


async def _latest_architecture(session: AsyncSession, project_id: uuid.UUID) -> Architecture | None:
    return (
        await session.execute(
            select(Architecture)
            .where(
                Architecture.project_id == project_id,
                Architecture.status.in_([SpecStatus.PROPOSED, SpecStatus.APPROVED]),
            )
            .order_by(Architecture.created_at.desc())
            .limit(1)
        )
    ).scalar_one_or_none()


async def _repository(session: AsyncSession, cycle: DeliveryCycle) -> Repository | None:
    if cycle.repository_id is None:
        return None
    return await session.get(Repository, cycle.repository_id)


async def _latest_task_plan(session: AsyncSession, cycle_id: uuid.UUID) -> TaskPlanRow | None:
    return (
        await session.execute(
            select(TaskPlanRow)
            .where(TaskPlanRow.delivery_cycle_id == cycle_id)
            .order_by(TaskPlanRow.created_at.desc())
            .limit(1)
        )
    ).scalar_one_or_none()


async def _latest_ic(session: AsyncSession, cycle_id: uuid.UUID) -> IntegrationCandidate | None:
    return (
        await session.execute(
            select(IntegrationCandidate)
            .where(IntegrationCandidate.delivery_cycle_id == cycle_id)
            .order_by(IntegrationCandidate.created_at.desc())
            .limit(1)
        )
    ).scalar_one_or_none()
