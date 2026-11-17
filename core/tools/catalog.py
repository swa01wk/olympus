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
    description: str
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
    description: str,
    params: dict[str, dict[str, Any]] | None = None,
    required: tuple[str, ...] = (),
    mutating: bool = False,
    risk: RiskTier = "R0",
    requires_workspace: bool = True,
) -> ToolDefinition:
    # Models only see this schema and description, so they must name every argument the
    # handler in core/tools/handlers reads; a bare {"type": "object"} leaves them guessing.
    return ToolDefinition(
        name=name,
        resource=resource,
        action=action,
        description=description,
        params_schema={
            "type": "object",
            "properties": params or {},
            "required": list(required),
        },
        result_schema={"type": "object"},
        mutating=mutating,
        risk=risk,
        requires_workspace=requires_workspace,
        handler=name.replace(".", "_"),
    )


_STR = {"type": "string"}
_PATH = {"type": "string", "description": "Path relative to the repository root, e.g. app/main.py"}
_STR_LIST = {"type": "array", "items": {"type": "string"}}

TOOL_CATALOG: dict[str, ToolDefinition] = {
    t.name: t
    for t in [
        _tool(
            "repo.read",
            "repository",
            "read",
            description="Read one file and return its text.",
            params={"path": _PATH},
            required=("path",),
        ),
        _tool(
            "repo.search",
            "repository",
            "search",
            description="Search file contents with a ripgrep regular expression.",
            params={"pattern": {**_STR, "description": "ripgrep regular expression"}},
            required=("pattern",),
        ),
        _tool(
            "repo.list",
            "repository",
            "list",
            description="List files (recursively), optionally under a folder.",
            params={"prefix": {**_STR, "description": "Folder to list; omit for the whole repo"}},
        ),
        _tool(
            "repo.write",
            "repository",
            "write",
            description=(
                "Create or overwrite a file with the given full content. Missing parent folders "
                "are created, so this is how you add new files and folders. The path must be "
                "inside allowed_scope."
            ),
            params={"path": _PATH, "content": {**_STR, "description": "Complete file content"}},
            required=("path", "content"),
            mutating=True,
            risk="R1",
        ),
        _tool(
            "repo.delete",
            "repository",
            "delete",
            description="Delete a file inside allowed_scope.",
            params={"path": _PATH},
            required=("path",),
            mutating=True,
            risk="R2",
        ),
        _tool(
            "shell.run",
            "shell",
            "run",
            description=(
                "Run one allowed command (no shell, no network). category picks the allow-list "
                "the binary in argv[0] must belong to."
            ),
            params={
                "category": {
                    "type": "string",
                    "enum": ["python", "pytest", "ruff", "mypy", "compile"],
                },
                "argv": {
                    **_STR_LIST,
                    "description": 'Command and arguments, e.g. ["ruff", "check", "."]',
                },
            },
            required=("category", "argv"),
            risk="R1",
        ),
        _tool(
            "test.run",
            "test",
            "run",
            description="Run the test suite (or a linter) in the sandbox and report pass/fail.",
            params={
                "runner": {"type": "string", "enum": ["pytest", "ruff", "mypy"]},
                "args": {**_STR_LIST, "description": 'Extra arguments, e.g. ["-q", "tests/"]'},
            },
            risk="R1",
        ),
        _tool(
            "test.run_probe",
            "test",
            "run_probe",
            description=(
                "Start the app with uvicorn and send HTTP probes; it must serve GET /health."
            ),
            params={
                "app_module": {**_STR, "description": "uvicorn target, e.g. app.main:app"},
                "port": {"type": "integer"},
                "probes": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "method": _STR,
                            "path": _STR,
                            "expected_status": {"type": "integer"},
                            "body": {"type": "object"},
                        },
                        "required": ["path"],
                    },
                },
            },
            risk="R1",
        ),
        _tool(
            "git.diff",
            "git",
            "diff",
            description="Show uncommitted changes, optionally for one path.",
            params={"path": _PATH},
        ),
        _tool("git.status", "git", "status", description="List changed and untracked files."),
        _tool(
            "git.commit",
            "git",
            "commit",
            description=(
                "Stage every change and create the candidate commit on this execution's branch "
                "(the default). Call once, after tests pass."
            ),
            params={
                "message": _STR,
                "branch": {**_STR, "description": "Leave out to use olympus/<execution-key>"},
                "task_contract_ref": _STR,
                "principal_symbols": {
                    **_STR_LIST,
                    "description": "Main functions/classes you added or changed",
                },
            },
            required=("message",),
            mutating=True,
            risk="R2",
        ),
        _tool(
            "olympus.ask_question",
            "olympus",
            "ask_question",
            description="Ask the person a question when a requirement is ambiguous.",
            params={"questions": _STR_LIST},
            required=("questions",),
            requires_workspace=False,
        ),
        _tool(
            "olympus.request_approval",
            "olympus",
            "request_approval",
            description="Ask the person to approve something before you continue.",
            params={"reason": _STR},
            required=("reason",),
            requires_workspace=False,
        ),
        _tool(
            "olympus.submit_artifact",
            "olympus",
            "submit_artifact",
            description="Submit a named artifact.",
            params={"kind": _STR},
            mutating=True,
            risk="R1",
        ),
    ]
}


def get_tool(name: str) -> ToolDefinition:
    if name not in TOOL_CATALOG:
        raise KeyError(name)
    return TOOL_CATALOG[name]
