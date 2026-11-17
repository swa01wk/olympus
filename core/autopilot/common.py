"""Planner building blocks shared by every journey."""

from __future__ import annotations

from collections.abc import Sequence

from sqlalchemy.ext.asyncio import AsyncSession

from core.autopilot.facts import (
    AgentTask,
    failure_reason,
    latest_for,
    open_questions,
    pending_approvals,
)
from core.autopilot.models import AutopilotState
from core.autopilot.types import Action, Decision, act, blocked, needs_you, working
from core.commands.context import CommandContext
from core.domain.delivery_cycles.models import DeliveryCycle
from core.domain.delivery_cycles.service import DeliveryCycleService
from core.domain.enums import ApprovalType

APPROVAL_PROMPTS: dict[ApprovalType, str] = {
    ApprovalType.SCOPE: "Review the features Olympus found in your PRD",
    ApprovalType.ARCHITECTURE: "Review the proposed design",
    ApprovalType.ARCHITECTURE_DELTA: "Review the proposed design change",
    ApprovalType.IMPLEMENTATION_SPEC: "Review the detailed plan for each feature",
    ApprovalType.SPEC_DELTA: "Review what this change adds or changes",
    ApprovalType.TASK_PLAN: "Review the task list before coding starts",
    ApprovalType.EXPECTED_BEHAVIOR: "Confirm how the app should behave",
    ApprovalType.UNREPRODUCED_REPAIR: "Decide whether to fix a bug that could not be reproduced",
    ApprovalType.PROMOTION: "Review the recovered behavior of your code",
    ApprovalType.FINDING_WAIVER: "Decide whether to accept a known issue",
    ApprovalType.ACTION: "An agent wants to run an action that needs your OK",
    ApprovalType.RELEASE: "Everything passed. Approve the release",
}


async def human_gate(session: AsyncSession, cycle: DeliveryCycle) -> Decision | None:
    """Pause when something is waiting on the person: a blocking question or an approval."""
    questions = [q for q in await open_questions(session, cycle) if q.blocking]
    if questions:
        noun = "question" if len(questions) == 1 else "questions"
        return needs_you(
            "answer_questions",
            f"Olympus has {len(questions)} {noun} for you",
            clarification_ids=[str(q.id) for q in questions],
        )
    approvals = await pending_approvals(session, cycle)
    if approvals:
        first = approvals[0]
        return needs_you(
            "review",
            APPROVAL_PROMPTS.get(first.approval_type, "Something needs your review"),
            approval_ids=[str(a.id) for a in approvals],
            approval_type=first.approval_type.value,
        )
    return None


async def forward(
    session: AsyncSession,
    cycle: DeliveryCycle,
    ctx: CommandContext,
    commands: Sequence[str],
    messages: dict[str, str],
) -> Decision | None:
    """Run the first allowed forward transition from ``commands`` (in priority order)."""
    svc = DeliveryCycleService()
    allowed = {
        str(c["command"]): c
        for c in await svc.allowed_commands(session, cycle, ctx)
        if c["allowed"]
    }
    for command in commands:
        if command not in allowed:
            continue
        expected = cycle.state

        async def _run(
            s: AsyncSession, c: CommandContext, cmd: str = command, state: str = expected
        ) -> None:
            await svc.run_command(s, cycle.id, cmd, state, c)

        return act(command, messages.get(command, "Moving to the next stage"), _run)
    return None


async def guard_reasons(
    session: AsyncSession,
    cycle: DeliveryCycle,
    ctx: CommandContext,
    command: str,
) -> list[str]:
    for c in await DeliveryCycleService().allowed_commands(session, cycle, ctx):
        if c["command"] == command:
            preview = c.get("guard_preview")
            return [str(r) for r in preview] if isinstance(preview, list) else []
    return []


async def agent_step(
    session: AsyncSession,
    state: AutopilotState,
    tasks: list[AgentTask],
    *,
    step: str,
    profile: str,
    start: Action,
    starting: str,
    busy: str,
    failed: str,
) -> Decision | None:
    """Start an agent step once, report it while it runs, stop if it failed.

    Returns ``None`` once the latest run of ``profile`` completed, so the caller moves on.
    A retry the person asked for (``state.retry_step == step``) starts the step again.
    """
    latest = latest_for(tasks, profile)
    if latest is None:
        return act(step, starting, start)
    if latest.is_open:
        return working(step, busy)
    if state.retry_step == step:
        return act(step, starting, start)
    if latest.failed:
        reason = await failure_reason(session, latest.task)
        return blocked(step, f"{failed}: {reason}", retryable=True, task_ids=[str(latest.task.id)])
    return None
