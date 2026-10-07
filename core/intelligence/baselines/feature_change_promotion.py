"""Release R2: promote new AC baselines and supersede modified AC baselines."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.assurance.enums import EvidenceResult, ObligationReason, ObligationStatus
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
from core.product_model.models import AcceptanceCriterion
from core.release.models import Release


class FeatureChangeBaselinePromotionService:
    async def on_release(
        self,
        session: AsyncSession,
        release: Release,
        ctx: CommandContext,
    ) -> None:
        cycle = await session.get(DeliveryCycle, release.delivery_cycle_id)
        if cycle is None or cycle.type != DeliveryCycleType.FEATURE_CHANGE:
            return
        if release.integrated_sha is None or release.integration_candidate_id is None:
            return
        ic_id = release.integration_candidate_id
        obligations = (
            await session.execute(
                select(VerificationObligation).where(
                    VerificationObligation.integration_candidate_id == ic_id,
                    VerificationObligation.status == ObligationStatus.SATISFIED,
                )
            )
        ).scalars()
        promoted: list[BehavioralBaseline] = []
        for obl in obligations:
            if obl.reason not in {
                ObligationReason.AC_MANDATORY,
                ObligationReason.AC_REVALIDATION,
                ObligationReason.BASELINE_REQUIRED,
            }:
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
            if obl.subject_type == "BASELINE":
                bl = await session.get(BehavioralBaseline, obl.subject_id)
                if bl is None:
                    continue
                if (
                    obl.reason == ObligationReason.BASELINE_REQUIRED
                    and bl.status == BaselineStatus.ACTIVE
                ):
                    bl.status = BaselineStatus.SUPERSEDED
                    promoted.append(
                        BehavioralBaseline(
                            project_id=cycle.project_id,
                            lineage_key=bl.lineage_key,
                            version=bl.version + 1,
                            status=BaselineStatus.ACTIVE,
                            source=BaselineSource.RELEASE_PROMOTION,
                            given=bl.given,
                            when=bl.when,
                            then=bl.then,
                            check_kind=bl.check_kind,
                            check_ref=ev.check_ref,
                            feature_spec_id=bl.feature_spec_id,
                            ac_lineage_key=bl.ac_lineage_key,
                            observed_behavior_ids=bl.observed_behavior_ids,
                            exercised_stable_keys=bl.exercised_stable_keys,
                            established_sha=release.integrated_sha,
                            established_evidence_id=ev.id,
                            activation=BaselineActivation.AUTO_DETERMINISTIC,
                        )
                    )
                    session.add(promoted[-1])
                continue
            ac = await session.get(AcceptanceCriterion, obl.subject_id)
            if ac is None or not ac.mandatory:
                continue
            if ac.change_kind not in {None, "ADDED", "MODIFIED"}:
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
            promoted.append(row)
            if ac.change_kind == "MODIFIED":
                old = (
                    await session.execute(
                        select(BehavioralBaseline).where(
                            BehavioralBaseline.project_id == cycle.project_id,
                            BehavioralBaseline.ac_lineage_key == ac.lineage_key,
                            BehavioralBaseline.status == BaselineStatus.ACTIVE,
                        )
                    )
                ).scalar_one_or_none()
                if old is not None:
                    old.status = BaselineStatus.SUPERSEDED
        if promoted:
            await BaselineSetService().create_from_active_baselines(
                session,
                cycle.project_id,
                cycle.id,
                release.integrated_sha,
                ctx,
            )
        from core.product_model.changes.service import ChangeRequestService

        await ChangeRequestService().mark_done(session, cycle.id, release.id, ctx)
