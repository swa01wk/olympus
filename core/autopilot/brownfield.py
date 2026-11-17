"""Autopilot planner for BROWNFIELD_ONBOARDING: learn an existing codebase until it is
ready for changes.

Most onboarding work is started by the stage transitions themselves (their effects schedule
indexing, Scout recovery, characterization and readiness checks). Autopilot fires the next
allowed transition, reports agents while they run, and pauses for the person's review of
what was learned.
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.autopilot.common import forward, guard_reasons, human_gate
from core.autopilot.facts import AgentTask, cycle_tasks, failure_reason, open_tasks
from core.autopilot.models import AutopilotState
from core.autopilot.review import pending_items
from core.autopilot.types import Decision, blocked, done, needs_you, working
from core.commands.context import CommandContext
from core.domain.delivery_cycles.models import DeliveryCycle
from core.domain.enums import RepositoryStatus
from core.domain.repositories.models import Repository

FORWARD = (
    "start_code_index",
    "start_spec_recovery",
    "retry_spec_recovery",
    "start_baseline",
    "start_readiness",
    "declare_ready",
    "start_remediation",
    "reassess_readiness",
)

FORWARD_MESSAGES = {
    "start_code_index": "Reading your code",
    "start_spec_recovery": "Working out what your app does",
    "retry_spec_recovery": "Trying again to work out what your app does",
    "start_baseline": "Running your tests to record how the app behaves today",
    "start_readiness": "Checking whether the project is ready for changes",
    "declare_ready": "Ready for changes",
    "start_remediation": "Fixing gaps found in the readiness check",
    "reassess_readiness": "Checking readiness again",
}

_BUSY = {
    "RECON": "Copying your repository",
    "CODE_INDEX": "Reading your code",
    "RECOVERED_SPEC": "Working out what your app does",
    "BASELINE": "Running your tests to record how the app behaves today",
    "READINESS": "Checking whether the project is ready for changes",
    "REMEDIATION": "Fixing gaps found in the readiness check",
}


async def plan_brownfield(
    session: AsyncSession,
    cycle: DeliveryCycle,
    ctx: CommandContext,
    state: AutopilotState,
) -> Decision:
    if cycle.state == "READY":
        return done("ready", "Ready for changes. You can add features or fix bugs now.")
    if cycle.state == "CANCELLED":
        return done("cancelled", "This run was cancelled")
    if cycle.state == "FAILED":
        return done("failed", f"This run failed: {cycle.terminal_reason or 'unknown reason'}")

    gate = await human_gate(session, cycle)
    if gate is not None:
        return gate

    review = await pending_items(session, cycle.id)
    tasks = await cycle_tasks(session, cycle.id)
    if review and not open_tasks(tasks):
        noun = "thing" if len(review) == 1 else "things"
        return needs_you(
            "review_learned",
            f"Confirm what Olympus learned about your app ({len(review)} {noun})",
            count=len(review),
        )

    step = await forward(session, cycle, ctx, FORWARD, FORWARD_MESSAGES)
    if step is not None:
        return step

    failed = [t for t in tasks if t.failed]
    if open_tasks(tasks):
        return working(cycle.state.lower(), _BUSY.get(cycle.state, "Working"))
    if cycle.state == "RECON":
        return await _recon(session, cycle, ctx)
    if failed and not _later_success(tasks, failed[-1]):
        reason = await failure_reason(session, failed[-1].task)
        return blocked(
            cycle.state.lower(),
            f"{_BUSY.get(cycle.state, 'A step')} failed: {reason}",
            task_ids=[str(failed[-1].task.id)],
            retryable=True,
            retry_tasks=True,
        )
    if cycle.state == "READINESS":
        return await _not_ready(session, cycle)
    command = {
        "CODE_INDEX": "start_spec_recovery",
        "RECOVERED_SPEC": "start_baseline",
        "BASELINE": "start_readiness",
        "REMEDIATION": "reassess_readiness",
    }.get(cycle.state)
    if command is None:
        return blocked("unknown_stage", f"Autopilot does not know the stage {cycle.state}")
    reasons = await guard_reasons(session, cycle, ctx, command)
    message = FORWARD_MESSAGES.get(command, "Moving on")
    return blocked(command, f"Could not start: {message.lower()}" + _suffix(reasons))


async def _recon(session: AsyncSession, cycle: DeliveryCycle, ctx: CommandContext) -> Decision:
    repo = await session.get(Repository, cycle.repository_id) if cycle.repository_id else None
    if repo is None:
        return blocked("repository", "This run has no repository attached")
    if repo.status == RepositoryStatus.ERROR:
        return blocked(
            "repository",
            f"Copying your repository failed: {repo.status_reason or 'unknown error'}",
        )
    if repo.status != RepositoryStatus.READY or not repo.canonical_commit:
        return working("repository", "Copying your repository")
    reasons = await guard_reasons(session, cycle, ctx, "start_code_index")
    return blocked("start_code_index", "Could not start reading your code" + _suffix(reasons))


async def _not_ready(session: AsyncSession, cycle: DeliveryCycle) -> Decision:
    from core.intelligence.baselines.models import ReadinessAssessment

    assessment = (
        await session.execute(
            select(ReadinessAssessment)
            .where(ReadinessAssessment.delivery_cycle_id == cycle.id)
            .order_by(ReadinessAssessment.created_at.desc())
            .limit(1)
        )
    ).scalar_one_or_none()
    if assessment is None:
        return working("readiness", _BUSY["READINESS"])
    reasons = [_reason_text(r) for r in (assessment.reasons or [])][:4]
    return blocked(
        "readiness",
        "Not ready for changes yet" + _suffix(reasons),
        reasons=reasons,
    )


def _later_success(tasks: list[AgentTask], failed: AgentTask) -> bool:
    """A failed run that was retried successfully no longer blocks."""
    later = [t for t in tasks if t.task.created_at > failed.task.created_at]
    return any(t.profile == failed.profile and not t.failed for t in later)


def _reason_text(raw: object) -> str:
    if isinstance(raw, dict):
        for key in ("message", "reason", "code"):
            if raw.get(key):
                return str(raw[key])
    return str(raw)


def _suffix(reasons: list[str]) -> str:
    return f": {'; '.join(reasons)}" if reasons else ""
