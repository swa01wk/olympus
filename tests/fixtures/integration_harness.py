"""Deterministic helpers for Phase 08 integration / git acceptance tests."""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from core.commands.context import CommandContext
from core.domain.canonical_json import sha256_hex
from core.domain.delivery_cycles.models import DeliveryCycle
from core.domain.enums import (
    DeliveryCycleType,
    ExecutionStatus,
    TaskContractStatus,
    TaskOrigin,
    TaskStatus,
    WorkType,
)
from core.domain.projects.models import Project
from core.domain.repositories.models import Repository, RepositoryWorkspace
from core.domain.task_contracts.models import TaskContract
from core.domain.task_contracts.schemas import TaskContractBody
from core.domain.tasks.models import Task
from core.domain.tasks.service import TaskService
from core.execution.worker import ExecutionWorker
from core.integration.enums import ICStatus
from core.integration.models import IntegrationCandidate
from core.integration.service import IntegrationService
from core.intelligence.code_index.canonical_service import CanonicalIndexService
from core.repositories.workspace_locator import WorkspaceLocator
from core.tools.gateway import ToolGateway
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from tests.fixtures.gateway_harness import GatewayExecutionBundle, seed_gateway_execution
from tests.fixtures.phase04_harness import seed_greenfield_repository


@dataclass(frozen=True)
class IntegrationFixture:
    project: Project
    repository: Repository
    cycle: DeliveryCycle
    base_sha: str


@dataclass(frozen=True)
class CodeTaskBundle:
    fixture: IntegrationFixture
    task: Task
    contract: TaskContract
    execution_bundle: GatewayExecutionBundle


@dataclass(frozen=True)
class ProductLineageFixture:
    feature_id: uuid.UUID
    capability_id: uuid.UUID
    feature_spec_id: uuid.UUID
    implementation_spec_id: uuid.UUID
    ac_id: uuid.UUID
    ac_lineage_key: str


async def seed_integration_fixture(
    session: AsyncSession,
    ctx: CommandContext,
    *,
    project_key: str = "ic-harness",
) -> IntegrationFixture:
    project, repo, base_sha = await seed_greenfield_repository(
        session, ctx, project_key=project_key
    )
    cycle = DeliveryCycle(
        project_id=project.id,
        key=f"C-{project_key}",
        type=DeliveryCycleType.FEATURE_CHANGE,
        objective="integration acceptance",
        state="DEVELOPMENT",
        state_version=0,
        opened_by_actor_id=ctx.actor.id,
        repository_id=repo.id,
        base_sha=base_sha,
    )
    session.add(cycle)
    await session.flush()
    await CanonicalIndexService().promote_repository_snapshot(session, repo.id, base_sha, ctx)
    return IntegrationFixture(project=project, repository=repo, cycle=cycle, base_sha=base_sha)


async def git_dir_for_repository(session: AsyncSession, repository_id: uuid.UUID) -> Path:
    repo = await session.get(Repository, repository_id)
    assert repo is not None and repo.workspace_id is not None
    ws = await session.get(RepositoryWorkspace, repo.workspace_id)
    assert ws is not None
    return WorkspaceLocator().resolve(ws.storage_backend, ws.logical_location)


