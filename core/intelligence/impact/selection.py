"""Test and baseline selection from impact with policy floor."""

from __future__ import annotations

import re
import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.integration.enums import SpecCodeLinkRelation, SpecCodeLinkStatus
from core.intelligence.baselines.enums import BaselineStatus
from core.intelligence.baselines.models import BaselineSet, BaselineSetItem, BehavioralBaseline
from core.intelligence.code_index.enums import EntityType, RelationType
from core.intelligence.code_index.models import CodeEntity, CodeRelation
from core.intelligence.impact.enums import BaselineImpactFloor
from core.intelligence.impact.traversal import TraversalHit
from core.policy.policy_service import get_cached_policy_content
from core.product_model.models import FeatureSpec
from core.traceability.models import SpecCodeLink


def _tokenize(text: str) -> set[str]:
    return {t.lower() for t in re.findall(r"[A-Za-z_][A-Za-z0-9_]{2,}", text)}


class ImpactSelection:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def impacted_tests(
        self,
        index_version_id: uuid.UUID,
        structural_hits: dict[str, TraversalHit],
        changed_ac_lineage_keys: set[str],
    ) -> list[tuple[str, str, list[dict[str, str]], float]]:
        """Returns (stable_key, rationale, path, confidence)."""
        out: list[tuple[str, str, list[dict[str, str]], float]] = []
        seen: set[str] = set()

        impacted_ids = [h.entity.id for h in structural_hits.values()]
        if impacted_ids:
            rels = await self._session.execute(
                select(CodeRelation, CodeEntity)
                .join(CodeEntity, CodeRelation.target_entity_id == CodeEntity.id)
                .where(
                    CodeRelation.index_version_id == index_version_id,
                    CodeRelation.relation == RelationType.VERIFIED_BY,
                    CodeRelation.source_entity_id.in_(impacted_ids),
                )
            )
            for rel, test_ent in rels.all():
                if test_ent.type != EntityType.TEST or test_ent.stable_key in seen:
                    continue
                seen.add(test_ent.stable_key)
                source = await self._session.get(CodeEntity, rel.source_entity_id)
                path = [
                    {
                        "from": source.stable_key if source else "",
                        "relation": "VERIFIED_BY",
                        "to": test_ent.stable_key,
                    }
                ]
                out.append(
                    (
                        test_ent.stable_key,
                        "VERIFIED_BY impacted entity",
                        path,
                        rel.confidence,
                    )
                )

        if changed_ac_lineage_keys:
            links = await self._session.execute(
                select(SpecCodeLink).where(
                    SpecCodeLink.relation == SpecCodeLinkRelation.VERIFIES,
                    SpecCodeLink.status == SpecCodeLinkStatus.ACTIVE,
                    SpecCodeLink.spec_lineage_key.in_(changed_ac_lineage_keys),
                )
            )
            for link in links.scalars():
                if link.code_stable_key in seen:
                    continue
                seen.add(link.code_stable_key)
                out.append(
                    (
                        link.code_stable_key,
                        f"VERIFIES changed AC {link.spec_lineage_key}",
                        [
                            {
                                "from": link.spec_lineage_key,
                                "relation": "VERIFIES",
                                "to": link.code_stable_key,
                            }
                        ],
                        link.confidence,
                    )
                )
        return out

    async def impacted_baselines(
        self,
        project_id: uuid.UUID,
        structural_hits: dict[str, TraversalHit],
        changed_spec_lineage_keys: set[str],
    ) -> list[tuple[BehavioralBaseline, str]]:
        policy = get_cached_policy_content().get("impact", {})
        floor = BaselineImpactFloor(
            policy.get("baseline_floor", BaselineImpactFloor.IMPACTED_PLUS_SMOKE.value)
        )
        impacted_keys = set(structural_hits)
        from core.domain.projects.models import Project

        project = await self._session.get(Project, project_id)
        if project is None or project.active_baseline_set_id is None:
            return []
        bset = await self._session.get(BaselineSet, project.active_baseline_set_id)
        if bset is None:
            return []
        items = (
            await self._session.execute(
                select(BaselineSetItem).where(BaselineSetItem.baseline_set_id == bset.id)
            )
        ).scalars()
        selected: list[tuple[BehavioralBaseline, str]] = []
        smoke_picked: set[str] = set()
        for item in items:
            bl = await self._session.get(BehavioralBaseline, item.baseline_id)
            if bl is None or bl.status != BaselineStatus.ACTIVE:
                continue
            exercised = set(bl.exercised_stable_keys or [])
            reason: str | None = None
            if exercised & impacted_keys:
                reason = "exercised_stable_keys intersect impact"
            elif bl.feature_spec_id is not None:
                spec = await self._session.get(FeatureSpec, bl.feature_spec_id)
                if spec and spec.lineage_key in changed_spec_lineage_keys:
                    reason = "feature_spec lineage changed"
            if reason:
                selected.append((bl, reason))
                continue
            if floor == BaselineImpactFloor.ALL:
                selected.append((bl, "policy floor ALL"))
            elif floor == BaselineImpactFloor.IMPACTED_PLUS_SMOKE:
                is_smoke = bl.activation and str(bl.activation).lower() == "smoke"
                feat_key = None
                if bl.feature_spec_id:
                    spec = await self._session.get(FeatureSpec, bl.feature_spec_id)
                    feat_key = str(spec.feature_id) if spec else None
                if is_smoke or (feat_key and feat_key not in smoke_picked):
                    smoke_picked.add(feat_key or str(bl.id))
                    selected.append((bl, "policy smoke floor"))
        return selected

    async def lexical_candidates(
        self,
        index_version_id: uuid.UUID,
        delta_text: str,
        structural_seed_count: int,
        linked_entity_names: set[str],
    ) -> list[tuple[CodeEntity, float]]:
        policy = get_cached_policy_content().get("impact", {})
        min_seeds = int(policy.get("min_structural_seeds", 3))
        tokens = _tokenize(delta_text)
        if not tokens:
            return []
        new_terms = not any(any(t in name.lower() for t in tokens) for name in linked_entity_names)
        if structural_seed_count >= min_seeds and not new_terms:
            return []
        from core.intelligence.code_index.retrieval.lexical import LexicalRetrieval

        hits = await LexicalRetrieval(self._session).search(
            index_version_id, " ".join(sorted(tokens)[:12]), mode="symbol"
        )
        out: list[tuple[CodeEntity, float]] = []
        for hit in hits[: int(policy.get("max_lexical_candidates", 20))]:
            ent = await self._session.get(CodeEntity, hit.entity_id)
            if ent is not None:
                out.append((ent, hit.score))
        return out
