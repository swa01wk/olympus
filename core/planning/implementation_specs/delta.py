"""ImplementationSpec kind=DELTA drafts."""

from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.commands.context import CommandContext
from core.domain.exceptions import DomainError
from core.intelligence.impact.enums import ImpactItemType, ImpactKind
from core.intelligence.impact.models import ImpactAssessment, ImpactItem
from core.planning.implementation_specs.service import ImplementationSpecService
from core.planning.models import ImplementationSpec
from core.planning.schemas import ImplementationSpecBody, ImplementationSpecDraft
from core.product_model.models import FeatureSpec


class ImplementationSpecDeltaService:
    def __init__(self) -> None:
        self._impl = ImplementationSpecService()

    async def persist_delta(
        self,
        session: AsyncSession,
        *,
        parent_impl_id: uuid.UUID,
        body: ImplementationSpecBody,
        feature_spec_id: uuid.UUID,
        execution_id: uuid.UUID | None,
        ctx: CommandContext,
    ) -> ImplementationSpec:
        parent = await session.get(ImplementationSpec, parent_impl_id)
        if parent is None:
            raise DomainError(code="NOT_FOUND", message="Parent ImplementationSpec not found")
        spec = await session.get(FeatureSpec, feature_spec_id)
        if spec is None:
            raise DomainError(code="NOT_FOUND", message="FeatureSpec not found")
        draft = ImplementationSpecDraft(body=body)
        row = await self._impl.persist_draft(
            session,
            feature_spec_id=feature_spec_id,
            draft=draft,
            execution_id=execution_id,
            ctx=ctx,
            for_delta=True,
        )
        row.supersedes_id = parent.id
        row.kind = "DELTA"
        await session.flush()
        return row

    async def latest_delta(
        self, session: AsyncSession, feature_spec_id: uuid.UUID
    ) -> ImplementationSpec | None:
        result = await session.execute(
            select(ImplementationSpec)
            .where(
                ImplementationSpec.feature_spec_id == feature_spec_id,
                ImplementationSpec.kind == "DELTA",
            )
            .order_by(ImplementationSpec.version.desc())
            .limit(1)
        )
        return result.scalar_one_or_none()

    def validate_impact_consistency(
        self,
        body: ImplementationSpecBody,
        *,
        impact_items: list[ImpactItem],
    ) -> tuple[bool, list[str]]:
        errors: list[str] = []
        scope_patterns = list(body.file_scope)
        refs = {c.lower() for c in body.components}
        refs.update(a.path.lower() for a in body.apis if a.path)
        refs.update(s.name.lower() for s in body.schemas)

        for item in impact_items:
            if item.impact_kind != ImpactKind.DIRECT.value or not item.contract_surface:
                continue
            ref = item.ref
            raw_path = item.path
            if isinstance(raw_path, list):
                path = "/".join(str(p) for p in raw_path).lower()
            else:
                path = str(raw_path or ref).lower()
            ref_l = ref.lower()
            if any(
                (r.startswith("/") and (r in ref_l or f" {r.strip()}" in ref_l))
                or (not r.startswith("/") and r in ref_l)
                for r in refs
            ):
                continue
            if (
                scope_patterns
                and not item.contract_surface
                and any(path.startswith(p.rstrip("*").rstrip("/").lower()) for p in scope_patterns)
            ):
                continue
            errors.append(f"unaddressed DIRECT contract surface: {ref} ({item.path})")
        return (not errors, errors)

    async def validate_for_cycle(
        self,
        session: AsyncSession,
        *,
        delivery_cycle_id: uuid.UUID,
        body: ImplementationSpecBody,
    ) -> tuple[bool, list[str]]:
        ia = (
            await session.execute(
                select(ImpactAssessment)
                .where(ImpactAssessment.delivery_cycle_id == delivery_cycle_id)
                .order_by(ImpactAssessment.created_at.desc())
                .limit(1)
            )
        ).scalar_one_or_none()
        if ia is None:
            return True, []
        items = list(
            (
                await session.execute(
                    select(ImpactItem).where(ImpactItem.impact_assessment_id == ia.id)
                )
            ).scalars()
        )
        direct = [i for i in items if i.item_type == ImpactItemType.CODE_ENTITY.value]
        return self.validate_impact_consistency(body, impact_items=direct)


async def resolve_parent_implementation_spec(
    session: AsyncSession,
    *,
    project_id: uuid.UUID,
    feature_spec_id: uuid.UUID,
) -> ImplementationSpec | None:
    from core.domain.enums import SpecStatus

    parent = (
        await session.execute(
            select(ImplementationSpec)
            .where(
                ImplementationSpec.feature_spec_id != feature_spec_id,
                ImplementationSpec.project_id == project_id,
                ImplementationSpec.status == SpecStatus.APPROVED,
                ImplementationSpec.kind != "DELTA",
            )
            .order_by(ImplementationSpec.version.desc())
            .limit(1)
        )
    ).scalar_one_or_none()
    if parent is not None:
        return parent
    return (
        await session.execute(
            select(ImplementationSpec)
            .where(
                ImplementationSpec.project_id == project_id,
                ImplementationSpec.status == SpecStatus.APPROVED,
                ImplementationSpec.kind != "DELTA",
            )
            .order_by(ImplementationSpec.created_at.desc())
            .limit(1)
        )
    ).scalar_one_or_none()
