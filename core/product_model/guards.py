from __future__ import annotations

from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.domain.approvals.models import Approval
from core.domain.delivery_cycles.models import DeliveryCycle
from core.domain.enums import ApprovalStatus, ApprovalType, ClarificationStatus, SpecStatus
from core.domain.executions.models import Clarification
from core.product_model.models import FeatureSpec, ProductSource, ScopeSet, ScopeSetItem
from core.state.guards import GuardResult


async def product_source_ingested(
    session: AsyncSession,
    cycle: DeliveryCycle,
    _ctx: Any,
) -> GuardResult:
    q = await session.execute(
        select(ProductSource.id)
        .where(
            (ProductSource.delivery_cycle_id == cycle.id)
            | (ProductSource.project_id == cycle.project_id)
        )
        .limit(1)
    )
    if q.scalar_one_or_none() is None:
        return GuardResult(ok=False, reasons=("NO_PRODUCT_SOURCE",))
    return GuardResult(ok=True)


async def scope_approved(
    session: AsyncSession,
    cycle: DeliveryCycle,
    _ctx: Any,
) -> GuardResult:
    blocking = await session.execute(
        select(Clarification.id)
        .where(
            Clarification.delivery_cycle_id == cycle.id,
            Clarification.status == ClarificationStatus.OPEN,
            Clarification.blocking.is_(True),
        )
        .limit(1)
    )
    if blocking.scalar_one_or_none() is not None:
        return GuardResult(ok=False, reasons=("BLOCKING_CLARIFICATION_OPEN",))

    scope = await session.execute(
        select(ScopeSet)
        .where(ScopeSet.delivery_cycle_id == cycle.id)
        .order_by(ScopeSet.created_at.desc())
        .limit(1)
    )
    scope_set = scope.scalar_one_or_none()
    if scope_set is None:
        return GuardResult(ok=False, reasons=("SCOPE_NOT_APPROVED",))

    approval = await session.execute(
        select(Approval).where(
            Approval.approval_type == ApprovalType.SCOPE,
            Approval.subject_type == "scope_set",
            Approval.subject_id == scope_set.id,
            Approval.status == ApprovalStatus.APPROVED,
        )
    )
    appr = approval.scalar_one_or_none()
    if appr is None:
        return GuardResult(ok=False, reasons=("SCOPE_NOT_APPROVED",))
    if appr.subject_hash != scope_set.content_hash:
        return GuardResult(ok=False, reasons=("SCOPE_HASH_MISMATCH",))

    items = await session.execute(
        select(ScopeSetItem).where(ScopeSetItem.scope_set_id == scope_set.id)
    )
    for item in items.scalars():
        spec = await session.get(FeatureSpec, item.feature_spec_id)
        if spec is None:
            return GuardResult(ok=False, reasons=("SCOPE_SPEC_MISSING",))
        if spec.status == SpecStatus.SUPERSEDED:
            return GuardResult(ok=False, reasons=("SCOPE_SPEC_SUPERSEDED",))
        if spec.status != SpecStatus.APPROVED:
            return GuardResult(ok=False, reasons=("SCOPE_SPEC_NOT_APPROVED",))

    return GuardResult(ok=True)
