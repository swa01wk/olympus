from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.domain.delivery_cycles.models import DeliveryCycle
from core.domain.enums import EntityStatus, KnowledgeClass, SpecStatus
from core.domain.projects.models import Project
from core.domain.tasks.models import Task
from core.product_model.models import Capability, Feature, FeatureSpec, KnowledgeItem


async def product_context_for_task(
    session: AsyncSession,
    task: Task,
) -> dict[str, object]:
    cycle = await session.get(DeliveryCycle, task.delivery_cycle_id)
    if cycle is None:
        return {
            "project_name": None,
            "decision_items": [],
            "approved_product_summary": "",
        }

    project_name: str | None = None
    project = await session.get(Project, cycle.project_id)
    if project is not None:
        project_name = project.name

    decisions = await session.execute(
        select(KnowledgeItem.statement).where(
            KnowledgeItem.delivery_cycle_id == cycle.id,
            KnowledgeItem.knowledge_class == KnowledgeClass.DECISION,
        )
    )
    decision_items = [str(row[0]) for row in decisions.all() if row[0]]

    cap_count = await session.execute(
        select(Capability.id).where(
            Capability.project_id == cycle.project_id,
            Capability.status == EntityStatus.APPROVED,
        )
    )
    feat_count = await session.execute(
        select(Feature.id).where(
            Feature.project_id == cycle.project_id,
            Feature.status == EntityStatus.APPROVED,
        )
    )
    spec_count = await session.execute(
        select(FeatureSpec.id).where(
            FeatureSpec.project_id == cycle.project_id,
            FeatureSpec.status == SpecStatus.APPROVED,
        )
    )
    n_caps = len(cap_count.all())
    n_feats = len(feat_count.all())
    n_specs = len(spec_count.all())
    summary = f"{n_caps} approved capabilities, {n_feats} features, {n_specs} feature specs"

    return {
        "project_name": project_name,
        "decision_items": decision_items,
        "approved_product_summary": summary,
    }
