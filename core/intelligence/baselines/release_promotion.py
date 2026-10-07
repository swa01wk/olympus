"""Greenfield release: promote passing mandatory AC evidence to ACTIVE baselines."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.assurance.enums import EvidenceResult, GateType, ObligationStatus
from core.assurance.models import Evidence, VerificationObligation
from core.commands.context import CommandContext
from core.domain.delivery_cycles.models import DeliveryCycle
from core.domain.enums import DeliveryCycleType
from core.domain.sequences import next_project_key
from core.intelligence.baselines.enums import (
    BaselineActivation,
    BaselineCheckKind,
    BaselineSource,
    BaselineStatus,
)
from core.intelligence.baselines.models import BehavioralBaseline
from core.intelligence.baselines.sets import BaselineSetService
from core.policy.policy_service import get_cached_policy_content
from core.product_model.models import AcceptanceCriterion
from core.release.models import Release


class GreenfieldBaselinePromotionService:
    async def on_release(
        self,
        session: AsyncSession,
        release: Release,
        ctx: CommandContext,
    ) -> None:
        policy = get_cached_policy_content()
        release_cfg = policy.get("release") or {}
        if not release_cfg.get("promote_acs_to_baselines", False):
            return
        cycle = await session.get(DeliveryCycle, release.delivery_cycle_id)
        if cycle is None or cycle.type != DeliveryCycleType.GREENFIELD_BUILD:
            return
        if release.integrated_sha is None:
            return
        ic_id = release.integration_candidate_id
        if ic_id is None:
            return
        obligations = (
            (
                await session.execute(
                    select(VerificationObligation).where(
                        VerificationObligation.integration_candidate_id == ic_id,
                        VerificationObligation.gate_type == GateType.SENTINEL.value,
                        VerificationObligation.required.is_(True),
                    )
                )
            )
            .scalars()
            .all()
        )
        created: list[BehavioralBaseline] = []
        for obl in obligations:
            if obl.status != ObligationStatus.SATISFIED:
                continue
            ev = (
                await session.execute(
                    select(Evidence)
                    .where(
                        Evidence.obligation_id == obl.id,
                        Evidence.result == EvidenceResult.PASS,
                        Evidence.commit_sha == release.integrated_sha,
                    )
                    .limit(1)
                )
            ).scalar_one_or_none()
            if ev is None:
                continue
            ac = await session.get(AcceptanceCriterion, obl.subject_id)
            if ac is None:
                continue
            key = await next_project_key(session, cycle.project_id, "baseline", prefix="BL")
            row = BehavioralBaseline(
                project_id=cycle.project_id,
                lineage_key=key,
                version=1,
                status=BaselineStatus.ACTIVE,
                source=BaselineSource.RELEASE_PROMOTION,
                given=ac.given or ac.statement,
                when=ac.when or "Execute mandatory check",
                then=ac.then or "Acceptance criterion satisfied",
                check_kind=BaselineCheckKind.EXISTING_TEST,
                check_ref=ev.check_ref,
                feature_spec_id=ac.feature_spec_id,
                ac_lineage_key=ac.lineage_key,
                observed_behavior_ids=[],
                exercised_stable_keys=[],
                established_sha=release.integrated_sha,
                established_evidence_id=ev.id,
                activation=BaselineActivation.AUTO_DETERMINISTIC,
            )
            session.add(row)
            await session.flush()
            created.append(row)
        if created:
            await BaselineSetService().create_from_active_baselines(
                session,
                cycle.project_id,
                cycle.id,
                release.integrated_sha,
                ctx,
            )
