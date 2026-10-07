"""Post-execution integration completion (canonical promotion)."""

from __future__ import annotations

from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from core.commands.context import CommandContext
from core.domain.exceptions import DomainError
from core.domain.executions.models import Execution
from core.domain.task_contracts.schemas import TaskContractBody
from core.integration.enums import ICStatus
from core.integration.models import IntegrationCandidate
from core.intelligence.code_index.canonical_service import CanonicalIndexService


class IntegrationCompletionService:
    async def promote_if_validating(
        self,
        session: AsyncSession,
        execution: Execution,
        contract: TaskContractBody,
        output: dict[str, Any],
        ctx: CommandContext,
    ) -> None:
        if contract.deterministic_executor != "integration.merge":
            return
        ic_id = None
        for ref in contract.inputs:
            if ref.ref_type == "INTEGRATION_CANDIDATE":
                ic_id = ref.ref_id
                break
        if ic_id is None:
            return
        ic = await session.get(IntegrationCandidate, ic_id)
        if ic is None or ic.status != ICStatus.VALIDATING:
            return
        try:
            await CanonicalIndexService().promote_ic(session, ic.id, ctx)
        except DomainError:
            raise
