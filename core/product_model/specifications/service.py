from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.commands.context import CommandContext
from core.domain.canonical_json import sha256_hex
from core.domain.enums import SpecStatus
from core.domain.exceptions import DomainError
from core.product_model.models import (
    AcceptanceCriterion,
    Feature,
    FeatureSpec,
    Requirement,
    UserStory,
)
from core.product_model.schemas import FeatureSpecBody


class FeatureSpecService:
    async def create_draft_version(
        self,
        session: AsyncSession,
        feature_id: uuid.UUID,
        body: FeatureSpecBody,
        ctx: CommandContext,
    ) -> FeatureSpec:
        feature = await session.get(Feature, feature_id)
        if feature is None:
            raise DomainError(code="NOT_FOUND", message="Feature not found")

        latest = await session.execute(
            select(FeatureSpec)
            .where(
                FeatureSpec.feature_id == feature_id,
            )
            .order_by(FeatureSpec.version.desc())
            .limit(1)
        )
        latest_row = latest.scalar_one_or_none()
        if latest_row and latest_row.status == SpecStatus.APPROVED:
            version = latest_row.version + 1
            supersedes_id = latest_row.id
        elif latest_row:
            version = latest_row.version + 1
            supersedes_id = latest_row.id
            latest_row.status = SpecStatus.SUPERSEDED
        else:
            version = 1
            supersedes_id = None

        body_dict = body.model_dump(mode="json")
        spec = FeatureSpec(
            project_id=feature.project_id,
            feature_id=feature_id,
            lineage_key=f"SPEC-{feature.key}",
            version=version,
            status=SpecStatus.DRAFT,
            body=body_dict,
            content_hash=sha256_hex(body_dict),
            supersedes_id=supersedes_id,
        )
        session.add(spec)
        await session.flush()
        return spec

    async def get_with_children(
        self, session: AsyncSession, spec_id: uuid.UUID
    ) -> tuple[FeatureSpec, list[Requirement], list[UserStory], list[AcceptanceCriterion]]:
        spec = await session.get(FeatureSpec, spec_id)
        if spec is None:
            raise DomainError(code="NOT_FOUND", message="FeatureSpec not found")
        reqs = list(
            (
                await session.execute(
                    select(Requirement).where(Requirement.feature_spec_id == spec_id)
                )
            ).scalars()
        )
        stories = list(
            (
                await session.execute(select(UserStory).where(UserStory.feature_spec_id == spec_id))
            ).scalars()
        )
        acs = list(
            (
                await session.execute(
                    select(AcceptanceCriterion).where(
                        AcceptanceCriterion.feature_spec_id == spec_id
                    )
                )
            ).scalars()
        )
        return spec, reqs, stories, acs
