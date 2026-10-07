"""Post-execution release completion."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from core.commands.context import CommandContext
from core.domain.delivery_cycles.models import DeliveryCycle
from core.domain.delivery_cycles.service import DeliveryCycleService
from core.domain.events.append import append_domain_event
from core.domain.executions.models import Execution
from core.domain.task_contracts.schemas import TaskContractBody
from core.release.enums import ReleaseStatus
from core.release.models import Release
from core.release.outcome import DeliveryOutcomeService


class ReleaseCompletionService:
    async def finalize_if_release_execution(
        self,
        session: AsyncSession,
        execution: Execution,
        contract: TaskContractBody,
        output: dict[str, Any],
        ctx: CommandContext,
    ) -> None:
        if contract.deterministic_executor != "stratos.release":
            return
        if output.get("status") != "RELEASED":
            return
        release_id = None
        for ref in contract.inputs:
            if ref.ref_type == "RELEASE":
                release_id = ref.ref_id
                break
        if release_id is None:
            return
        release = await session.get(Release, release_id)
        if release is None:
            return
        release.status = ReleaseStatus.RELEASED
        release.released_at = datetime.now(UTC)
        release.tag = output.get("tag")
        await session.flush()
        cycle = await session.get(DeliveryCycle, release.delivery_cycle_id)
        if cycle is None:
            return
        await DeliveryOutcomeService().record_released(session, cycle, release, ctx)
        from core.intelligence.baselines.release_promotion import (
            GreenfieldBaselinePromotionService,
        )

        await GreenfieldBaselinePromotionService().on_release(session, release, ctx)
        from core.intelligence.baselines.feature_change_promotion import (
            FeatureChangeBaselinePromotionService,
        )

        await FeatureChangeBaselinePromotionService().on_release(session, release, ctx)
        from core.intelligence.baselines.bug_fix_promotion import BugFixBaselinePromotionService

        await BugFixBaselinePromotionService().on_release(session, release, ctx)
        if cycle.state == "RELEASE":
            await DeliveryCycleService().run_command(
                session, cycle.id, "complete", cycle.state, ctx
            )
        await append_domain_event(
            session,
            aggregate_type="release",
            aggregate_id=release.id,
            event_type="release.executed",
            payload={"integrated_sha": release.integrated_sha, "tag": release.tag},
            actor_id=ctx.actor.id,
            correlation_id=ctx.correlation_id,
            project_id=release.project_id,
            delivery_cycle_id=release.delivery_cycle_id,
        )
