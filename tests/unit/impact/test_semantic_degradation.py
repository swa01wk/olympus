from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, MagicMock

import pytest
from core.commands.context import CommandContext
from core.domain.actors.models import Actor
from core.domain.enums import ActorKind, ActorRole
from core.intelligence.code_index.embeddings import EmbeddingService
from core.intelligence.impact.engine import ImpactEngine

pytestmark = pytest.mark.unit


@pytest.mark.asyncio
async def test_assess_records_semantic_unavailable(monkeypatch) -> None:
    session = AsyncMock()
    actor = Actor(kind=ActorKind.SYSTEM, name="t", roles=[ActorRole.SYSTEM.value])
    ctx = CommandContext(actor=actor, correlation_id="c")

    cycle = MagicMock()
    cycle.id = uuid.uuid4()
    cycle.project_id = uuid.uuid4()
    version = MagicMock()
    version.id = uuid.uuid4()
    version.commit_sha = "sha"
    version.repository_id = uuid.uuid4()

    spec_delta = MagicMock()
    spec_delta.id = uuid.uuid4()
    spec_delta.changes = {"rules": {"added": ["priority field"]}}
    spec_delta.to_spec_id = uuid.uuid4()

    async def get_side_effect(model, pk):
        from core.domain.delivery_cycles.models import DeliveryCycle
        from core.intelligence.code_index.models import CodeIndexVersion
        from core.intelligence.impact.models import SpecDelta

        if model is DeliveryCycle:
            return cycle
        if model is CodeIndexVersion:
            return version
        if model is SpecDelta:
            return spec_delta
        return None

    session.get = AsyncMock(side_effect=get_side_effect)
    captured: list[object] = []

    def _add(row: object) -> None:
        captured.append(row)

    session.add = _add
    session.flush = AsyncMock()

    class EmptyResult:
        def scalars(self):
            return iter([])

        def scalar_one_or_none(self):
            return None

    session.execute = AsyncMock(return_value=EmptyResult())

    monkeypatch.setattr(
        "core.intelligence.impact.engine.ensure_policy_version",
        AsyncMock(return_value=MagicMock(version_row=None)),
    )
    monkeypatch.setattr(
        "core.intelligence.impact.engine.next_project_key",
        AsyncMock(return_value="IA-1"),
    )
    monkeypatch.setattr(
        "core.intelligence.impact.engine.ImpactTraversal",
        lambda _s: MagicMock(expand=AsyncMock(return_value={})),
    )
    monkeypatch.setattr(
        "core.intelligence.impact.engine.ImpactSelection",
        lambda _s: MagicMock(
            impacted_tests=AsyncMock(return_value=[]),
            impacted_baselines=AsyncMock(return_value=[]),
            lexical_candidates=AsyncMock(return_value=[]),
        ),
    )
    monkeypatch.setattr(
        "core.intelligence.impact.engine.ArchitectureDeltaHeuristic",
        lambda: MagicMock(suggest=AsyncMock(return_value=False)),
    )
    monkeypatch.setattr(
        "core.intelligence.impact.engine.SpecCodeLinkService",
        lambda: MagicMock(links_for_spec=AsyncMock(return_value=[])),
    )
    monkeypatch.setattr(
        "core.intelligence.impact.engine.append_domain_event",
        AsyncMock(),
    )
    monkeypatch.setattr(
        "core.intelligence.impact.engine.get_cached_policy_content",
        lambda: {"impact": {"min_semantic_threshold": 0, "max_items": 100}},
    )

    embed = EmbeddingService()
    monkeypatch.setattr(embed, "embed_texts", AsyncMock(return_value=[]))

    engine = ImpactEngine(embeddings=embed)
    await engine.assess(
        session,
        cycle.id,
        spec_delta_id=spec_delta.id,
        index_version_id=version.id,
        ctx=ctx,
    )
    from core.intelligence.impact.models import ImpactAssessment

    ia = next(r for r in captured if isinstance(r, ImpactAssessment))
    assert ia.summary.get("semantic_note") == "SEMANTIC_UNAVAILABLE"
