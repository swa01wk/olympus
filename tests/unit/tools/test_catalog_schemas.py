"""Models see only a tool's schema and description; both must match what the handler reads."""

from __future__ import annotations

import inspect
import re

import pytest
from core.tools import handlers
from core.tools.catalog import TOOL_CATALOG
from core.tools.handlers import test_runner

# Handlers that delegate their params to a helper.
_DELEGATES = {
    "test_run": test_runner.run_pytest_in_workspace,
    "test_run_probe": test_runner.run_probe_in_workspace,
}
_PARAM = re.compile(r"params(?:\[|\.get\()\"(\w+)\"")


@pytest.mark.unit
@pytest.mark.parametrize("name", sorted(TOOL_CATALOG))
def test_schema_names_every_param_the_handler_reads(name: str) -> None:
    tool = TOOL_CATALOG[name]
    fn = _DELEGATES.get(tool.handler) or handlers.HANDLERS[tool.handler]
    read = set(_PARAM.findall(inspect.getsource(fn)))
    props = tool.params_schema["properties"]
    assert read <= set(props), f"{name} schema misses {sorted(read - set(props))}"
    assert set(tool.params_schema["required"]) <= set(props)
    assert tool.description and tool.description != f"{tool.resource}.{tool.action}"
