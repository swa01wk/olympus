"""Olympus trace/log context binding (TECH §24.2)."""

from __future__ import annotations

from contextvars import ContextVar
from typing import Any

from core.observability.correlation import get_correlation_id, set_correlation_id

_bound: ContextVar[dict[str, str] | None] = ContextVar("olympus_obs_bound", default=None)


def _current_bound() -> dict[str, str]:
    val = _bound.get()
    return {} if val is None else val


def bind(**ids: str | None) -> None:
    current = dict(_current_bound())
    for key, value in ids.items():
        if value is not None:
            current[key] = value
    _bound.set(current)
    cid = ids.get("correlation_id") or ids.get("olympus.correlation_id")
    if cid:
        set_correlation_id(cid)


def clear() -> None:
    _bound.set({})


def get_bound() -> dict[str, str]:
    return dict(_current_bound())


def merged_context() -> dict[str, Any]:
    out: dict[str, Any] = dict(_current_bound())
    cid = get_correlation_id()
    if cid:
        out.setdefault("correlation_id", cid)
        out.setdefault("olympus.correlation_id", cid)
    return out


def structlog_context_processor(
    _logger: object,
    _method_name: str,
    event_dict: dict[str, Any],
) -> dict[str, Any]:
    for key, value in merged_context().items():
        event_dict.setdefault(key, value)
    return event_dict
