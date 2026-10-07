from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class DomainError(Exception):
    code: str
    message: str
    details: dict[str, object] = field(default_factory=dict)

    def __str__(self) -> str:
        return self.message


class StateConflict(DomainError):
    def __init__(self, *, current: str, expected: str | None = None) -> None:
        super().__init__(
            code="STATE_CONFLICT",
            message=f"State conflict: current={current}, expected={expected}",
            details={"current": current, "expected": expected},
        )


class IllegalTransition(DomainError):
    def __init__(self, *, aggregate: str, state: str, command: str) -> None:
        super().__init__(
            code="ILLEGAL_TRANSITION",
            message=f"Illegal transition on {aggregate}: {state} + {command}",
            details={"aggregate": aggregate, "state": state, "command": command},
        )


class GuardFailed(DomainError):
    def __init__(self, reasons: list[str]) -> None:
        super().__init__(
            code="GUARD_FAILED",
            message="Guard evaluation failed",
            details={"reasons": reasons},
        )
        self.reasons = reasons


class Unauthorized(DomainError):
    def __init__(self, message: str = "Unauthorized") -> None:
        super().__init__(code="UNAUTHORIZED", message=message)


class IdempotencyConflict(DomainError):
    def __init__(self) -> None:
        super().__init__(
            code="IDEMPOTENCY_CONFLICT",
            message="Idempotency key reused with different request body",
        )
