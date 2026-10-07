"""Evidence carry-forward between superseding integration candidates."""

from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.assurance.coverage import CoverageService
from core.assurance.enums import EvidenceResult, ObligationStatus
from core.assurance.evidence import EvidenceService
from core.assurance.models import AcceptanceCoverage, Evidence, VerificationObligation
from core.commands.context import CommandContext
from core.integration.enums import SpecCodeLinkRelation
from core.integration.models import IntegrationCandidate
from core.intelligence.code_index.models import CodeEntity
from core.traceability.models import SpecCodeLink


async def entity_hashes_for_obligation(
    session: AsyncSession,
    index_version_id: uuid.UUID,
    obligation: VerificationObligation,
    *,
    repository_id: uuid.UUID,
) -> dict[str, str]:
    links = await session.execute(
        select(SpecCodeLink).where(
            SpecCodeLink.spec_id == obligation.subject_id,
            SpecCodeLink.repository_id == repository_id,
            SpecCodeLink.established_index_version_id == index_version_id,
            SpecCodeLink.relation == SpecCodeLinkRelation.VERIFIES,
        )
    )
    keys = {link.code_stable_key for link in links.scalars()}
    if not keys:
        return {}
    entities = await session.execute(
        select(CodeEntity).where(
            CodeEntity.index_version_id == index_version_id,
            CodeEntity.stable_key.in_(keys),
        )
    )
    out: dict[str, str] = {}
    for entity in entities.scalars():
        if entity.content_hash:
            out[entity.stable_key] = entity.content_hash
    return out


def entity_sets_unchanged(
    prior: dict[str, str],
    current: dict[str, str],
) -> bool:
    if not prior or not current:
        return False
    if set(prior.keys()) != set(current.keys()):
        return False
    return all(prior[k] == current[k] for k in prior)


class EvidenceCarryForwardService:
    async def carry_from_superseded(
        self,
        session: AsyncSession,
        new_ic: IntegrationCandidate,
        prior_ic_id: uuid.UUID,
        ctx: CommandContext,
    ) -> list[Evidence]:
        prior_ic = await session.get(IntegrationCandidate, prior_ic_id)
        if (
            prior_ic is None
            or prior_ic.canonical_index_version_id is None
            or new_ic.canonical_index_version_id is None
            or new_ic.integrated_sha is None
        ):
            return []
        new_obligations = await session.execute(
            select(VerificationObligation).where(
                VerificationObligation.integration_candidate_id == new_ic.id,
            )
        )
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
        evidence_svc = EvidenceService()
        carried: list[Evidence] = []
        for new_obl in new_obligations.scalars():
            prior_obl = prior_obligations.get(new_obl.subject_key)
            if prior_obl is None:
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
            if not entity_sets_unchanged(prior_hashes, new_hashes):
                continue
            prior_evidence = await session.execute(
                select(Evidence)
                .join(AcceptanceCoverage, AcceptanceCoverage.evidence_id == Evidence.id)
                .where(
                    AcceptanceCoverage.obligation_id == prior_obl.id,
                    AcceptanceCoverage.satisfied.is_(True),
                    Evidence.result == EvidenceResult.PASS,
                    Evidence.commit_sha == prior_ic.integrated_sha,
                )
                .limit(1)
            )
            source = prior_evidence.scalar_one_or_none()
            if source is None:
                continue
            row = await evidence_svc.record(
                session,
                project_id=source.project_id,
                delivery_cycle_id=new_ic.delivery_cycle_id,
                integration_candidate_id=new_ic.id,
                commit_sha=new_ic.integrated_sha,
                evidence_type=source.evidence_type,
                result=EvidenceResult.PASS,
                subject_type=source.subject_type,
                subject_id=source.subject_id,
                check_ref=f"carried:{source.key}",
                producer=source.producer,
                ctx=ctx,
                obligation_id=new_obl.id,
                carried_forward_from_id=source.id,
                details={"carried_forward_from": source.key},
            )
            new_obl.status = ObligationStatus.SATISFIED
            carried.append(row)
        if carried:
            await CoverageService().recompute_for_ic(session, new_ic.id, ctx)
        await session.flush()
        return carried
