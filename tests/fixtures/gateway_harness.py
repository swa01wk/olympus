from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from core.commands.context import CommandContext
from core.domain.actors.models import Actor
from core.domain.delivery_cycles.models import DeliveryCycle
from core.domain.enums import (
    ActorKind,
    ActorRole,
    DeliveryCycleType,
    ExecutionStatus,
    LeaseState,
    TaskContractStatus,
    TaskOrigin,
    TaskStatus,
    WorkType,
)
from core.domain.executions.models import Execution, ExecutionLease, ExecutionSnapshot
from core.domain.projects.models import Project
from core.domain.repositories.models import Repository
from core.domain.task_contracts.models import TaskContract
from core.domain.task_contracts.schemas import TaskContractBody
from core.domain.tasks.models import Task
from core.domain.tasks.service import TaskService
from core.policy.policy_service import ensure_policy_version
from core.tools.tokens import (
    default_token_expiry,
    issue_token,
    persist_token,
    revoke_tokens_for_execution,
)
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession


@dataclass(frozen=True)
class GatewayExecutionBundle:
    actor: Actor
    agent: Actor
    project: Project
    cycle: DeliveryCycle
    task: Task
    contract: TaskContract
    execution: Execution
    lease: ExecutionLease
    token: str
    repository: Repository
    ctx: CommandContext


async def seed_gateway_execution(
    session: AsyncSession,
    *,
    repository: Repository,
    base_commit: str,
    key_prefix: str = "gw",
    existing_task: Task | None = None,
    existing_contract: TaskContract | None = None,
    existing_cycle: DeliveryCycle | None = None,
    allowed_tools: tuple[str, ...] = (
        "repo.read",
        "repo.write",
        "git.commit",
        "git.status",
    ),
    allowed_scope: list[str] | None = None,
    agent_profile: str = "forge.implementation",
) -> GatewayExecutionBundle:
    from core.runtime.profiles.forge import register_forge_profile

    register_forge_profile()
    policy_svc = await ensure_policy_version(session)
    policy_version = policy_svc.version_row
    assert policy_version is not None
    actor = Actor(kind=ActorKind.SYSTEM, name=f"{key_prefix}-sys", roles=[ActorRole.SYSTEM.value])
    agent = Actor(kind=ActorKind.AGENT, name=f"{key_prefix}-agent", roles=[ActorRole.SYSTEM.value])
    session.add(actor)
    session.add(agent)
    await session.flush()
    project = await session.get(Project, repository.project_id)
    if project is None:
        raise RuntimeError("repository project_id missing")
    ctx = CommandContext(actor=actor, correlation_id=f"{key_prefix}-corr")
    if existing_contract is not None and existing_task is not None and existing_cycle is not None:
        cycle = existing_cycle
        task = existing_task
        contract = existing_contract
        body = TaskContractBody.model_validate(contract.body)
    else:
        cycle = DeliveryCycle(
            project_id=project.id,
            key=f"C-{key_prefix}",
            type=DeliveryCycleType.FEATURE_CHANGE,
            objective="gateway test",
            state="DEVELOPMENT",
            state_version=0,
            opened_by_actor_id=actor.id,
        )
        session.add(cycle)
        await session.flush()
        task = await TaskService().create_task(
            session,
            cycle.id,
            f"Task {key_prefix}",
            WorkType.CODE_CHANGE,
            TaskOrigin.CONTROL_PLANE,
            ctx,
        )
        body = TaskContractBody(
            objective="implement",
            work_type=WorkType.CODE_CHANGE,
            repository_id=repository.id,
            allowed_scope=allowed_scope or ["**"],
            allowed_actions=list(allowed_tools),
            inputs=[],
            executor_kind="AGENT_RUNTIME",
            agent_profile=agent_profile,
        )
        contract = TaskContract(
            task_id=task.id,
            key="v1",
            version=1,
            status=TaskContractStatus.ISSUED,
            body=body.model_dump(mode="json"),
            content_hash=f"hash-{key_prefix}",
            compiled_by="test",
        )
        session.add(contract)
        await session.flush()
        task.current_contract_id = contract.id
        task.status = TaskStatus.READY
    terminal_exec = {
        ExecutionStatus.COMPLETED,
        ExecutionStatus.FAILED,
        ExecutionStatus.CANCELLED,
    }
    attempt_number = 1
    if existing_task is not None:
        open_rows = (
            await session.execute(
                select(Execution).where(
                    Execution.task_id == task.id,
                    Execution.status.not_in(tuple(terminal_exec)),
                )
            )
        ).scalars()
        now = datetime.now(UTC)
        for row in open_rows:
            row.status = ExecutionStatus.FAILED
            row.finished_at = now
        if open_rows:
            await session.flush()
        latest = (
            await session.execute(
                select(Execution)
                .where(Execution.task_id == task.id)
                .order_by(Execution.attempt_number.desc())
                .limit(1)
            )
        ).scalar_one_or_none()
        if latest is not None:
            attempt_number = latest.attempt_number + 1
    execution = Execution(
        key=f"EX-{key_prefix}",
        task_id=task.id,
        delivery_cycle_id=cycle.id,
        task_contract_id=contract.id,
        attempt_number=attempt_number,
        status=ExecutionStatus.STARTED,
        executor_kind="AGENT_RUNTIME",
        agent_profile=agent_profile,
        started_at=datetime.now(UTC),
    )
    session.add(execution)
    await session.flush()
    snapshot = ExecutionSnapshot(
        execution_id=execution.id,
        task_contract_id=contract.id,
        task_contract_version=1,
        task_contract_hash=contract.content_hash,
        base_commit=base_commit,
        repository_id=repository.id,
        policy_version_id=policy_version.id,
        risk_tier="R1",
        content={"contract": body.model_dump(mode="json")},
        snapshot_hash=f"snap-{key_prefix}",
    )
    session.add(snapshot)
    await session.flush()
    execution.snapshot_id = snapshot.id
    lease = (
        await session.execute(
            select(ExecutionLease).where(
                ExecutionLease.execution_id == execution.id,
                ExecutionLease.state == LeaseState.ACTIVE,
            )
        )
    ).scalar_one_or_none()
    if lease is None:
        lease = ExecutionLease(
            execution_id=execution.id,
            worker_id="test-worker",
            state=LeaseState.ACTIVE,
            acquired_at=datetime.now(UTC),
            expires_at=datetime.now(UTC) + timedelta(hours=1),
            heartbeat_at=datetime.now(UTC),
        )
        session.add(lease)
        await session.flush()
    await revoke_tokens_for_execution(session, execution.id)
    raw, token_hash = issue_token(execution.id, lease.id, default_token_expiry(lease))
    await persist_token(session, execution.id, lease.id, token_hash, default_token_expiry(lease))
    return GatewayExecutionBundle(
        actor=actor,
        agent=agent,
        project=project,
        cycle=cycle,
        task=task,
        contract=contract,
        execution=execution,
        lease=lease,
        token=raw,
        repository=repository,
        ctx=ctx,
    )
