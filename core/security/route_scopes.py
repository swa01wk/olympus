"""Map HTTP routes to API token scopes."""

from __future__ import annotations

import re
from typing import Literal

from starlette.requests import Request

ApiScopeNeed = Literal["read", "operate", "approve", "admin"]

_ADMIN_PREFIXES = ("/auth/tokens", "/ops/")
_APPROVE_PATTERNS = (
    re.compile(r"^/approvals/[^/]+/(approve|reject|decide|decision)", re.I),
    re.compile(r"/request-approval$"),
    re.compile(r"^/task-plans/[^/]+/commands/accept$", re.I),
)


def required_scope(request: Request) -> ApiScopeNeed:
    path = request.url.path.rstrip("/") or "/"
    if any(path.startswith(p) for p in _ADMIN_PREFIXES):
        return "admin"
    for pat in _APPROVE_PATTERNS:
        if pat.search(path):
            return "approve"
    if request.method in {"GET", "HEAD", "OPTIONS"}:
        return "read"
    return "operate"
