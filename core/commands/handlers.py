"""CommandBus handlers for control-plane write operations."""

from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from core.commands.context import CommandContext
from core.domain.approvals.service import ApprovalService
from core.domain.delivery_cycles.models import DeliveryCycle
from core.domain.delivery_cycles.service import DeliveryCycleService
from core.domain.enums import ApprovalStatus, ApprovalType, DeliveryCycleType, TaskOrigin, WorkType
from core.domain.exceptions import DomainError
from core.domain.projects.service import ProjectService
from core.domain.task_contracts.schemas import TaskContractBody
from core.domain.task_contracts.service import ContractService
from core.domain.tasks.service import TaskService
from core.policy.policy_service import ensure_policy_version
from core.repositories.service import RepositoryService
from core.state.transition_service import TransitionService


async def handle_create_project(
    session: AsyncSession,
    ctx: CommandContext,
    payload: dict[str, Any],
) -> dict[str, Any]:
    project = await ProjectService().create(
        session,
        payload["key"],
        payload["name"],
        payload.get("description"),
        ctx,
    )
    return {"project_id": str(project.id)}


async def handle_create_delivery_cycle(
    session: AsyncSession,
    ctx: CommandContext,
    payload: dict[str, Any],
) -> dict[str, Any]:
    repo_id = payload.get("repository_id")
    cycle = await DeliveryCycleService().create(
        session,
        uuid.UUID(payload["project_id"]),
        DeliveryCycleType(payload["type"]),
        payload["objective"],
        ctx,
        repository_id=uuid.UUID(repo_id) if repo_id else None,
    )
    return {"cycle_id": str(cycle.id)}


async def handle_delivery_cycle_transition(
    session: AsyncSession,
    ctx: CommandContext,
    payload: dict[str, Any],
) -> dict[str, Any]:
    cycle_id = uuid.UUID(payload["cycle_id"])
    command_name = payload["command_name"]
    result = await DeliveryCycleService().run_command(
        session,
        cycle_id,
        command_name,
        payload["expected_state"],
        ctx,
        payload=payload.get("payload"),
    )
    return {"from_state": result.from_state, "to_state": result.to_state}


async def handle_create_task(
    session: AsyncSession,
    ctx: CommandContext,
    payload: dict[str, Any],
) -> dict[str, Any]:
    task = await TaskService().create_task(
        session,
        uuid.UUID(payload["cycle_id"]),
        payload["title"],
        WorkType(payload["work_type"]),
        TaskOrigin(payload.get("origin", TaskOrigin.CONTROL_PLANE.value)),
        ctx,
        priority=int(payload.get("priority", 100)),
    )
    return {"task_id": str(task.id)}


async def handle_task_command(
    session: AsyncSession,
    ctx: CommandContext,
    payload: dict[str, Any],
) -> dict[str, Any]:
    task_id = uuid.UUID(payload["task_id"])
    command_name = payload["command_name"]
    if command_name == "mark_ready":
        task = await TaskService().mark_ready(session, task_id, ctx)
        return {"status": task.status.value}
    result = await TransitionService().transition(
        session,
        "task",
        task_id,
        payload["expected_state"],
        command_name,
        ctx,
    )
    return {"from_state": result.from_state, "to_state": result.to_state}


async def handle_create_contract_draft(
    session: AsyncSession,
    ctx: CommandContext,
    payload: dict[str, Any],
) -> dict[str, Any]:
    body = TaskContractBody.model_validate(payload["body"])
    contract = await ContractService().create_draft(
        session,
        uuid.UUID(payload["task_id"]),
        body,
        payload.get("compiled_by", "manual"),
        ctx,
    )
    return {"contract_id": str(contract.id)}


async def handle_update_contract_draft(
    session: AsyncSession,
    _ctx: CommandContext,
    payload: dict[str, Any],
) -> dict[str, Any]:
    body = TaskContractBody.model_validate(payload["body"])
    contract = await ContractService().update_draft(
        session,
        uuid.UUID(payload["contract_id"]),
        body,
    )
    return {"contract_id": str(contract.id)}


async def handle_issue_contract(
    session: AsyncSession,
    ctx: CommandContext,
    payload: dict[str, Any],
) -> dict[str, Any]:
    contract = await ContractService().issue(
        session,
        uuid.UUID(payload["contract_id"]),
        ctx,
    )
    return {"contract_id": str(contract.id)}


async def handle_request_approval(
    session: AsyncSession,
    ctx: CommandContext,
    payload: dict[str, Any],
) -> dict[str, Any]:
    cycle_id = uuid.UUID(payload["cycle_id"])
    cycle = await session.get(DeliveryCycle, cycle_id)
    if cycle is None:
        raise DomainError(code="NOT_FOUND", message="Delivery cycle not found")
    policy = await ensure_policy_version(session)
    approval = await ApprovalService(policy=policy).request(
        session,
        cycle.project_id,
        cycle_id,
        ApprovalType(payload["approval_type"]),
        payload["subject_type"],
        uuid.UUID(payload["subject_id"]),
        int(payload["subject_version"]),
        payload["subject_hash"],
        ctx,
        policy=policy,
    )
    return {
        "approval_id": str(approval.id),
        "key": approval.key,
        "status": approval.status.value,
    }


