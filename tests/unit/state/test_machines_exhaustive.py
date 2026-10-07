from __future__ import annotations

import pytest
from core.domain.enums import DeliveryCycleType
from core.state.machines import (
    CONTRACT_MACHINE,
    DELIVERY_CYCLE_MACHINES,
    REPOSITORY_MACHINE,
    TASK_MACHINE,
)

pytestmark = pytest.mark.unit


@pytest.mark.parametrize(
    "cycle_type",
    list(DeliveryCycleType),
)
def test_delivery_cycle_initial_state(cycle_type: DeliveryCycleType) -> None:
    machine = DELIVERY_CYCLE_MACHINES[cycle_type]
    assert machine.initial in machine.states


@pytest.mark.parametrize(
    "machine",
    list(DELIVERY_CYCLE_MACHINES.values()),
    ids=lambda m: m.name,
)
def test_delivery_cycle_edges_exhaustive(machine) -> None:
    commands = {cmd for (_state, cmd) in machine.edges}
    for state in machine.states:
        for cmd in commands:
            expected = machine.edges.get((state, cmd))
            assert machine.edge(state, cmd) == expected


def test_task_machine_exhaustive() -> None:
    commands = {cmd for (_state, cmd) in TASK_MACHINE.edges}
    for state in TASK_MACHINE.states:
        for cmd in commands:
            expected = TASK_MACHINE.edges.get((state, cmd))
            assert TASK_MACHINE.edge(state, cmd) == expected


def test_contract_and_repository_machines_exhaustive() -> None:
    for machine in (CONTRACT_MACHINE, REPOSITORY_MACHINE):
        commands = {cmd for (_state, cmd) in machine.edges}
        for state in machine.states:
            for cmd in commands:
                expected = machine.edges.get((state, cmd))
                assert machine.edge(state, cmd) == expected
