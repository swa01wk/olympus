"""Deterministic integration.merge executor."""

from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.assurance.findings import FindingService
from core.commands.context import CommandContext
from core.domain.candidate_commits.models import CandidateCommit
from core.domain.delivery_cycles.models import DeliveryCycle
from core.domain.events.append import append_domain_event
from core.domain.exceptions import DomainError
from core.domain.execution_workspaces.models import ExecutionWorkspace
from core.domain.repositories.models import Repository, RepositoryWorkspace
from core.execution.artifacts import ArtifactStore
from core.execution.executors.base import ExecutionContext, ExecutorOutcome
from core.execution.worktrees.git import GitCli
from core.execution.worktrees.manager import WorktreeManager
from core.integration.checks import run_integration_checks
from core.integration.enums import FindingSeverity, FindingSource, ICStatus
from core.integration.models import IntegrationCandidate, IntegrationCandidateCommit
from core.integration.remediation import create_merge_conflict_remediation
from core.repositories.git_inspect import GitInspector
from core.repositories.workspace_locator import WorkspaceLocator


async def run_integration_merge(
    session: AsyncSession,
    ctx: ExecutionContext,
    command_ctx: CommandContext,
) -> ExecutorOutcome:
    ic = await _load_ic(session, ctx)
    if ic.status == ICStatus.CREATED:
        ic.status = ICStatus.INTEGRATING
        await session.flush()

    cycle = await session.get(DeliveryCycle, ic.delivery_cycle_id)
    execution = ctx.execution
    if cycle is None:
        return ExecutorOutcome(status="FAILED", error_code="CYCLE_MISSING", error_message="cycle")

    repo = await session.get(Repository, ic.repository_id)
    canonical_ws = await session.get(RepositoryWorkspace, repo.workspace_id if repo else None)
    if repo is None or canonical_ws is None:
        return ExecutorOutcome(status="FAILED", error_code="REPO_MISSING", error_message="repo")

    locator = WorkspaceLocator()
    git_dir = locator.resolve(canonical_ws.storage_backend, canonical_ws.logical_location)
    inspector = GitInspector()

    if cycle.base_sha and not inspector.is_ancestor(git_dir, cycle.base_sha, ic.base_sha):
        await _fail_ic(
            session,
            ic,
            cycle,
            command_ctx,
            category="ANCESTRY_INVALID",
            title="Cycle base is not an ancestor of integration base",
            detail={"cycle_base_sha": cycle.base_sha, "ic_base_sha": ic.base_sha},
            execution_id=execution.id,
        )
        return ExecutorOutcome(status="FAILED", error_code="ANCESTRY_INVALID", error_message="base")

    commits = await _ordered_included_commits(session, ic.id)
    for cc in commits:
        if not inspector.is_ancestor(git_dir, cycle.base_sha or ic.base_sha, cc.sha):
            await _fail_ic(
                session,
                ic,
                cycle,
                command_ctx,
                category="ANCESTRY_INVALID",
                title="Candidate commit does not descend from cycle base",
                detail={"candidate_sha": cc.sha, "cycle_base_sha": cycle.base_sha},
                execution_id=execution.id,
            )
            return ExecutorOutcome(
                status="FAILED", error_code="ANCESTRY_INVALID", error_message="candidate"
            )

    wt_mgr = WorktreeManager()
    existing = await session.execute(
        select(ExecutionWorkspace).where(ExecutionWorkspace.execution_id == execution.id)
    )
    workspace = existing.scalar_one_or_none()
    if workspace is None:
        workspace = await wt_mgr.create(
            session,
            execution,
            ic.repository_id,
            ic.base_sha,
            actor_id=command_ctx.actor.id,
            correlation_id=command_ctx.correlation_id,
            project_id=cycle.project_id,
            branch_name=ic.integration_branch,
        )
    wt_path = locator.resolve(canonical_ws.storage_backend, workspace.logical_location)
    git = GitCli()
    head = ic.base_sha
    conflict_files: list[str] = []
    conflict_tasks: list[str] = []
    for link in await _ordered_links(session, ic.id):
        if not link.included:
            continue
        candidate_commit = await session.get(CandidateCommit, link.candidate_commit_id)
        if candidate_commit is None:
            continue
        if inspector.is_ancestor(git_dir, candidate_commit.sha, head):
            continue
        merge = git.run(
            GitCli.hook_disabled_config_args()
            + [
                "merge",
                "--no-ff",
                "--no-edit",
                "-m",
                f"Olympus Integration: merge {candidate_commit.sha[:8]}",
                candidate_commit.sha,
            ],
            cwd=wt_path,
            check=False,
        )
        if merge.returncode != 0:
            git.run(["merge", "--abort"], cwd=wt_path, check=False)
            conflict_files = _parse_conflict_files(merge.stderr + merge.stdout)
            task_key = (
                ic.ordering[link.position]["task_key"] if link.position < len(ic.ordering) else ""
            )
            conflict_tasks.append(task_key)
            ic.status = ICStatus.CONFLICT
            await session.flush()
            finding = await FindingService().create(
                session,
                project_id=cycle.project_id,
                delivery_cycle_id=cycle.id,
                source=FindingSource.INTEGRATION,
                category="MERGE_CONFLICT",
                severity=FindingSeverity.BLOCKER,
                title=f"Merge conflict integrating {ic.key}",
                detail={
                    "conflicting_files": conflict_files,
                    "task_keys": conflict_tasks,
                    "candidate_sha": candidate_commit.sha,
                },
                ctx=command_ctx,
                integration_candidate_id=ic.id,
                producer_execution_id=execution.id,
            )
            await create_merge_conflict_remediation(
                session, ic, finding, conflict_files, command_ctx
            )
            await append_domain_event(
                session,
                aggregate_type="integration_candidate",
                aggregate_id=ic.id,
                event_type="integration.conflict",
                payload={"finding_id": str(finding.id)},
                actor_id=command_ctx.actor.id,
                correlation_id=command_ctx.correlation_id,
                project_id=cycle.project_id,
                delivery_cycle_id=cycle.id,
            )
            return ExecutorOutcome(
                status="FAILED",
                error_code="MERGE_CONFLICT",
                error_message="merge conflict",
                output={"finding_id": str(finding.id)},
            )
        head = git.run(["rev-parse", "HEAD"], cwd=wt_path, check=True).stdout.strip()

    head = git.run(["rev-parse", "HEAD"], cwd=wt_path, check=True).stdout.strip()
    git.run(
        ["fetch", str(wt_path.resolve()), f"+HEAD:refs/heads/{ic.integration_branch}"],
        git_dir=git_dir,
        check=False,
    )

    checks = run_integration_checks(wt_path)
    artifacts = ArtifactStore()
    artifact = await artifacts.put(
        session,
        project_id=cycle.project_id,
        delivery_cycle_id=cycle.id,
        execution_id=execution.id,
        kind="INTEGRATION_CHECKS",
        schema_name="IntegrationChecks",
        schema_version="1",
        content={
            "ok": checks.ok,
            "compileall_rc": checks.compileall_rc,
            "collect_rc": checks.collect_rc,
            "pytest_rc": checks.pytest_rc,
            "output": checks.output[:50000],
        },
    )
    ic.checks_artifact_id = artifact.id
    if not checks.ok:
        await _fail_ic(
            session,
            ic,
            cycle,
            command_ctx,
            category="INTEGRATION_CHECK_FAILED",
            title="Integration checks failed",
            detail={"artifact_id": str(artifact.id)},
            execution_id=execution.id,
        )
        return ExecutorOutcome(
            status="FAILED",
            error_code="INTEGRATION_CHECK_FAILED",
            error_message="checks failed",
        )

    ic.integrated_sha = head
    ic.status = ICStatus.VALIDATING
    await session.flush()
    return ExecutorOutcome(
        status="OUTPUT_PRODUCED",
        output={
            "integration_result": {
                "integration_candidate_id": str(ic.id),
                "integrated_sha": head,
                "checks_artifact_id": str(artifact.id),
            }
        },
    )


