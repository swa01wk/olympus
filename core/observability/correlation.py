from __future__ import annotations

import uuid
from contextvars import ContextVar, Token

import uuid6

CORRELATION_HEADER = "X-Correlation-ID"

_correlation_id: ContextVar[str | None] = ContextVar("correlation_id", default=None)


def get_correlation_id() -> str | None:
    return _correlation_id.get()


def set_correlation_id(correlation_id: str) -> Token[str | None]:
    return _correlation_id.set(correlation_id)


def clear_correlation_id(token: Token[str | None]) -> None:
    _correlation_id.reset(token)


def bind_correlation_id(raw: str | None) -> str:
    correlation_id = raw or str(uuid6.uuid7())
    set_correlation_id(correlation_id)
    return correlation_id


def new_correlation_id() -> str:
    return bind_correlation_id(None)


def is_valid_correlation_id(value: str) -> bool:
    try:
        uuid.UUID(value)
    except ValueError:
        return False
    return True
