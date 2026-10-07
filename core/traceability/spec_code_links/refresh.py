"""Refresh SpecCodeLinks after canonical index promotion."""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.assurance.findings import FindingService
from core.commands.context import CommandContext
from core.integration.enums import (
    FindingSeverity,
    FindingSource,
    SpecCodeLinkOrigin,
    SpecCodeLinkStatus,
)
from core.intelligence.code_index.models import CodeEntity
from core.traceability.models import SpecCodeLink


@dataclass
class RefreshReport:
    stale_links: list[str] = field(default_factory=list)
    updated_links: list[str] = field(default_factory=list)
    missing_principals: list[str] = field(default_factory=list)
    artifact_id: uuid.UUID | None = None

    def to_dict(self) -> dict[str, object]:
        return {
            "stale_links": self.stale_links,
            "updated_links": self.updated_links,
            "missing_principals": self.missing_principals,
            "artifact_id": str(self.artifact_id) if self.artifact_id else None,
        }


class SpecCodeLinkRefreshService:
    async def refresh(
        self,
        session: AsyncSession,
        *,
        repository_id: uuid.UUID,
        canonical_index_version_id: uuid.UUID,
        delivery_cycle_id: uuid.UUID,
        project_id: uuid.UUID,
        ctx: CommandContext,
    ) -> RefreshReport:
        entities = await session.execute(
            select(CodeEntity).where(CodeEntity.index_version_id == canonical_index_version_id)
        )
        by_key = {e.stable_key: e for e in entities.scalars()}
        links = await session.execute(
            select(SpecCodeLink).where(
                SpecCodeLink.repository_id == repository_id,
                SpecCodeLink.status == SpecCodeLinkStatus.ACTIVE,
            )
        )
        report = RefreshReport()
        finding_svc = FindingService()
        for link in links.scalars():
            ent = by_key.get(link.code_stable_key)
            if ent is None:
                link.status = SpecCodeLinkStatus.STALE
                report.stale_links.append(link.code_stable_key)
                severity = (
                    FindingSeverity.MAJOR
                    if link.origin
                    in {SpecCodeLinkOrigin.GENERATED_LINEAGE, SpecCodeLinkOrigin.HUMAN_CONFIRMED}
                    else FindingSeverity.MINOR
                )
                await finding_svc.create(
                    session,
                    project_id=project_id,
                    delivery_cycle_id=delivery_cycle_id,
                    source=FindingSource.INTEGRATION,
                    category="LINEAGE_LINK_STALE",
                    severity=severity,
                    title=f"SpecCodeLink stale: {link.code_stable_key}",
                    detail={
                        "stable_key": link.code_stable_key,
                        "spec_lineage_key": link.spec_lineage_key,
                    },
                    ctx=ctx,
                )
                continue
            prev = link.last_confirmed_index_version_id
            hash_changed = ent.content_hash != by_key.get(link.code_stable_key, ent).content_hash
            if hash_changed or prev != canonical_index_version_id:
                link.last_confirmed_index_version_id = canonical_index_version_id
                report.updated_links.append(link.code_stable_key)
        await session.flush()
        from core.execution.artifacts import ArtifactStore

        payload: dict[str, object] = {
            "stale_links": report.stale_links,
            "updated_links": report.updated_links,
            "missing_principals": report.missing_principals,
        }
        artifact = await ArtifactStore().put(
            session,
            project_id=project_id,
            delivery_cycle_id=delivery_cycle_id,
            execution_id=None,
            kind="spec_code_link.refresh_report",
            schema_name="RefreshReport",
            schema_version="1",
            content=payload,
            created_by_actor_id=ctx.actor.id,
        )
        report.artifact_id = artifact.id
        return report
