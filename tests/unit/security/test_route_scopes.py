from __future__ import annotations

import pytest
from core.security.route_scopes import required_scope
from starlette.requests import Request

pytestmark = pytest.mark.unit


def _req(method: str, path: str) -> Request:
    scope = {"type": "http", "method": method, "path": path, "headers": []}
    return Request(scope)


def test_get_requires_read() -> None:
    assert required_scope(_req("GET", "/projects")) == "read"


def test_post_requires_operate() -> None:
    assert required_scope(_req("POST", "/projects/p/cycles")) == "operate"


def test_admin_tokens() -> None:
    assert required_scope(_req("POST", "/auth/tokens")) == "admin"


def test_task_plan_accept_requires_approve() -> None:
    assert required_scope(_req("POST", "/task-plans/tp-1/commands/accept")) == "approve"
