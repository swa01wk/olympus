from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any, Literal

RiskTier = Literal["R0", "R1", "R2", "R3"]
HandlerFn = Callable[..., Awaitable[dict[str, Any]]]


@dataclass(frozen=True)
class ToolDefinition:
    name: str
    resource: str
    action: str
    params_schema: dict[str, Any]
    result_schema: dict[str, Any]
    mutating: bool
    risk: RiskTier
    requires_workspace: bool
    handler: str


def _tool(
    name: str,
    resource: str,
    action: str,
    *,
    mutating: bool = False,
    risk: RiskTier = "R0",
    requires_workspace: bool = True,
) -> ToolDefinition:
    return ToolDefinition(
        name=name,
        resource=resource,
        action=action,
        params_schema={"type": "object"},
        result_schema={"type": "object"},
        mutating=mutating,
        risk=risk,
        requires_workspace=requires_workspace,
        handler=name.replace(".", "_"),
    )


TOOL_CATALOG: dict[str, ToolDefinition] = {
    t.name: t
    for t in [
        _tool("repo.read", "repository", "read"),
        _tool("repo.search", "repository", "search"),
        _tool("repo.list", "repository", "list"),
        _tool("repo.write", "repository", "write", mutating=True, risk="R1"),
        _tool("repo.delete", "repository", "delete", mutating=True, risk="R2"),
        _tool("shell.run", "shell", "run", mutating=False, risk="R1"),
        _tool("test.run", "test", "run", mutating=False, risk="R1"),
        _tool("test.run_probe", "test", "run_probe", mutating=False, risk="R1"),
        _tool("git.diff", "git", "diff"),
        _tool("git.status", "git", "status"),
        _tool("git.commit", "git", "commit", mutating=True, risk="R2"),
        _tool("olympus.ask_question", "olympus", "ask_question", requires_workspace=False),
        _tool("olympus.request_approval", "olympus", "request_approval", requires_workspace=False),
        _tool("olympus.submit_artifact", "olympus", "submit_artifact", mutating=True, risk="R1"),
    ]
}


def get_tool(name: str) -> ToolDefinition:
    if name not in TOOL_CATALOG:
        raise KeyError(name)
    return TOOL_CATALOG[name]
