"""Post-execution handlers for baseline stage agent outputs."""

from __future__ import annotations

import uuid

from agents.sentinel.schemas import CharacterizationPlan
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.commands.context import CommandContext
from core.domain.delivery_cycles.models import DeliveryCycle
from core.domain.executions.models import Execution
from core.domain.task_contracts.schemas import TaskContractBody
from core.intelligence.baselines.enums import BaselineCheckKind
from core.intelligence.baselines.proposals import BaselineProposalService
from core.product_model.models import AcceptanceCriterion


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
        ac_keys = set(
            (
                await session.execute(
                    select(AcceptanceCriterion.lineage_key).where(
                        AcceptanceCriterion.feature_spec_id == spec_id
                    )
                )
            )
            .scalars()
            .all()
        )
        svc = BaselineProposalService()
        for check in plan.checks:
            if check.recovered_ac_key not in ac_keys:
                continue
            if check.kind == "API_PROBE":
                if check.probe is None:
                    continue
                kind = BaselineCheckKind.API_PROBE
                check_ref = f"GET:{check.probe.path}"
                test_code = None
            else:
                if not check.test_code or not check.test_code.strip():
                    continue
                kind = BaselineCheckKind.AUTHORED_TEST
                check_ref = check.test_filename or check.recovered_ac_key
                test_code = check.test_code
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
                test_code=test_code,
                execution_id=execution.id,
            )
