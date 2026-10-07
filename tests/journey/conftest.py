"""Journey test harness (Phase 10 Greenfield)."""

from __future__ import annotations

import pytest
from tests.workflow.product_model.conftest import control_app, operator_token  # noqa: F401

pytestmark = [pytest.mark.journey]
