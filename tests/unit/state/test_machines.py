from __future__ import annotations

import pytest
from core.state.machines import DELIVERY_CYCLE_MACHINES, TASK_MACHINE

pytestmark = pytest.mark.unit


@pytest.mark.parametrize("machine", DELIVERY_CYCLE_MACHINES.values())
def test_machines_validate(machine) -> None:
    machine.validate()


def test_greenfield_illegal_transition() -> None:
    from core.domain.enums import DeliveryCycleType

    machine = DELIVERY_CYCLE_MACHINES[DeliveryCycleType.GREENFIELD_BUILD]
    assert machine.edge("DISCOVERY", "start_product_modeling") is not None
    assert machine.edge("DISCOVERY", "complete") is None


def test_task_completed_can_become_stale() -> None:
    assert TASK_MACHINE.edge("COMPLETED", "mark_stale") is not None
