from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.commands.context import CommandContext
from core.domain.events.append import append_domain_event
from core.execution.artifacts import ArtifactStore
from core.product_model.models import ProductSource


class ProductSourceService:
    async def ingest(
        self,
        session: AsyncSession,
        *,
        project_id: uuid.UUID,
        lineage_key: str,
        source_type: str,
        title: str,
        mime_type: str,
        content_hash: str,
        raw_storage_ref: str,
        text: str,
        ctx: CommandContext,
        delivery_cycle_id: uuid.UUID | None = None,
        inbound_event_id: uuid.UUID | None = None,
    ) -> dict[str, Any]:
        dup = await session.execute(
            select(ProductSource).where(
                ProductSource.project_id == project_id,
                ProductSource.lineage_key == lineage_key,
                ProductSource.content_hash == content_hash,
            )
        )
        existing_dup = dup.scalar_one_or_none()
        if existing_dup is not None:
            return {
                "product_source_id": str(existing_dup.id),
                "version": existing_dup.version,
                "duplicate": True,
            }

        latest = await session.execute(
            select(ProductSource)
            .where(
                ProductSource.project_id == project_id,
                ProductSource.lineage_key == lineage_key,
            )
            .order_by(ProductSource.version.desc())
            .limit(1)
        )
        latest_row = latest.scalar_one_or_none()
        version = 1 if latest_row is None else latest_row.version + 1

        store = ArtifactStore()
        text_artifact = await store.put(
            session,
            project_id=project_id,
            delivery_cycle_id=delivery_cycle_id,
            execution_id=None,
            kind="PRODUCT_SOURCE_TEXT",
            schema_name="NormalizedText",
            schema_version="1",
            content={"text": text, "title": title},
            created_by_actor_id=ctx.actor.id,
        )

        row = ProductSource(
            project_id=project_id,
            delivery_cycle_id=delivery_cycle_id,
            lineage_key=lineage_key,
            version=version,
            source_type=source_type,
            title=title,
            mime_type=mime_type,
            content_hash=content_hash,
            raw_storage_ref=raw_storage_ref,
            text_artifact_id=text_artifact.id,
            inbound_event_id=inbound_event_id,
            created_by_actor_id=ctx.actor.id,
        )
        session.add(row)
        await session.flush()
        await append_domain_event(
            session,
            aggregate_type="product_source",
            aggregate_id=row.id,
            event_type="product_source.ingested",
            payload={
                "version": version,
                "lineage_key": lineage_key,
                "content_hash": content_hash,
            },
            actor_id=ctx.actor.id,
            correlation_id=ctx.correlation_id,
            project_id=project_id,
            delivery_cycle_id=delivery_cycle_id,
        )
        return {
            "product_source_id": str(row.id),
            "version": version,
            "text_artifact_id": str(text_artifact.id),
            "duplicate": False,
        }

    async def get(self, session: AsyncSession, source_id: uuid.UUID) -> ProductSource | None:
        return await session.get(ProductSource, source_id)

    async def list_for_project(
        self, session: AsyncSession, project_id: uuid.UUID
    ) -> list[ProductSource]:
        result = await session.execute(
            select(ProductSource)
            .where(ProductSource.project_id == project_id)
            .order_by(ProductSource.lineage_key, ProductSource.version)
        )
        return list(result.scalars())
