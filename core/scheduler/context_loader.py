from __future__ import annotations

import uuid

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from core.domain.approvals.models import Approval
from core.domain.delivery_cycles.models import DeliveryCycle
from core.domain.enums import ApprovalStatus, ExecutionStatus, TaskContractStatus, TaskStatus
from core.domain.executions.models import Execution
from core.domain.repositories.models import Repository
from core.domain.task_contracts.models import TaskContract
from core.domain.task_contracts.schemas import VersionedRef, parse_task_contract_body
from core.domain.tasks.models import Task, TaskDependency
from core.execution.snapshots.base_commit import BaseCommitResolver
from core.scheduler.refs import RefResolverRegistry
from core.scheduler.types import EligibilityContext, TaskView


async def load_task_view(session: AsyncSession, task: Task) -> TaskView:
    body_repo: uuid.UUID | None = None
    base_policy = "NONE"
    if task.current_contract_id:
        contract = await session.get(TaskContract, task.current_contract_id)
        if contract:
            body = parse_task_contract_body(contract.body)
            body_repo = body.repository_id
            base_policy = body.base_policy
    cycle = await session.get(DeliveryCycle, task.delivery_cycle_id)
    repository_id: uuid.UUID | None
    if body_repo is not None:
        repository_id = body_repo
    elif base_policy != "NONE" and cycle is not None:
        repository_id = cycle.repository_id
    else:
        repository_id = None
    return TaskView(
        id=task.id,
        key=task.key,
        status=task.status,
        delivery_cycle_id=task.delivery_cycle_id,
        current_contract_id=task.current_contract_id,
        allow_parallel_executions=task.allow_parallel_executions,
        max_attempts=task.max_attempts,
        work_type=task.work_type.value,
        origin=task.origin.value,
        repository_id=repository_id,
    )


async def load_eligibility_context(
    session: AsyncSession,
    task: Task,
    *,
    ref_registry: RefResolverRegistry,
    base_resolver: BaseCommitResolver,
) -> EligibilityContext:
    deps = await session.execute(select(TaskDependency).where(TaskDependency.task_id == task.id))
    dependency_statuses: dict[uuid.UUID, TaskStatus] = {}
    dependency_keys: dict[uuid.UUID, str] = {}
    for dep in deps.scalars():
        other = await session.get(Task, dep.depends_on_task_id)
        if other:
            dependency_statuses[other.id] = other.status
            dependency_keys[other.id] = other.key

    issued_contract_id: uuid.UUID | None = None
    issued_version: int | None = None
    contract_inputs: tuple[VersionedRef, ...] = ()
    required_approvals: tuple[uuid.UUID, ...] = ()
    if task.current_contract_id:
        contract = await session.get(TaskContract, task.current_contract_id)
        if contract and contract.status == TaskContractStatus.ISSUED:
            issued_contract_id = contract.id
            issued_version = contract.version
            body = parse_task_contract_body(contract.body)
            contract_inputs = tuple(body.inputs)
            required_approvals = tuple(body.required_approvals)

    approval_statuses: dict[uuid.UUID, ApprovalStatus] = {}
    for approval_id in required_approvals:
        row = await session.get(Approval, approval_id)
        if row:
            approval_statuses[approval_id] = row.status

    active = await session.execute(
        select(Execution).where(
            Execution.task_id == task.id,
            Execution.status.in_(
                [
                    ExecutionStatus.QUEUED,
                    ExecutionStatus.LEASED,
                    ExecutionStatus.STARTED,
                    ExecutionStatus.OUTPUT_PRODUCED,
                    ExecutionStatus.VALIDATING,
                    ExecutionStatus.COMMITTED,
                ]
            ),
        )
    )
    conflicting = active.scalar_one_or_none()

    count_result = await session.execute(
        select(func.count()).select_from(Execution).where(Execution.task_id == task.id)
    )
    attempt_count = int(count_result.scalar_one())

    ref_exists, ref_current = await ref_registry.resolve_checks(session, list(contract_inputs))

    repository_status = None
    base_commit_available: bool | None = None
    base_resolver_available = True
    view = await load_task_view(session, task)
    if view.repository_id:
        repo = await session.get(Repository, view.repository_id)
        if repo:
            repository_status = repo.status
        if task.current_contract_id:
            contract = await session.get(TaskContract, task.current_contract_id)
            if contract:
                body = parse_task_contract_body(contract.body)
                try:
                    resolution = await base_resolver.resolve(session, body, task)
                    base_commit_available = resolution.commit_available
                except ValueError as exc:
                    if str(exc) == "BASE_RESOLVER_UNAVAILABLE":
                        base_resolver_available = False
                    else:
                        base_commit_available = False

    return EligibilityContext(
        dependency_statuses=dependency_statuses,
        dependency_keys=dependency_keys,
        issued_contract_id=issued_contract_id,
        issued_contract_version=issued_version,
        contract_inputs=contract_inputs,
        required_approvals=required_approvals,
        approval_statuses=approval_statuses,
        policy_blocked_rules=(),
        conflicting_execution_key=conflicting.key if conflicting else None,
        attempt_count=attempt_count,
        ref_exists=ref_exists,
        ref_current=ref_current,
        repository_status=repository_status,
        base_commit_available=base_commit_available,
        base_resolver_available=base_resolver_available,
    )
