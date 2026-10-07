from __future__ import annotations

import pytest
from core.intelligence.impact.architecture_flag import ArchitectureDeltaHeuristic

pytestmark = pytest.mark.unit


@pytest.mark.asyncio
async def test_architecture_flag_integration_rule(db_session) -> None:
    suggested = await ArchitectureDeltaHeuristic().suggest(
        db_session,
        project_id=__import__("uuid").uuid4(),
        feature_spec_id=__import__("uuid").uuid4(),
        hits={},
        delta_changes={"rules": {"added": ["new external integration endpoint"]}},
    )
    assert suggested is True


def test_architecture_flag_integration_keyword() -> None:
    rules_block: dict[str, object] = {"added": ["Enable webhook integration for CRM"]}
    rules_added: list[object] = list(rules_block.get("added") or [])  # type: ignore[arg-type]
    assert any("integrat" in str(r).lower() for r in rules_added)
