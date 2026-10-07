"""Impacted obligation selection after remediation (Phase 09 §8)."""

from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.assurance.carry_forward import entity_hashes_for_obligation, entity_sets_unchanged
from core.assurance.enums import EvidenceResult, ObligationStatus
from core.assurance.models import Evidence, VerificationObligation
from core.integration.models import IntegrationCandidate
from core.traceability.models import CodeEntityChange


class ImpactedVerificationService:
    async def mark_impacted(
        self,
        session: AsyncSession,
        new_ic: IntegrationCandidate,
        prior_ic_id: uuid.UUID,
    ) -> list[uuid.UUID]:
        prior_ic = await session.get(IntegrationCandidate, prior_ic_id)
        if prior_ic is None or prior_ic.canonical_index_version_id is None:
            return []
        if new_ic.canonical_index_version_id is None:
            return []
        prior_obligations = {
            o.subject_key: o
            for o in (
                await session.execute(
                    select(VerificationObligation).where(
                        VerificationObligation.integration_candidate_id == prior_ic_id,
                    )
                )
            ).scalars()
        }
        changed_keys = {
            row.stable_key
            for row in (
                await session.execute(
                    select(CodeEntityChange).where(
                        CodeEntityChange.integration_candidate_id == new_ic.id,
                    )
                )
            ).scalars()
        }
        impacted: list[uuid.UUID] = []
        new_obligations = await session.execute(
            select(VerificationObligation).where(
                VerificationObligation.integration_candidate_id == new_ic.id,
            )
        )
        for new_obl in new_obligations.scalars():
            prior_obl = prior_obligations.get(new_obl.subject_key)
            if prior_obl is None:
                impacted.append(new_obl.id)
                new_obl.status = ObligationStatus.OPEN
                continue
            failed = await session.execute(
                select(Evidence.id).where(
                    Evidence.obligation_id == prior_obl.id,
                    Evidence.result == EvidenceResult.FAIL,
                )
            )
            if failed.scalar_one_or_none() is not None:
                impacted.append(new_obl.id)
                new_obl.status = ObligationStatus.OPEN
                continue
            prior_hashes = await entity_hashes_for_obligation(
                session,
                prior_ic.canonical_index_version_id,
                prior_obl,
                repository_id=new_ic.repository_id,
            )
            new_hashes = await entity_hashes_for_obligation(
                session,
                new_ic.canonical_index_version_id,
                new_obl,
                repository_id=new_ic.repository_id,
            )
            entity_changed = not entity_sets_unchanged(prior_hashes, new_hashes)
            code_overlap = bool(
                changed_keys and prior_hashes and any(k in changed_keys for k in prior_hashes)
            )
            if entity_changed or code_overlap:
                impacted.append(new_obl.id)
                new_obl.status = ObligationStatus.OPEN
        await session.flush()
        return impacted
