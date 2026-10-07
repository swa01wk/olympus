from __future__ import annotations

import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from core.commands.context import CommandContext
from core.domain.enums import KnowledgeClass, KnowledgeItemStatus
from core.domain.events.append import append_domain_event
from core.product_model.models import KnowledgeItem


class KnowledgeService:
    async def create_decision_from_clarification(
        self,
        session: AsyncSession,
        *,
        project_id: uuid.UUID,
        delivery_cycle_id: uuid.UUID,
        clarification_id: uuid.UUID,
        statement: str,
        ctx: CommandContext,
    ) -> KnowledgeItem:
        row = KnowledgeItem(
            project_id=project_id,
            delivery_cycle_id=delivery_cycle_id,
            knowledge_class=KnowledgeClass.DECISION,
            statement=statement,
            subject_refs=[{"ref_type": "CLARIFICATION", "ref_id": str(clarification_id)}],
            provenance={
                "origin": "HUMAN",
                "actor_id": str(ctx.actor.id),
            },
            status=KnowledgeItemStatus.ACTIVE,
            blocking=False,
        )
        session.add(row)
        await session.flush()
        await append_domain_event(
            session,
            aggregate_type="knowledge_item",
            aggregate_id=row.id,
            event_type="knowledge_item.created",
            payload={"class": KnowledgeClass.DECISION.value},
            actor_id=ctx.actor.id,
            correlation_id=ctx.correlation_id,
            project_id=project_id,
            delivery_cycle_id=delivery_cycle_id,
        )
        return row
