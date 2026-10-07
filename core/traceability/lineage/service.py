"""Forward and reverse lineage graph composition."""

from __future__ import annotations

import uuid
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field

from sqlalchemy.ext.asyncio import AsyncSession

from core.traceability.models import CodeEntityChange, SpecCodeLink


@dataclass
class LineageNode:
    type: str
    id: str
    key: str | None = None
    version: int | None = None
    label: str | None = None
    origin: str | None = None
    confidence: float | None = None


@dataclass
class LineageEdge:
    from_id: str
    to_id: str
    relation: str
    origin: str = "GENERATED_LINEAGE"
    confidence: float = 1.0


@dataclass
class LineageGraph:
    nodes: list[LineageNode] = field(default_factory=list)
    edges: list[LineageEdge] = field(default_factory=list)


LineageHop = Callable[[AsyncSession, LineageGraph, str], Awaitable[None]]


class LineageService:
    def __init__(self) -> None:
        self._hops: list[LineageHop] = []

    def register_hop(self, hop: LineageHop) -> None:
        """Extension point for Phase 09/10 evidence and release hops."""
        self._hops.append(hop)

    async def forward(
        self,
        session: AsyncSession,
        root_type: str,
        root_id: uuid.UUID,
    ) -> LineageGraph:
        graph = LineageGraph()
        graph.nodes.append(LineageNode(type=root_type, id=str(root_id), key=str(root_id)))
        for _ in range(3):
            for hop in self._hops:
                await hop(session, graph, str(root_id))
        return graph

    async def reverse(
        self,
        session: AsyncSession,
        code_entity_id: uuid.UUID,
    ) -> LineageGraph:
        from core.intelligence.code_index.models import CodeEntity

        entity = await session.get(CodeEntity, code_entity_id)
        if entity is None:
            return LineageGraph()
        graph = LineageGraph(
            nodes=[
                LineageNode(
                    type="CODE_ENTITY",
                    id=str(entity.id),
                    key=entity.stable_key,
                    label=entity.qualified_name,
                )
            ]
        )
        from sqlalchemy import select

        links = await session.execute(
            select(SpecCodeLink).where(SpecCodeLink.code_stable_key == entity.stable_key)
        )
        for link in links.scalars():
            graph.nodes.append(
                LineageNode(
                    type=link.spec_type,
                    id=str(link.spec_id),
                    key=link.spec_lineage_key,
                    origin=link.origin.value,
                    confidence=link.confidence,
                )
            )
            graph.edges.append(
                LineageEdge(
                    from_id=str(link.spec_id),
                    to_id=str(entity.id),
                    relation=link.relation.value,
                    origin=link.origin.value,
                    confidence=link.confidence,
                )
            )
        changes = await session.execute(
            select(CodeEntityChange).where(CodeEntityChange.stable_key == entity.stable_key)
        )
        for ch in changes.scalars():
            graph.nodes.append(
                LineageNode(type="EXECUTION", id=str(ch.execution_id), key=str(ch.execution_id))
            )
            graph.edges.append(
                LineageEdge(
                    from_id=str(ch.execution_id),
                    to_id=str(entity.id),
                    relation="CHANGED",
                )
            )
        for _ in range(3):
            for hop in self._hops:
                await hop(session, graph, str(code_entity_id))
        return graph
