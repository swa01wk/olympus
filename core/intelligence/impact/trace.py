"""Trace correlation from reproduction test runs."""

from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.intelligence.code_index.models import CodeEntity
from core.product_model.defects.models import TraceCorrelation


async def persist_trace_correlation(
    session: AsyncSession,
    reproduction_id: uuid.UUID,
    index_version_id: uuid.UUID,
    cases: list[dict[str, Any]],
    failure_detail: dict[str, Any] | None,
    entry_route_key: str | None,
) -> TraceCorrelation:
    traceback_keys: list[str] = []
    if failure_detail:
        text = str(failure_detail.get("failure_text", ""))
        for line in text.splitlines():
            if "ticket_service" in line or "tickets.py" in line:
                entities = (
                    await session.execute(
                        select(CodeEntity).where(
                            CodeEntity.index_version_id == index_version_id,
                            CodeEntity.stable_key.like("%TicketService%"),
                        )
                    )
                ).scalars()
                for ent in entities:
                    if ent.stable_key not in traceback_keys:
                        traceback_keys.append(ent.stable_key)
    executed_keys: list[str] = []
    if entry_route_key:
        route = (
            await session.execute(
                select(CodeEntity).where(
                    CodeEntity.index_version_id == index_version_id,
                    CodeEntity.stable_key == entry_route_key,
                )
            )
        ).scalar_one_or_none()
        if route is not None and route.stable_key not in executed_keys:
            executed_keys.append(route.stable_key)

    candidates: list[dict[str, Any]] = []
    for key in traceback_keys:
        candidates.append(
            {"stable_key": key, "evidence_basis": "TRACEBACK", "path": [entry_route_key, key]}
        )
    for key in executed_keys:
        if key not in {c["stable_key"] for c in candidates}:
            candidates.append(
                {"stable_key": key, "evidence_basis": "EXECUTED", "path": [entry_route_key, key]}
            )

    row = TraceCorrelation(
        reproduction_id=reproduction_id,
        index_version_id=index_version_id,
        entry_route_key=entry_route_key,
        traceback_stable_keys=traceback_keys,
        executed_stable_keys=executed_keys,
        candidates=candidates,
    )
    session.add(row)
    await session.flush()
    return row
