from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.domain.enums import SpecKind
from core.integration.enums import SpecCodeLinkRelation
from core.product_model.models import FeatureSpec
from core.traceability.models import SpecCodeLink


class RecoveryReconciliationService:
    async def compare(
        self,
        session: AsyncSession,
        project_id: uuid.UUID,
        recovered_spec_ids: list[uuid.UUID],
    ) -> dict[str, Any]:
        canonical = (
            (
                await session.execute(
                    select(FeatureSpec).where(
                        FeatureSpec.project_id == project_id,
                        FeatureSpec.spec_kind == SpecKind.CANONICAL,
                    )
                )
            )
            .scalars()
            .all()
        )
        recovered: list[FeatureSpec] = []
        for sid in recovered_spec_ids:
            row = await session.get(FeatureSpec, sid)
            if row is not None:
                recovered.append(row)
        matched: list[str] = []
        new: list[str] = []
        missing: list[str] = []
        divergent: list[str] = []

        async def principal_keys(spec_id: uuid.UUID) -> set[str]:
            links = (
                await session.execute(
                    select(SpecCodeLink).where(
                        SpecCodeLink.spec_id == spec_id,
                        SpecCodeLink.relation == SpecCodeLinkRelation.IMPLEMENTS,
                    )
                )
            ).scalars()
            return {link.code_stable_key for link in links}

        recovered_keys = {}
        for spec in recovered:
            recovered_keys[spec.id] = await principal_keys(spec.id)

        for cspec in canonical:
            ckeys = await principal_keys(cspec.id)
            found = False
            for rspec in recovered:
                rkeys = recovered_keys.get(rspec.id, set())
                if ckeys and ckeys == rkeys:
                    matched.append(str(rspec.id))
                    found = True
                    if _ac_overlap(cspec.body, rspec.body) < 0.3:
                        divergent.append(str(rspec.id))
            if not found:
                missing.append(str(cspec.id))

        canonical_key_sets: list[set[str]] = []
        for spec in canonical:
            canonical_key_sets.append(await principal_keys(spec.id))
        for rspec in recovered:
            rkeys = recovered_keys.get(rspec.id, set())
            if not any(rkeys and rkeys == ck for ck in canonical_key_sets if ck):
                new.append(str(rspec.id))

        return {
            "MATCHED": matched,
            "NEW": new,
            "MISSING": missing,
            "DIVERGENT": divergent,
        }


def _ac_overlap(a_body: dict[str, Any], b_body: dict[str, Any]) -> float:
    a_text = str(a_body.get("summary", "")).lower()
    b_text = str(b_body.get("summary", "")).lower()
    a_words = set(a_text.split())
    b_words = set(b_text.split())
    if not a_words or not b_words:
        return 0.0
    return len(a_words & b_words) / len(a_words | b_words)
