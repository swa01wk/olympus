"""Secret redaction for logs and telemetry."""

from __future__ import annotations

import re
from typing import Any

_SECRET_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"sk-[A-Za-z0-9]{20,}"),
    re.compile(r"ghp_[A-Za-z0-9]{20,}"),
    re.compile(r"AKIA[A-Z0-9]{16}"),
    re.compile(r"-----BEGIN [A-Z ]+ PRIVATE KEY-----"),
)

_REDACTED = "[REDACTED]"


def redact_string(value: str, *, extra_literals: frozenset[str] = frozenset()) -> str:
    out = value
    for literal in extra_literals:
        if literal and literal in out:
            out = out.replace(literal, _REDACTED)
    for pattern in _SECRET_PATTERNS:
        out = pattern.sub(_REDACTED, out)
    return out


def redact_value(value: Any, *, extra_literals: frozenset[str] = frozenset()) -> Any:
    if isinstance(value, str):
        return redact_string(value, extra_literals=extra_literals)
    if isinstance(value, dict):
        return {k: redact_value(v, extra_literals=extra_literals) for k, v in value.items()}
    if isinstance(value, list):
        return [redact_value(v, extra_literals=extra_literals) for v in value]
    return value


def structlog_redaction_processor(
    _logger: object,
    _method_name: str,
    event_dict: dict[str, Any],
) -> dict[str, Any]:
    out = redact_value(event_dict)
    return dict(out) if isinstance(out, dict) else event_dict
