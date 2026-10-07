from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class RuntimeError(Exception):
    code: str
    message: str
    details: dict[str, object] = field(default_factory=dict)

    def __str__(self) -> str:
        return self.message


class ConfigError(RuntimeError):
    def __init__(self, message: str) -> None:
        super().__init__(code="CONFIG_ERROR", message=message)


class ProviderTransientError(RuntimeError):
    def __init__(self, message: str, *, retry_after: float | None = None) -> None:
        super().__init__(
            code="PROVIDER_TRANSIENT",
            message=message,
            details={"retry_after": retry_after},
        )
        self.retry_after = retry_after


class ProviderRateLimited(ProviderTransientError):
    def __init__(self, message: str, *, retry_after: float | None = None) -> None:
        super().__init__(message, retry_after=retry_after)
        self.code = "PROVIDER_RATE_LIMITED"


class ProviderAuthError(RuntimeError):
    def __init__(self, message: str) -> None:
        super().__init__(code="PROVIDER_AUTH", message=message)


class SchemaValidationFailed(RuntimeError):
    def __init__(self, message: str, *, errors: list[dict[str, object]]) -> None:
        super().__init__(
            code="SCHEMA_VALIDATION_FAILED",
            message=message,
            details={"errors": errors},
        )
        self.errors = errors


class BudgetExceeded(RuntimeError):
    def __init__(self, message: str = "LLM budget exceeded") -> None:
        super().__init__(code="BUDGET_EXCEEDED", message=message)


class RuntimeCancelled(RuntimeError):
    def __init__(self, message: str = "Runtime run cancelled") -> None:
        super().__init__(code="RUNTIME_CANCELLED", message=message)
