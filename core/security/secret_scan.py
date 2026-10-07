"""Detect secret-like patterns in untrusted content."""

from __future__ import annotations

import re
from dataclasses import dataclass

from core.security.redaction import _SECRET_PATTERNS

_ENTROPY_LIKE = re.compile(r"[A-Za-z0-9+/=_-]{32,}")


@dataclass(frozen=True)
class SecretFinding:
    pattern: str
    offset: int


def scan_text(text: str) -> list[SecretFinding]:
    findings: list[SecretFinding] = []
    for pattern in _SECRET_PATTERNS:
        for match in pattern.finditer(text):
            findings.append(SecretFinding(pattern=pattern.pattern, offset=match.start()))
    return findings


def contains_secret(text: str) -> bool:
    return bool(scan_text(text))


def scan_file_bytes(data: bytes, *, max_bytes: int = 512_000) -> list[SecretFinding]:
    chunk = data[:max_bytes]
    try:
        text = chunk.decode("utf-8")
    except UnicodeDecodeError:
        text = chunk.decode("utf-8", errors="replace")
    return scan_text(text)
