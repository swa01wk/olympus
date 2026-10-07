"""Post-execution handlers for baseline stage agent outputs."""

from __future__ import annotations

import uuid

from agents.sentinel.schemas import CharacterizationPlan
from sqlalchemy.ext.asyncio import AsyncSession

from core.commands.context import CommandContext
from core.domain.delivery_cycles.models import DeliveryCycle
from core.domain.executions.models import Execution
from core.domain.task_contracts.schemas import TaskContractBody
from core.intelligence.baselines.enums import BaselineCheckKind
from core.intelligence.baselines.proposals import BaselineProposalService


class BaselineCompletionService:
    async def persist_characterization(
        self,
        session: AsyncSession,
        execution: Execution,
        contract: TaskContractBody,
        output: dict[str, object],
        ctx: CommandContext,
    ) -> None:
        plan = CharacterizationPlan.model_validate(output)
        cycle = await session.get(DeliveryCycle, execution.delivery_cycle_id)
        if cycle is None or cycle.base_sha is None:
            return
        spec_id: uuid.UUID | None = None
        for ref in contract.inputs:
            if ref.ref_type == "FEATURE_SPEC":
                spec_id = ref.ref_id
                break
        if spec_id is None:
            return
        svc = BaselineProposalService()
        for check in plan.checks:
            kind = BaselineCheckKind.AUTHORED_TEST
            if check.kind == "API_PROBE":
                kind = BaselineCheckKind.API_PROBE
            check_ref = check.test_filename or (
                f"GET:{check.probe.path}" if check.probe else check.recovered_ac_key
            )
            await svc.create_from_characterization(
                session,
                cycle,
                spec_id,
                check.recovered_ac_key,
                given=check.given,
                when=check.when,
                then=check.then,
                check_kind=kind,
                check_ref=check_ref,
                exercised=list(check.exercised_entities),
                sha=cycle.base_sha,
                ctx=ctx,
            )
