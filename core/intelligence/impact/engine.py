"""Deterministic impact assessment with optional semantic expansion."""

from __future__ import annotations

import json
import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.commands.context import CommandContext
from core.domain.canonical_json import sha256_hex
from core.domain.events.append import append_domain_event
from core.domain.exceptions import DomainError
from core.domain.sequences import next_project_key
from core.integration.enums import SpecCodeLinkStatus
from core.intelligence.code_index.embeddings import EmbeddingService
from core.intelligence.code_index.enums import EntityType
from core.intelligence.code_index.models import CodeIndexVersion
from core.intelligence.code_index.retrieval.semantic import SemanticRetrieval
from core.intelligence.impact.architecture_flag import ArchitectureDeltaHeuristic
from core.intelligence.impact.enums import (
    ImpactAssessmentStatus,
    ImpactItemType,
    ImpactKind,
    ImpactRetrievalSource,
    ImpactSeedKind,
)
from core.intelligence.impact.models import ImpactAssessment, ImpactItem, SpecDelta
from core.intelligence.impact.selection import ImpactSelection
from core.intelligence.impact.traversal import ImpactTraversal
from core.policy.policy_service import ensure_policy_version, get_cached_policy_content
from core.traceability.spec_code_links.service import SpecCodeLinkService


class ImpactEngine:
    def __init__(self, *, embeddings: EmbeddingService | None = None) -> None:
        self._embeddings = embeddings or EmbeddingService()

    async def assess(
        self,
        session: AsyncSession,
        cycle_id: uuid.UUID,
        *,
        spec_delta_id: uuid.UUID | None = None,
        seed_stable_keys: list[str] | None = None,
        index_version_id: uuid.UUID,
        ctx: CommandContext,
    ) -> ImpactAssessment:
        from core.domain.delivery_cycles.models import DeliveryCycle

        cycle = await session.get(DeliveryCycle, cycle_id)
        if cycle is None:
            raise DomainError(code="NOT_FOUND", message="Delivery cycle not found")
        version = await session.get(CodeIndexVersion, index_version_id)
        if version is None:
            raise DomainError(code="NOT_FOUND", message="Index version not found")

        spec_delta: SpecDelta | None = None
        seed_kind = ImpactSeedKind.MANUAL
        if spec_delta_id is not None:
            spec_delta = await session.get(SpecDelta, spec_delta_id)
            if spec_delta is None:
                raise DomainError(code="NOT_FOUND", message="SpecDelta not found")
            seed_kind = ImpactSeedKind.SPEC_DELTA
        elif seed_stable_keys:
            seed_kind = ImpactSeedKind.DEFECT_ROOT_CAUSE

        policy_svc = await ensure_policy_version(session)
        policy_version_id = (
            policy_svc.version_row.id if policy_svc.version_row is not None else None
        )
        key = await next_project_key(session, cycle.project_id, "impact_assessment", prefix="IA")
        ia = ImpactAssessment(
            key=key,
            delivery_cycle_id=cycle_id,
            index_version_id=index_version_id,
            commit_sha=version.commit_sha,
            seed_kind=seed_kind.value,
            spec_delta_id=spec_delta_id,
            seed_refs=list(seed_stable_keys or []),
            status=ImpactAssessmentStatus.RUNNING.value,
            architecture_delta_suggested=False,
            summary={},
            policy_version_id=policy_version_id,
            content_hash="",
        )
        session.add(ia)
        await session.flush()

        seed_keys: set[str] = set(seed_stable_keys or [])
        link_conf: dict[str, float] = {}
        changed_ac_keys: set[str] = set()
        changed_spec_lineage: set[str] = set()
        delta_text = ""

        if spec_delta is not None:
            changes = spec_delta.changes or {}
            ac_part = changes.get("acceptance_criteria") or {}
            for row in ac_part.get("added") or []:
                changed_ac_keys.add(row["lineage_key"])
            for row in ac_part.get("modified") or []:
                changed_ac_keys.add(row["lineage_key"])
            from core.product_model.models import FeatureSpec

            to_spec = await session.get(FeatureSpec, spec_delta.to_spec_id)
            if to_spec:
                changed_spec_lineage.add(to_spec.lineage_key)
            delta_text = json.dumps(changes)
            lineage_keys = {to_spec.lineage_key} if to_spec else set()
            for ac_key in changed_ac_keys:
                lineage_keys.add(ac_key)
            for lk in lineage_keys:
                for link in await SpecCodeLinkService().links_for_spec(session, lk):
                    if link.status != SpecCodeLinkStatus.ACTIVE:
                        continue
                    seed_keys.add(link.code_stable_key)
                    link_conf[link.code_stable_key] = min(
                        link_conf.get(link.code_stable_key, 1.0), link.confidence
                    )

        traversal = ImpactTraversal(session)
        structural = await traversal.expand(index_version_id, seed_keys, link_confidence=link_conf)
        selection = ImpactSelection(session)
        tests = await selection.impacted_tests(index_version_id, structural, changed_ac_keys)
        baselines = await selection.impacted_baselines(
            cycle.project_id, structural, changed_spec_lineage
        )

        linked_names = {h.entity.qualified_name for h in structural.values()}
        lexical = await selection.lexical_candidates(
            index_version_id, delta_text, len(seed_keys), linked_names
        )

        policy = get_cached_policy_content().get("impact", {})
        max_items = int(policy.get("max_items", 500))
        semantic_note: str | None = None
        from core.intelligence.code_index.retrieval.types import RetrievalHit

        semantic_hits: list[RetrievalHit] = []
        min_structural = int(policy.get("min_semantic_threshold", 5))
        if len(structural) < min_structural or (lexical == [] and delta_text):
            vec = await self._embeddings.embed_texts(
                session,
                subject_type="SPEC_DELTA",
                subject_key=str(spec_delta_id or cycle_id),
                content_hash=sha256_hex({"text": delta_text}),
                texts=[delta_text or " ".join(seed_keys)],
                repository_id=version.repository_id,
                metadata={"correlation_id": ctx.correlation_id},
            )
            if vec and vec[0]:
                semantic_hits = await SemanticRetrieval(session).search(
                    index_version_id, vec[0], limit=int(policy.get("max_semantic_candidates", 15))
                )
            else:
                semantic_note = "SEMANTIC_UNAVAILABLE"

        arch_flag = False
        if spec_delta is not None:
            arch_flag = await ArchitectureDeltaHeuristic().suggest(
                session,
                cycle.project_id,
                spec_delta.to_spec_id,
                structural,
                spec_delta.changes,
            )

        items: list[ImpactItem] = []
        verify_keys: set[str] = set()

        def add_item(
            *,
            item_type: str,
            ref: str,
            impact_kind: str,
            retrieval_source: str,
            path: list[dict[str, str]],
            confidence: float,
            contract_surface: bool,
            rationale: str,
            selected: bool,
        ) -> None:
            if len(items) >= max_items:
                return
            items.append(
                ImpactItem(
                    impact_assessment_id=ia.id,
                    item_type=item_type,
                    ref=ref,
                    impact_kind=impact_kind,
                    retrieval_source=retrieval_source,
                    path=path,
                    confidence=confidence,
                    contract_surface=contract_surface,
                    rationale=rationale,
                    selected_for_verification=selected,
                )
            )

        for sk, hit in structural.items():
            itype = (
                ImpactItemType.CONTRACT.value
                if hit.contract_surface
                else ImpactItemType.CODE_ENTITY.value
            )
            selected = hit.impact_kind in {"DIRECT", "TRANSITIVE"}
            if selected:
                verify_keys.add(sk)
            add_item(
                item_type=itype,
                ref=sk,
                impact_kind=hit.impact_kind,
                retrieval_source=ImpactRetrievalSource.STRUCTURAL.value,
                path=hit.path,
                confidence=hit.confidence,
                contract_surface=hit.contract_surface,
                rationale="structural traversal",
                selected=selected,
            )

        for stable_key, rationale, path, conf in tests:
            add_item(
                item_type=ImpactItemType.TEST.value,
                ref=stable_key,
                impact_kind=ImpactKind.DIRECT.value,
                retrieval_source=ImpactRetrievalSource.STRUCTURAL.value,
                path=path,
                confidence=conf,
                contract_surface=False,
                rationale=rationale,
                selected=True,
            )
            verify_keys.add(stable_key)

        for bl, reason in baselines:
            add_item(
                item_type=ImpactItemType.BASELINE.value,
                ref=bl.lineage_key,
                impact_kind=ImpactKind.DIRECT.value,
                retrieval_source=ImpactRetrievalSource.STRUCTURAL.value,
                path=[],
                confidence=1.0,
                contract_surface=False,
                rationale=reason,
                selected=True,
            )

        for ent, score in lexical:
            if ent.stable_key in structural:
                continue
            add_item(
                item_type=ImpactItemType.CODE_ENTITY.value,
                ref=ent.stable_key,
                impact_kind=ImpactKind.CANDIDATE.value,
                retrieval_source=ImpactRetrievalSource.LEXICAL.value,
                path=[],
                confidence=score,
                contract_surface=ent.type
                in {
                    EntityType.SCHEMA,
                    EntityType.ROUTE,
                    EntityType.ORM_MODEL,
                    EntityType.TABLE,
                },
                rationale="lexical expansion",
                selected=False,
            )

        for sem_hit in semantic_hits:
            if sem_hit.stable_key in structural:
                continue
            add_item(
                item_type=ImpactItemType.CODE_ENTITY.value,
                ref=sem_hit.stable_key,
                impact_kind=ImpactKind.SEMANTIC_CANDIDATE.value,
                retrieval_source=ImpactRetrievalSource.SEMANTIC.value,
                path=[],
                confidence=sem_hit.score,
                contract_surface=False,
                rationale="semantic expansion",
                selected=False,
            )

        for row in items:
            session.add(row)

        payload: dict[str, object] = {
            "structural_count": len(structural),
            "tests": len(tests),
            "baselines": len(baselines),
            "lexical": len(lexical),
            "semantic": len(semantic_hits),
        }
        if semantic_note:
            payload["semantic_note"] = semantic_note
        ia.architecture_delta_suggested = arch_flag
        ia.summary = payload
        ia.status = ImpactAssessmentStatus.COMPLETE.value
        ia.content_hash = sha256_hex(
            {
                "items": [
                    (i.ref, i.impact_kind, i.retrieval_source, i.selected_for_verification)
                    for i in items
                ]
            }
        )
        await session.flush()

        await append_domain_event(
            session,
            aggregate_type="impact_assessment",
            aggregate_id=ia.id,
            event_type="impact.assessed",
            payload={"content_hash": ia.content_hash, "spec_delta_id": str(spec_delta_id or "")},
            actor_id=ctx.actor.id,
            correlation_id=ctx.correlation_id,
            project_id=cycle.project_id,
            delivery_cycle_id=cycle_id,
        )
        return ia

    async def latest_complete(
        self, session: AsyncSession, delivery_cycle_id: uuid.UUID
    ) -> ImpactAssessment | None:
        result = await session.execute(
            select(ImpactAssessment)
            .where(
                ImpactAssessment.delivery_cycle_id == delivery_cycle_id,
                ImpactAssessment.status == ImpactAssessmentStatus.COMPLETE.value,
            )
            .order_by(ImpactAssessment.created_at.desc())
            .limit(1)
        )
        return result.scalar_one_or_none()
