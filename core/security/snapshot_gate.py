"""Reject snapshots and continuation packages that contain secret patterns."""

from __future__ import annotations

import json
from typing import Any

from core.domain.exceptions import DomainError
from core.security.secret_scan import contains_secret, scan_text


def _walk_strings(obj: Any, out: list[str]) -> None:
    if isinstance(obj, str):
        out.append(obj)
    elif isinstance(obj, dict):
        for v in obj.values():
            _walk_strings(v, out)
    elif isinstance(obj, list):
        for v in obj:
            _walk_strings(v, out)


def assert_no_secrets_in_payload(payload: dict[str, Any], *, context: str) -> None:
    strings: list[str] = []
    _walk_strings(payload, strings)
    blob = "\n".join(strings)
    if contains_secret(blob):
        findings = scan_text(blob)
        raise DomainError(
            code="SECRET_IN_CONTEXT",
            message=f"Secret pattern detected in {context} ({findings[0].pattern})",
        )


def assert_no_secrets_in_json_text(text: str, *, context: str) -> None:
    if contains_secret(text):
        raise DomainError(
            code="SECRET_IN_CONTEXT",
            message=f"Secret pattern detected in {context}",
        )


def scan_worktree_file_text(text: str, path: str) -> None:
    if contains_secret(text):
        raise DomainError(
            code="SECRET_IN_WORKTREE",
            message=f"Secret pattern in worktree file {path}",
        )


def dump_for_scan(payload: dict[str, Any]) -> str:
    return json.dumps(payload, default=str)
