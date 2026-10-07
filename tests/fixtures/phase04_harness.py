from __future__ import annotations

import uuid
from dataclasses import dataclass

from core.commands.context import CommandContext
from core.domain.enums import TaskContractStatus, TaskOrigin, TaskStatus, WorkType
from core.domain.projects.models import Project
from core.domain.repositories.models import Repository
from core.domain.task_contracts.models import TaskContract
from core.domain.task_contracts.schemas import TaskContractBody
from core.domain.tasks.service import TaskService
from core.repositories.materialization import RepositoryMaterializationService
from core.repositories.service import RepositoryService
from sqlalchemy.ext.asyncio import AsyncSession
from tests.fixtures.gateway_harness import GatewayExecutionBundle, seed_gateway_execution


@dataclass(frozen=True)
class CodeChangeFixture:
    project: Project
    repository: Repository
    base_sha: str
    task_id: uuid.UUID
    cycle_id: uuid.UUID


async def seed_greenfield_repository(
    session: AsyncSession,
    ctx: CommandContext,
    *,
    project_key: str = "p04",
) -> tuple[Project, Repository, str]:
    project = Project(key=project_key, name=f"Phase04 {project_key}")
    session.add(project)
    await session.flush()
    repo = await RepositoryService().declare_managed(session, project.id, ctx)
    await RepositoryMaterializationService().provision_managed(session, repo.id, ctx)
    await session.refresh(repo)
    assert repo.canonical_commit
    return project, repo, repo.canonical_commit


async def seed_code_change_task(
    session: AsyncSession,
    ctx: CommandContext,
    project: Project,
    repository: Repository,
    base_sha: str,
    *,
    allowed_scope: list[str] | None = None,
    allowed_actions: list[str] | None = None,
) -> CodeChangeFixture:
    from core.domain.delivery_cycles.models import DeliveryCycle
    from core.domain.enums import DeliveryCycleType

    cycle = DeliveryCycle(
        project_id=project.id,
        key=f"C-{project.key}",
        type=DeliveryCycleType.FEATURE_CHANGE,
        objective="code change",
        state="DEVELOPMENT",
        state_version=0,
        opened_by_actor_id=ctx.actor.id,
        repository_id=repository.id,
    )
    session.add(cycle)
    await session.flush()
    task = await TaskService().create_task(
        session,
        cycle.id,
        "Implement",
        WorkType.CODE_CHANGE,
        TaskOrigin.CONTROL_PLANE,
        ctx,
    )
    scope = allowed_scope or ["**"]
    actions = allowed_actions or [
        "repo.read",
        "repo.write",
        "git.status",
        "git.diff",
        "git.commit",
        "test.run",
        "shell.run",
    ]
    body = TaskContractBody(
        objective="implement feature",
        work_type=WorkType.CODE_CHANGE,
        repository_id=repository.id,
        base_policy="EXPLICIT_SHA",
        base_commit=base_sha,
        allowed_scope=scope,
        allowed_actions=actions,
        required_outputs=["candidate_commit"],
        inputs=[],
        executor_kind="AGENT_RUNTIME",
        agent_profile="forge.implementation",
    )
    contract = TaskContract(
        task_id=task.id,
        key="v1",
        version=1,
        status=TaskContractStatus.ISSUED,
        body=body.model_dump(mode="json"),
        content_hash=f"hash-{project.key}",
        compiled_by="test",
    )
    session.add(contract)
    await session.flush()
    task.current_contract_id = contract.id
    task.status = TaskStatus.READY
    await session.flush()
    return CodeChangeFixture(
        project=project,
        repository=repository,
        base_sha=base_sha,
        task_id=task.id,
        cycle_id=cycle.id,
    )


async def seed_execution_with_worktree(
    session: AsyncSession,
    ctx: CommandContext,
    fixture: CodeChangeFixture,
    *,
    key_prefix: str = "api",
) -> GatewayExecutionBundle:
    from core.domain.delivery_cycles.models import DeliveryCycle
    from core.domain.task_contracts.models import TaskContract
    from core.domain.tasks.models import Task

    task = await session.get(Task, fixture.task_id)
    assert task is not None and task.current_contract_id is not None
    contract = await session.get(TaskContract, task.current_contract_id)
    cycle = await session.get(DeliveryCycle, fixture.cycle_id)
    assert contract is not None and cycle is not None
    bundle = await seed_gateway_execution(
        session,
        repository=fixture.repository,
        base_commit=fixture.base_sha,
        key_prefix=key_prefix,
        existing_task=task,
        existing_contract=contract,
        existing_cycle=cycle,
    )
    from core.execution.worktrees.manager import WorktreeManager

    await WorktreeManager().create(
        session,
        bundle.execution,
        fixture.repository.id,
        fixture.base_sha,
        actor_id=ctx.actor.id,
        correlation_id=ctx.correlation_id,
        project_id=fixture.project.id,
    )
    return bundle
