"""Remediation task creation for integration findings."""

from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from core.assurance.models import Finding
from core.commands.context import CommandContext
from core.domain.enums import TaskOrigin, WorkType
from core.domain.task_contracts.schemas import TaskContractBody
from core.domain.task_contracts.service import ContractService
from core.domain.tasks.service import TaskService
from core.integration.enums import FindingStatus
from core.integration.models import IntegrationCandidate


async def create_merge_conflict_remediation(
    session: AsyncSession,
    ic: IntegrationCandidate,
    finding: Finding,
    conflicting_files: list[str],
    ctx: CommandContext,
) -> None:
    from core.domain.delivery_cycles.models import DeliveryCycle

    cycle = await session.get(DeliveryCycle, ic.delivery_cycle_id)
    if cycle is None:
        return
    task = await TaskService().create_task(
        session,
        cycle.id,
        f"Remediate merge conflict for {ic.key}",
        WorkType.CODE_CHANGE,
        TaskOrigin.REMEDIATION,
        ctx,
        priority=0,
    )
    allowed = sorted(set(conflicting_files))
    body = TaskContractBody(
        objective=f"Resolve merge conflicts for {ic.key}",
        work_type=WorkType.CODE_CHANGE,
        inputs=[],
        repository_id=ic.repository_id,
        base_policy="EXPLICIT_SHA",
        base_commit=ic.integrated_sha or ic.base_sha,
        allowed_scope=allowed or ["**"],
        allowed_actions=["repo.read", "repo.write", "git.commit", "test.run", "shell.run"],
        required_outputs=["candidate_commit", "implementation_result"],
        executor_kind="AGENT_RUNTIME",
        agent_profile="forge.implementation",
        model_alias="implementation",
        timeouts={"wall_clock_s": 3600},
    )
    contract = await ContractService().create_draft(
        session, task.id, body, "integration.remediation", ctx
    )
    await ContractService().issue(session, contract.id, ctx)
    await TaskService().mark_ready(session, task.id, ctx)
    finding.remediation_task_id = task.id
    finding.status = FindingStatus.IN_REMEDIATION
    await session.flush()
