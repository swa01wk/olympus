"""Release eligibility condition names and fail-closed registry behavior."""

from __future__ import annotations

import pytest
from core.domain.enums import DeliveryCycleType
from core.release.eligibility import (
    _default_required_conditions,
    get_eligibility_registry,
    register_core_eligibility_conditions,
)

pytestmark = pytest.mark.unit


def test_greenfield_and_feature_change_share_core_conditions() -> None:
    register_core_eligibility_conditions()
    gf = _default_required_conditions(DeliveryCycleType.GREENFIELD_BUILD)
    fc = _default_required_conditions(DeliveryCycleType.FEATURE_CHANGE)
    assert gf == fc
    assert len(gf) == 8


def test_unregistered_condition_name_would_fail_closed() -> None:
    register_core_eligibility_conditions()
    reg = get_eligibility_registry()
    assert reg.get("manifest_valid") is not None
    assert reg.get("nonexistent_condition_xyz") is None