async def add_implementation_code_task(
    session: AsyncSession,
    ctx: CommandContext,
    fixture: IntegrationFixture,
    *,
    title: str,
    key_prefix: str,
    base_sha: str | None = None,
) -> CodeTaskBundle:
    base = base_sha or fixture.base_sha
    task = await TaskService().create_task(
        session,
        fixture.cycle.id,
        title,
        WorkType.CODE_CHANGE,
        TaskOrigin.IMPLEMENTATION_PLAN,
        ctx,
    )
    scope = ["**"]
    actions = [
        "repo.read",
        "repo.write",
        "git.status",
        "git.diff",
        "git.commit",
        "test.run",
        "shell.run",
    ]
    body = TaskContractBody(
        objective=title,
        work_type=WorkType.CODE_CHANGE,
        repository_id=fixture.repository.id,
        base_policy="EXPLICIT_SHA",
        base_commit=base,
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
        content_hash=f"hash-{key_prefix}",
        compiled_by="test",
    )
    session.add(contract)
    await session.flush()
    task.current_contract_id = contract.id
    task.status = TaskStatus.READY
    await session.flush()
    bundle = await seed_gateway_execution(
        session,
        repository=fixture.repository,
        base_commit=base,
        key_prefix=key_prefix,
        existing_task=task,
        existing_contract=contract,
        existing_cycle=fixture.cycle,
    )
    from core.execution.worktrees.manager import WorktreeManager

    await WorktreeManager().create(
        session,
        bundle.execution,
        fixture.repository.id,
        base,
        actor_id=ctx.actor.id,
        correlation_id=ctx.correlation_id,
        project_id=fixture.project.id,
    )
    return CodeTaskBundle(
        fixture=fixture,
        task=task,
        contract=contract,
        execution_bundle=bundle,
    )


async def _worktree_path(session: AsyncSession, execution_id: uuid.UUID) -> Path:
    from core.domain.execution_workspaces.models import ExecutionWorkspace

    ws = (
        await session.execute(
            select(ExecutionWorkspace).where(ExecutionWorkspace.execution_id == execution_id)
        )
    ).scalar_one()
    return WorkspaceLocator().resolve("LOCAL_FILESYSTEM", ws.logical_location)


async def commit_files_in_worktree(
    session: AsyncSession,
    ctx: CommandContext,
    bundle: CodeTaskBundle,
    files: dict[str, str],
    *,
    message: str = "feat: candidate",
    principal_symbols: list[str] | None = None,
    implementation_result: dict[str, Any] | None = None,
) -> str:
    wt = await _worktree_path(session, bundle.execution_bundle.execution.id)
    for rel, content in files.items():
        path = wt / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
    gateway = ToolGateway(session)
    branch = f"olympus/{bundle.execution_bundle.execution.key}"
    params: dict[str, object] = {"branch": branch, "message": message}
    if principal_symbols:
        params["principal_symbols"] = principal_symbols
    result = await gateway.handle(bundle.execution_bundle.token, "git.commit", params)
    assert result.status == "SUCCEEDED", result.denial_reasons
    from core.domain.candidate_commits.models import CandidateCommit

    cc = (
        await session.execute(
            select(CandidateCommit).where(
                CandidateCommit.execution_id == bundle.execution_bundle.execution.id
            )
        )
    ).scalar_one()
    bundle.task.status = TaskStatus.COMPLETED
    exec_row = bundle.execution_bundle.execution
    exec_row.status = ExecutionStatus.COMPLETED
    if implementation_result is not None:
        exec_row.output = implementation_result
    await session.flush()
    with session.no_autoflush:
        await CanonicalIndexService().build_candidate(session, exec_row.id, ctx)
    await session.flush()
    from core.domain.tasks.models import TaskDependency
    from core.domain.tasks.service import TaskService

    deps = await session.execute(
        select(TaskDependency).where(TaskDependency.depends_on_task_id == bundle.task.id)
    )
    task_svc = TaskService()
    for dep in deps.scalars():
        await task_svc.on_dependency_completed(session, dep.task_id)
    await session.flush()
    return cc.sha


async def run_worker_until_ic_settled(
    session: AsyncSession,
    ctx: CommandContext,
    ic_id: uuid.UUID,
    *,
    max_rounds: int = 40,
) -> IntegrationCandidate:
    worker = ExecutionWorker(worker_id=f"ic-test-{uuid.uuid4().hex[:8]}")
    terminal = {
        ICStatus.READY,
        ICStatus.CONFLICT,
        ICStatus.FAILED,
        ICStatus.SUPERSEDED,
    }
    ic = await session.get(IntegrationCandidate, ic_id)
    assert ic is not None
    for _ in range(max_rounds):
        await session.refresh(ic)
        if ic.status in terminal:
            return ic
        await worker.run_once(session, ctx)
    await session.refresh(ic)
    return ic


