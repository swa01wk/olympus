"""Keyword-matched clarification answers for chained MVP (human fixtures only)."""

from __future__ import annotations

import uuid
from pathlib import Path

import yaml
from core.domain.enums import ClarificationStatus
from core.domain.executions.models import Clarification
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession


def _pick_answer(question: str, rules: dict[str, object]) -> str:
    q = question.lower()
    for entry in rules.get("entries") or []:
        if not isinstance(entry, dict):
            continue
        keywords = entry.get("keywords") or []
        if any(str(kw).lower() in q for kw in keywords):
            return str(entry.get("answer", ""))
    defaults = rules.get("defaults") or []
    if defaults and isinstance(defaults, list):
        first = defaults[0]
        if isinstance(first, dict) and first.get("answer"):
            return str(first["answer"])
    return "Proceed with SupportDesk PRD defaults (closed ticket updates return HTTP 409)."


async def answer_open_clarifications(
    client: AsyncClient,
    session: AsyncSession,
    cycle_id: uuid.UUID,
    *,
    fixture_path: Path | None = None,
) -> int:
    path = fixture_path or (
        Path(__file__).resolve().parents[2]
        / "fixtures"
        / "supportdesk"
        / "clarification_answers.yaml"
    )
    rules = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    rows = await session.execute(
        select(Clarification).where(
            Clarification.delivery_cycle_id == cycle_id,
            Clarification.status == ClarificationStatus.OPEN,
        )
    )
    answered = 0
    for cl in rows.scalars():
        answer = _pick_answer(cl.question or "", rules)
        resp = await client.post(
            f"/clarifications/{cl.id}/answer",
            json={"answer": answer},
        )
        if resp.is_error:
            raise AssertionError(f"clarification answer failed ({resp.status_code}): {resp.text}")
        answered += 1
    return answered
