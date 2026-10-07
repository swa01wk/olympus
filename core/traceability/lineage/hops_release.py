"""Lineage hop from IntegrationCandidate to Release."""

from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.release.enums import ReleaseStatus
from core.release.models import Release
from core.traceability.lineage.service import LineageEdge, LineageGraph, LineageNode


async def hop_ic_to_release(session: AsyncSession, graph: LineageGraph, _root_id: str) -> None:
    for node in list(graph.nodes):
        if node.type != "INTEGRATION_CANDIDATE":
            continue
        releases = await session.execute(
            select(Release).where(
                Release.integration_candidate_id == uuid.UUID(node.id),
                Release.status == ReleaseStatus.RELEASED,
            )
        )
        for rel in releases.scalars():
            rel_id = str(rel.id)
            if not any(n.id == rel_id for n in graph.nodes):
                graph.nodes.append(
                    LineageNode(type="RELEASE", id=rel_id, key=rel.key, label=rel.integrated_sha)
                )
            graph.edges.append(
                LineageEdge(
                    from_id=node.id,
                    to_id=rel_id,
                    relation="RELEASED_AS",
                    origin="STRUCTURAL",
                )
            )