async def _load_ic(session: AsyncSession, ctx: ExecutionContext) -> IntegrationCandidate:
    ic_id: uuid.UUID | None = None
    for ref in ctx.contract.inputs:
        if ref.ref_type == "INTEGRATION_CANDIDATE":
            ic_id = ref.ref_id
            break
    if ic_id is None:
        raise DomainError(code="IC_REF_MISSING", message="Missing INTEGRATION_CANDIDATE input")
    ic = await session.get(IntegrationCandidate, ic_id)
    if ic is None:
        raise DomainError(code="NOT_FOUND", message="Integration candidate not found")
    return ic


async def _ordered_links(
    session: AsyncSession, ic_id: uuid.UUID
) -> list[IntegrationCandidateCommit]:
    result = await session.execute(
        select(IntegrationCandidateCommit)
        .where(IntegrationCandidateCommit.integration_candidate_id == ic_id)
        .order_by(IntegrationCandidateCommit.position)
    )
    return list(result.scalars())


async def _ordered_included_commits(
    session: AsyncSession, ic_id: uuid.UUID
) -> list[CandidateCommit]:
    out: list[CandidateCommit] = []
    for link in await _ordered_links(session, ic_id):
        if not link.included:
            continue
        cc = await session.get(CandidateCommit, link.candidate_commit_id)
        if cc is not None:
            out.append(cc)
    return out


async def _fail_ic(
    session: AsyncSession,
    ic: IntegrationCandidate,
    cycle: DeliveryCycle,
    ctx: CommandContext,
    *,
    category: str,
    title: str,
    detail: dict[str, object],
    execution_id: uuid.UUID,
) -> None:
    ic.status = ICStatus.FAILED
    await session.flush()
    await FindingService().create(
        session,
        project_id=cycle.project_id,
        delivery_cycle_id=cycle.id,
        source=FindingSource.INTEGRATION,
        category=category,
        severity=FindingSeverity.BLOCKER,
        title=title,
        detail=detail,
        ctx=ctx,
        integration_candidate_id=ic.id,
        producer_execution_id=execution_id,
    )
    await append_domain_event(
        session,
        aggregate_type="integration_candidate",
        aggregate_id=ic.id,
        event_type="integration.failed",
        payload={"category": category},
        actor_id=ctx.actor.id,
        correlation_id=ctx.correlation_id,
        project_id=cycle.project_id,
        delivery_cycle_id=cycle.id,
    )


def _parse_conflict_files(text: str) -> list[str]:
    files: list[str] = []
    for line in text.splitlines():
        if line.startswith("CONFLICT") and "merge" in line:
            parts = line.split()
            if parts:
                files.append(parts[-1])
    return files
