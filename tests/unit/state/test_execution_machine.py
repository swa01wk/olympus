from __future__ import annotations

import pytest
from core.state.machines import EXECUTION_MACHINE

pytestmark = pytest.mark.unit


def test_execution_machine_exhaustive() -> None:
    commands = {cmd for (_state, cmd) in EXECUTION_MACHINE.edges}
    for state in EXECUTION_MACHINE.states:
        for cmd in commands:
            expected = EXECUTION_MACHINE.edges.get((state, cmd))
            assert EXECUTION_MACHINE.edge(state, cmd) == expected
