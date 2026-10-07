from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any

from core.tools.context import ToolExecutionContext
from core.tools.handlers import git_tools, olympus_tools, repo, shell, test_runner

Handler = Callable[[ToolExecutionContext, dict[str, Any]], Awaitable[dict[str, Any]]]

HANDLERS: dict[str, Handler] = {
    "repo_read": repo.repo_read,
    "repo_search": repo.repo_search,
    "repo_list": repo.repo_list,
    "repo_write": repo.repo_write,
    "repo_delete": repo.repo_delete,
    "shell_run": shell.shell_run,
    "test_run": test_runner.test_run,
    "test_run_probe": test_runner.test_run_probe,
    "git_diff": git_tools.git_diff,
    "git_status": git_tools.git_status,
    "git_commit": git_tools.git_commit,
    "olympus_ask_question": olympus_tools.olympus_ask_question,
    "olympus_request_approval": olympus_tools.olympus_request_approval,
    "olympus_submit_artifact": olympus_tools.olympus_submit_artifact,
}


def get_handler(name: str) -> Handler:
    if name not in HANDLERS:
        raise KeyError(name)
    return HANDLERS[name]