async def create_and_run_integration(
    session: AsyncSession,
    ctx: CommandContext,
    cycle_id: uuid.UUID,
) -> IntegrationCandidate:
    ic = await IntegrationService().create(session, cycle_id, ctx)
    return await run_worker_until_ic_settled(session, ctx, ic.id)


async def attach_product_lineage(
    session: AsyncSession,
    fixture: IntegrationFixture,
    task: Task,
) -> ProductLineageFixture:
    from core.domain.enums import EntityStatus, EvidenceRequirement, ModelOrigin, SpecStatus
    from core.planning.models import ImplementationSpec, TaskSpecRef
    from core.product_model.models import (
        AcceptanceCriterion,
        Capability,
        Feature,
        FeatureSpec,
    )

    cap = Capability(
        project_id=fixture.project.id,
        key="CAP-1",
        name="Tickets",
        description="Ticket capability",
        status=EntityStatus.APPROVED,
        origin=ModelOrigin.GREENFIELD,
    )
    session.add(cap)
    await session.flush()
    feat = Feature(
        project_id=fixture.project.id,
        capability_id=cap.id,
        key="FEAT-1",
        name="Create ticket",
        description="Create ticket feature",
        status=EntityStatus.APPROVED,
        origin=ModelOrigin.GREENFIELD,
    )
    session.add(feat)
    await session.flush()
    fs_body = {"summary": "create ticket", "behavior": "POST /tickets", "rules": []}
    fs = FeatureSpec(
        project_id=fixture.project.id,
        feature_id=feat.id,
        lineage_key="SPEC-FEAT-1",
        version=1,
        status=SpecStatus.APPROVED,
        body=fs_body,
        content_hash=sha256_hex(fs_body),
    )
    session.add(fs)
    await session.flush()
    arch_id = uuid.uuid4()
    impl_body = {
        "summary": "impl",
        "components": ["api"],
        "file_scope": ["src/**", "tests/**"],
    }
    from core.planning.models import Architecture

    arch_body = {"summary": "arch", "components": []}
    session.add(
        Architecture(
            id=arch_id,
            project_id=fixture.project.id,
            lineage_key="ARCH-1",
            version=1,
            status=SpecStatus.APPROVED,
            kind="BASELINE",
            body=arch_body,
            content_hash=sha256_hex(arch_body),
        )
    )
    await session.flush()
    impl = ImplementationSpec(
        project_id=fixture.project.id,
        lineage_key="SPEC-IMPL-1",
        version=1,
        status=SpecStatus.APPROVED,
        kind="FEATURE",
        feature_spec_id=fs.id,
        architecture_id=arch_id,
        body=impl_body,
        content_hash=sha256_hex(impl_body),
    )
    session.add(impl)
    await session.flush()
    ac = AcceptanceCriterion(
        feature_spec_id=fs.id,
        lineage_key="AC-1",
        statement="Ticket can be created",
        mandatory=True,
        evidence_requirement=EvidenceRequirement.EXECUTABLE,
    )
    session.add(ac)
    await session.flush()
    session.add(
        TaskSpecRef(
            task_id=task.id,
            ref_type="IMPLEMENTATION_SPEC",
            ref_id=impl.id,
            ref_version=1,
        )
    )
    session.add(
        TaskSpecRef(
            task_id=task.id,
            ref_type="FEATURE_SPEC",
            ref_id=fs.id,
            ref_version=1,
        )
    )
    task.implementation_spec_id = impl.id
    await session.flush()
    return ProductLineageFixture(
        feature_id=feat.id,
        capability_id=cap.id,
        feature_spec_id=fs.id,
        implementation_spec_id=impl.id,
        ac_id=ac.id,
        ac_lineage_key=ac.lineage_key,
    )


async def default_branch_head(git_dir: Path, branch: str = "main") -> str:
    from core.execution.worktrees.git import GitCli

    return GitCli().run(["rev-parse", branch], git_dir=git_dir, check=True).stdout.strip()
