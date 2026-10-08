"""Aggregate canonical feature specs into one PRD-shaped product-spec document."""

from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.domain.enums import KnowledgeClass, SpecKind, SpecStatus
from core.intelligence.brownfield.models import RecoveredSpecEvidence
from core.product_model.models import (
    AcceptanceCriterion,
    Capability,
    Feature,
    FeatureSpec,
    KnowledgeItem,
    ProductSource,
)

_CANONICAL_STATUSES = (
    SpecStatus.APPROVED,
    SpecStatus.PROMOTED,
    SpecStatus.CONFIRMED_EXISTING,
)


def _refs_feature(subject_refs: list[Any], feature_id: uuid.UUID, spec_id: uuid.UUID) -> bool:
    fid = str(feature_id)
    sid = str(spec_id)
    for ref in subject_refs:
        if not isinstance(ref, dict):
            continue
        if ref.get("feature_id") == fid or ref.get("feature_spec_id") == sid:
            return True
        if ref.get("type") == "FEATURE" and ref.get("id") == fid:
            return True
    return False


class ProductSpecViewService:
    async def build(self, session: AsyncSession, project_id: uuid.UUID) -> dict[str, Any]:
        capabilities = (
            (
                await session.execute(
                    select(Capability)
                    .where(Capability.project_id == project_id)
                    .order_by(Capability.key)
                )
            )
            .scalars()
            .all()
        )
        features = (
            (
                await session.execute(
                    select(Feature).where(Feature.project_id == project_id).order_by(Feature.key)
                )
            )
            .scalars()
            .all()
        )
        specs = (
            (
                await session.execute(
                    select(FeatureSpec).where(
                        FeatureSpec.project_id == project_id,
                        FeatureSpec.status.in_(_CANONICAL_STATUSES),
                    )
                )
            )
            .scalars()
            .all()
        )
        spec_by_feature = self._pick_specs_per_feature(list(specs))

        caps_out: list[dict[str, Any]] = []
        features_by_cap: dict[uuid.UUID | None, list[Feature]] = {}
        for f in features:
            features_by_cap.setdefault(f.capability_id, []).append(f)

        for cap in capabilities:
            cap_features = []
            for feat in features_by_cap.get(cap.id, []):
                entry = await self._feature_entry(session, feat, spec_by_feature.get(feat.id))
                if entry is not None:
                    cap_features.append(entry)
            if cap_features:
                caps_out.append(
                    {
                        "id": str(cap.id),
                        "key": cap.key,
                        "name": cap.name,
                        "description": cap.description,
                        "features": cap_features,
                    }
                )

        unscoped = features_by_cap.get(None, [])
        if unscoped:
            cap_features = []
            for feat in unscoped:
                entry = await self._feature_entry(session, feat, spec_by_feature.get(feat.id))
                if entry is not None:
                    cap_features.append(entry)
            if cap_features:
                caps_out.append(
                    {
                        "id": None,
                        "key": "unscoped",
                        "name": "Unscoped",
                        "description": "",
                        "features": cap_features,
                    }
                )

        return {"project_id": str(project_id), "capabilities": caps_out}

    def _pick_specs_per_feature(self, specs: list[FeatureSpec]) -> dict[uuid.UUID, FeatureSpec]:
        by_feature: dict[uuid.UUID, list[FeatureSpec]] = {}
        for spec in specs:
            by_feature.setdefault(spec.feature_id, []).append(spec)

        chosen: dict[uuid.UUID, FeatureSpec] = {}
        for feature_id, rows in by_feature.items():
            canonical = [
                s
                for s in rows
                if s.spec_kind == SpecKind.CANONICAL and s.status == SpecStatus.APPROVED
            ]
            if canonical:
                chosen[feature_id] = max(canonical, key=lambda s: (s.lineage_key, s.version))
                continue
            confirmed = [
                s
                for s in rows
                if s.spec_kind == SpecKind.RECOVERED and s.status == SpecStatus.CONFIRMED_EXISTING
            ]
            if confirmed:
                chosen[feature_id] = max(confirmed, key=lambda s: s.version)
                continue
            promoted = [s for s in rows if s.status == SpecStatus.PROMOTED]
            if promoted:
                chosen[feature_id] = max(promoted, key=lambda s: s.version)
        return chosen

    async def _feature_entry(
        self,
        session: AsyncSession,
        feature: Feature,
        spec: FeatureSpec | None,
    ) -> dict[str, Any] | None:
        if spec is None:
            return None
        acs = (
            (
                await session.execute(
                    select(AcceptanceCriterion).where(
                        AcceptanceCriterion.feature_spec_id == spec.id
                    )
                )
            )
            .scalars()
            .all()
        )
        provenance = await self._provenance(session, feature, spec)
        body = dict(spec.body or {})
        known_gaps = await self._gaps_for_feature(session, feature.project_id, feature.id, spec.id)
        return {
            "id": str(feature.id),
            "key": feature.key,
            "name": feature.name,
            "description": feature.description,
            "origin": feature.origin.value,
            "source_refs": feature.source_refs or [],
            "spec": {
                "id": str(spec.id),
                "version": spec.version,
                "status": spec.status.value,
                "spec_kind": spec.spec_kind.value,
                "body": body,
                "acceptance_criteria": [
                    {
                        "id": str(a.id),
                        "lineage_key": a.lineage_key,
                        "statement": a.statement,
                        "given": a.given,
                        "when": a.when,
                        "then": a.then,
                        "mandatory": a.mandatory,
                        "evidence_requirement": a.evidence_requirement.value,
                    }
                    for a in acs
                ],
                "provenance": provenance,
                "known_gaps": known_gaps,
            },
        }

    async def _provenance(
        self,
        session: AsyncSession,
        feature: Feature,
        spec: FeatureSpec,
    ) -> dict[str, Any]:
        if spec.promoted_from_id:
            recovered = await session.get(FeatureSpec, spec.promoted_from_id)
            evidence_rows = (
                (
                    await session.execute(
                        select(RecoveredSpecEvidence).where(
                            RecoveredSpecEvidence.feature_spec_id == spec.promoted_from_id
                        )
                    )
                )
                .scalars()
                .all()
            )
            return {
                "kind": "brownfield",
                "confidence": recovered.confidence if recovered else spec.confidence,
                "recovered_evidence": [
                    {
                        "element_type": e.element_type,
                        "element_key": e.element_key,
                        "support_type": e.support_type,
                        "support_ref": e.support_ref,
                        "strength": e.strength,
                    }
                    for e in evidence_rows
                ],
            }
        source: ProductSource | None = None
        if spec.derived_from_source_version_id:
            source = await session.get(ProductSource, spec.derived_from_source_version_id)
        return {
            "kind": "greenfield",
            "product_source_id": str(source.id) if source else None,
            "product_source_version": source.version if source else None,
            "product_source_title": source.title if source else None,
            "feature_source_refs": feature.source_refs or [],
        }

    async def _known_gaps(
        self, session: AsyncSession, project_id: uuid.UUID
    ) -> list[KnowledgeItem]:
        rows = (
            await session.execute(
                select(KnowledgeItem).where(
                    KnowledgeItem.project_id == project_id,
                    KnowledgeItem.knowledge_class == KnowledgeClass.UNCERTAINTY,
                )
            )
        ).scalars()
        return [u for u in rows if (u.provenance or {}).get("accepted_known_gap")]

    async def _gaps_for_feature(
        self,
        session: AsyncSession,
        project_id: uuid.UUID,
        feature_id: uuid.UUID,
        spec_id: uuid.UUID,
    ) -> list[dict[str, Any]]:
        gaps = await self._known_gaps(session, project_id)
        out: list[dict[str, Any]] = []
        for item in gaps:
            if not _refs_feature(item.subject_refs or [], feature_id, spec_id):
                continue
            out.append(
                {
                    "id": str(item.id),
                    "statement": item.statement,
                    "confidence": item.confidence,
                }
            )
        return out