async def handle_approval_decide(
    session: AsyncSession,
    ctx: CommandContext,
    payload: dict[str, Any],
) -> dict[str, Any]:
    approval = await ApprovalService().decide(
        session,
        uuid.UUID(payload["approval_id"]),
        ApprovalStatus(payload["decision"]),
        payload.get("note"),
        ctx,
    )
    if approval.approval_type == ApprovalType.SCOPE and approval.subject_type == "scope_set":
        from core.product_model.specifications.scope import ScopeService

        scope_svc = ScopeService()
        if approval.status == ApprovalStatus.APPROVED:
            await scope_svc.on_scope_approved(session, approval.subject_id, approval.id, ctx)
        elif approval.status == ApprovalStatus.REJECTED:
            await scope_svc.on_scope_rejected(session, approval.subject_id, approval.id, ctx)
    elif (
        approval.approval_type == ApprovalType.ARCHITECTURE
        and approval.subject_type == "architecture"
    ):
        from core.planning.architecture.service import ArchitectureService

        if approval.status == ApprovalStatus.APPROVED:
            await ArchitectureService().on_approved(session, approval.subject_id, approval.id, ctx)
    elif (
        approval.approval_type == ApprovalType.IMPLEMENTATION_SPEC
        and approval.subject_type == "implementation_spec"
    ):
        from core.planning.implementation_specs.service import ImplementationSpecService

        if approval.status == ApprovalStatus.APPROVED:
            await ImplementationSpecService().on_approved(
                session, approval.subject_id, approval.id, ctx
            )
            if approval.delivery_cycle_id is not None:
                from core.product_model.changes.completion import FeatureChangeCompletionService
                from core.product_model.defects.completion import BugFixCompletionService

                await FeatureChangeCompletionService().maybe_start_task_plan_after_impl_approval(
                    session, approval.delivery_cycle_id, ctx
                )
                await BugFixCompletionService().maybe_start_task_plan_after_repair_impl_approval(
                    session, approval.delivery_cycle_id, ctx
                )
    elif (
        approval.approval_type == ApprovalType.FINDING_WAIVER
        and approval.subject_type == "FINDING"
        and approval.status == ApprovalStatus.APPROVED
    ):
        from core.assurance.findings import FindingService

        await FindingService().apply_waiver(session, approval.subject_id, approval.id, ctx)
    elif (
        approval.approval_type == ApprovalType.SPEC_DELTA
        and approval.status == ApprovalStatus.APPROVED
    ):
        from core.product_model.changes.completion import FeatureChangeCompletionService
        from core.product_model.changes.service import ChangeRequestService

        await ChangeRequestService().on_spec_delta_approved(
            session, approval.subject_id, approval.id, ctx
        )
        if approval.delivery_cycle_id is not None:
            await FeatureChangeCompletionService().maybe_start_impact_after_spec_approval(
                session, approval.delivery_cycle_id, ctx
            )
    return {"approval_id": str(approval.id)}


async def handle_task_add_dependency(
    session: AsyncSession,
    _ctx: CommandContext,
    payload: dict[str, Any],
) -> dict[str, Any]:
    await TaskService().add_dependency(
        session,
        uuid.UUID(payload["task_id"]),
        uuid.UUID(payload["depends_on_task_id"]),
    )
    return {}


async def handle_register_repository(
    session: AsyncSession,
    ctx: CommandContext,
    payload: dict[str, Any],
) -> dict[str, Any]:
    from core.domain.enums import RepositoryProvider
    from core.repositories.remote import RemoteRepositoryService

    provider = RepositoryProvider(payload["provider"])
    await RemoteRepositoryService().validate_registration(
        session,
        provider,
        payload["remote_url"],
        payload.get("credential_ref", "none:"),
    )
    repo = await RepositoryService().register_external(
        session,
        uuid.UUID(payload["project_id"]),
        payload["name"],
        provider,
        payload["remote_url"],
        payload.get("default_branch") or "main",
        payload.get("credential_ref", "none:"),
        ctx,
    )
    return {"repository_id": str(repo.id)}


async def handle_create_integration_candidate(
    session: AsyncSession,
    ctx: CommandContext,
    payload: dict[str, Any],
) -> dict[str, Any]:
    from core.integration.service import IntegrationService

    ic = await IntegrationService().create(session, uuid.UUID(payload["cycle_id"]), ctx)
    return {"integration_candidate_id": str(ic.id), "key": ic.key, "status": ic.status.value}


async def handle_retry_materialization(
    session: AsyncSession,
    ctx: CommandContext,
    payload: dict[str, Any],
) -> dict[str, Any]:
    from core.repositories.materialization import RepositoryMaterializationService

    repo = await RepositoryMaterializationService().retry_materialization(
        session,
        uuid.UUID(payload["repository_id"]),
        ctx,
    )
    return {"repository_id": str(repo.id), "status": repo.status.value}
