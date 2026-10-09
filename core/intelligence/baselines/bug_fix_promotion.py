"""Release R3: supersede contradicted baselines and promote regression baseline."""

from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.assurance.enums import EvidenceResult
from core.assurance.models import Evidence
from core.commands.context import CommandContext
from core.domain.delivery_cycles.models import DeliveryCycle
from core.domain.enums import DeliveryCycleType, SpecStatus
from core.domain.sequences import next_project_key
from core.intelligence.baselines.enums import (
    BaselineActivation,
    BaselineCheckKind,
    BaselineSource,
    BaselineStatus,
)
from core.intelligence.baselines.models import BehavioralBaseline
from core.intelligence.baselines.sets import BaselineSetService
from core.planning.models import ImplementationSpec, TaskPlanRow
from core.product_model.defects.models import Defect
from core.product_model.defects.repair import RepairSpecValidator
from core.product_model.models import AcceptanceCriterion
from core.release.models import Release


class BugFixBaselinePromotionService:
    async def on_release(
        self,
        session: AsyncSession,
        release: Release,
        ctx: CommandContext,
    ) -> None:
        cycle = await session.get(DeliveryCycle, release.delivery_cycle_id)
        if cycle is None or cycle.type != DeliveryCycleType.BUG_FIX:
            return
        if release.integrated_sha is None or release.integration_candidate_id is None:
            return
        defect = (
            await session.execute(select(Defect).where(Defect.delivery_cycle_id == cycle.id))
        ).scalar_one_or_none()
        if defect is None:
            return
        defect.status = "RELEASED"
        from core.product_model.defects.service import DefectService

        contradicted, _approval_key = await DefectService().superseded_baseline_ids_for_cycle(
            session, cycle.id
        )
        for bl_id in contradicted:
            bl = await session.get(BehavioralBaseline, bl_id)
            if bl is not None and bl.status == BaselineStatus.ACTIVE:
                bl.status = BaselineStatus.SUPERSEDED
        repair_impl = await self._cycle_repair_spec(session, cycle.id)
        if repair_impl is None:
            await session.flush()
            return
        from core.planning.implementation_specs.service import ImplementationSpecService

        body = ImplementationSpecService().parse_body(repair_impl)
        reg_path = RepairSpecValidator().regression_test_path_from_body(body)
        if not reg_path:
            await session.flush()
            return
        reg_rows = list(
            (
                await session.execute(
                    select(Evidence)
                    .where(
                        Evidence.delivery_cycle_id == cycle.id,
                        Evidence.result == EvidenceResult.PASS,
                        Evidence.commit_sha == release.integrated_sha,
                    )
                    .order_by(Evidence.created_at.desc())
                )
            ).scalars()
        )
        reg_ev = next((e for e in reg_rows if reg_path in (e.check_ref or "")), None)
        if reg_ev is None:
            await session.flush()
            return
        ac: AcceptanceCriterion | None = None
        if defect.expected_ac_ids:
            ac = await session.get(AcceptanceCriterion, uuid.UUID(str(defect.expected_ac_ids[0])))
        key = await next_project_key(session, cycle.project_id, "baseline", prefix="BL")
        row = BehavioralBaseline(
            project_id=cycle.project_id,
            lineage_key=key,
            version=1,
            status=BaselineStatus.ACTIVE,
            source=BaselineSource.REPAIR,
            given=ac.given if ac and ac.given else (ac.statement if ac else "Bug fix regression"),
            when=ac.when if ac and ac.when else "Execute regression test",
            then=ac.then if ac and ac.then else "Observed behavior matches approved expectation",
            check_kind=BaselineCheckKind.EXISTING_TEST,
            check_ref=reg_ev.check_ref or reg_path,
            feature_spec_id=ac.feature_spec_id if ac else repair_impl.feature_spec_id,
            ac_lineage_key=ac.lineage_key if ac else None,
            observed_behavior_ids=[],
            exercised_stable_keys=[],
            established_sha=release.integrated_sha,
            established_evidence_id=reg_ev.id,
            activation=BaselineActivation.AUTO_DETERMINISTIC,
        )
        session.add(row)
        await session.flush()
        await BaselineSetService().create_from_active_baselines(
            session,
            cycle.project_id,
            cycle.id,
            release.integrated_sha,
            ctx,
        )

    async def _cycle_repair_spec(
        self, session: AsyncSession, cycle_id: uuid.UUID
    ) -> ImplementationSpec | None:
        plans = (
            await session.execute(
                select(TaskPlanRow)
                .where(
                    TaskPlanRow.delivery_cycle_id == cycle_id,
                    TaskPlanRow.status == "ACCEPTED",
                )
                .order_by(TaskPlanRow.created_at.desc())
            )
        ).scalars()
        for plan in plans:
            for raw_id in plan.implementation_spec_ids or []:
                spec = await session.get(ImplementationSpec, uuid.UUID(str(raw_id)))
                if (
                    spec is not None
                    and spec.kind == "REPAIR"
                    and spec.status == SpecStatus.APPROVED
                ):
                    return spec
        return None
