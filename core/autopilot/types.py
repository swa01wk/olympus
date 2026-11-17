"""What the Autopilot planner decides for one cycle on one tick."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from typing import Any, Literal

from sqlalchemy.ext.asyncio import AsyncSession

from core.commands.context import CommandContext

Status = Literal["WORKING", "NEEDS_YOU", "BLOCKED", "DONE"]
Action = Callable[[AsyncSession, CommandContext], Awaitable[None]]


@dataclass(frozen=True)
class Decision:
    """One planner outcome.

    ``status`` and ``message`` are shown to the person as-is, so ``message`` is plain
    language. ``step`` is a stable code (used for retries and by the UI). When ``action`` is
    set, the service runs it; ``status`` then describes the state *after* it ran.
    """

    status: Status
    step: str
    message: str
    action: Action | None = None
    detail: dict[str, Any] = field(default_factory=dict)


def working(step: str, message: str, **detail: Any) -> Decision:
    return Decision("WORKING", step, message, detail=detail)


def act(step: str, message: str, action: Action, **detail: Any) -> Decision:
    return Decision("WORKING", step, message, action=action, detail=detail)


def needs_you(step: str, message: str, **detail: Any) -> Decision:
    return Decision("NEEDS_YOU", step, message, detail=detail)


def blocked(step: str, message: str, **detail: Any) -> Decision:
    return Decision("BLOCKED", step, message, detail=detail)


def done(step: str, message: str, **detail: Any) -> Decision:
    return Decision("DONE", step, message, detail=detail)
