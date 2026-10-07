from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, MagicMock

import pytest
from core.domain.projects.models import Project
from core.intelligence.baselines.enums import (
    BaselineActivation,
    BaselineCheckKind,
    BaselineSource,
    BaselineStatus,
)
from core.intelligence.baselines.models import BaselineSet, BaselineSetItem, BehavioralBaseline
from core.intelligence.impact.selection import ImpactSelection
from core.intelligence.impact.traversal import TraversalHit

pytestmark = pytest.mark.unit


@pytest.mark.asyncio
async def test_impacted_only_excludes_unrelated_baselines(monkeypatch) -> None:
    session = AsyncMock()
    project_id = uuid.uuid4()
    bset_id = uuid.uuid4()
    smoke_id = uuid.uuid4()
    impacted_id = uuid.uuid4()

    smoke = BehavioralBaseline(
        id=smoke_id,
        project_id=project_id,
        lineage_key="BL-SMOKE",
        version=1,
        status=BaselineStatus.ACTIVE,
        source=BaselineSource.CHANGE,
        given="g",
        when="w",
        then="t",
        check_kind=BaselineCheckKind.AUTHORED_TEST,
        check_ref="x",
        exercised_stable_keys=["UNRELATED:KEY"],
        established_sha="sha",
        activation=BaselineActivation.HUMAN,
    )
    impacted = BehavioralBaseline(
        id=impacted_id,
        project_id=project_id,
        lineage_key="BL-TIX",
        version=1,
        status=BaselineStatus.ACTIVE,
        source=BaselineSource.CHANGE,
        given="g",
        when="w",
        then="t",
        check_kind=BaselineCheckKind.AUTHORED_TEST,
        check_ref="x",
        exercised_stable_keys=["ROUTE:POST /tickets"],
        established_sha="sha",
    )

    project = Project(id=project_id, key="P", name="P")
    project.active_baseline_set_id = bset_id
    bset = BaselineSet(
        id=bset_id,
        project_id=project_id,
        key="B1",
        commit_sha="s",
        content_hash="h",
        delivery_cycle_id=uuid.uuid4(),
    )
    item_smoke = BaselineSetItem(baseline_set_id=bset_id, baseline_id=smoke_id)
    item_imp = BaselineSetItem(baseline_set_id=bset_id, baseline_id=impacted_id)

    async def get_side_effect(model, pk):
        if model is Project:
            return project
        if model is BaselineSet:
            return bset
        if pk == smoke_id:
            return smoke
        if pk == impacted_id:
            return impacted
        return None

    session.get = AsyncMock(side_effect=get_side_effect)

    class Result:
        def scalars(self):
            return iter([item_smoke, item_imp])

    session.execute = AsyncMock(return_value=Result())

    monkeypatch.setattr(
        "core.policy.policy_service.get_cached_policy_content",
        lambda: {"impact": {"baseline_floor": "IMPACTED_ONLY"}},
    )

    entity = MagicMock()
    entity.id = uuid.uuid4()
    hits = {
        "ROUTE:POST /tickets": TraversalHit(
            entity=entity,
            impact_kind="DIRECT",
            path=[],
            confidence=1.0,
        )
    }
    selected = await ImpactSelection(session).impacted_baselines(project_id, hits, set())
    keys = {bl.lineage_key for bl, _ in selected}
    assert "BL-TIX" in keys
    assert "BL-SMOKE" not in keys
