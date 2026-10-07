from __future__ import annotations

from core.intelligence.recovered_specs.validation import cap_confidence


def test_confidence_cap_table() -> None:
    assert cap_confidence("HIGH", {"TEST_ASSERTED"}) == "HIGH"
    assert cap_confidence("HIGH", {"ROUTE_BEHAVIOR"}) == "MEDIUM"
    assert cap_confidence("HIGH", set()) == "LOW"
    assert cap_confidence("LOW", {"TEST_EXECUTION"}) == "LOW"
