from __future__ import annotations

import uuid

from sqlalchemy import select

from core.domain.candidate_commits.models import CandidateCommit
from core.domain.enums import WorkType
from core.domain.events.append import append_domain_event
from core.domain.sequences import next_project_key
from core.execution.worktrees.git import GitCli
from core.tools.context import ToolExecutionContext
from core.tools.paths import PathPolicyViolation, assert_write_scope


def _symbol_list(value: object) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(x) for x in value]


async def git_diff(ctx: ToolExecutionContext, params: dict[str, object]) -> dict[str, object]:
    assert ctx.workspace_path
    git = GitCli()
    extra = [str(params["path"])] if params.get("path") else []
    result = git.run(["diff", *extra], cwd=ctx.workspace_path)
    return {"diff": result.stdout}


async def git_status(ctx: ToolExecutionContext, params: dict[str, object]) -> dict[str, object]:
    assert ctx.workspace_path
    git = GitCli()
    result = git.run(["status", "--porcelain"], cwd=ctx.workspace_path)
    return {"status": result.stdout}


async def git_commit(ctx: ToolExecutionContext, params: dict[str, object]) -> dict[str, object]:
    assert ctx.workspace_path and ctx.contract and ctx.workspace_branch
    if ctx.contract.work_type != WorkType.CODE_CHANGE:
        raise PathPolicyViolation("git.commit only for CODE_CHANGE")
    expected_branch = f"olympus/{ctx.execution_key}"
    branch = str(params.get("branch", ctx.workspace_branch))
    if branch != expected_branch:
        raise PathPolicyViolation(f"commit only allowed on branch {expected_branch}")
    message = str(params.get("message", "feat: implementation"))
    git = GitCli()
    git.run(["add", "-A"], cwd=ctx.workspace_path)
    status = git.run(["status", "--porcelain"], cwd=ctx.workspace_path).stdout.splitlines()
    changed: list[dict[str, object]] = []
    for line in status:
        if len(line) < 4:
            continue
        code, rel = line[:2], line[3:].strip()
        if " -> " in rel:
            rel = rel.split(" -> ", 1)[1]
        try:
            assert_write_scope(
                ctx.workspace_path / rel,
                ctx.workspace_path,
                ctx.contract.allowed_scope,
            )
        except PathPolicyViolation as exc:
            raise PathPolicyViolation(str(exc)) from exc
        fpath = ctx.workspace_path / rel
        if fpath.is_file():
            from core.security.snapshot_gate import scan_worktree_file_text

            scan_worktree_file_text(fpath.read_text(encoding="utf-8", errors="replace"), rel)
        changed.append({"path": rel, "change_type": code.strip(), "additions": 0, "deletions": 0})
    parent = git.run(["rev-parse", "HEAD"], cwd=ctx.workspace_path).stdout.strip()
    task_ref = params.get("task_contract_ref", "")
    git.run(
        [
            "-c",
            "user.name=Olympus Forge",
            "-c",
            "user.email=forge@olympus.local",
            "commit",
            "-m",
            message,
            "--trailer",
            f"Olympus-Execution: {ctx.execution_key}",
            "--trailer",
            f"Olympus-Task: {ctx.task_id}",
            "--trailer",
            f"Olympus-Contract: {task_ref}",
        ],
        cwd=ctx.workspace_path,
    )
    sha = git.run(["rev-parse", "HEAD"], cwd=ctx.workspace_path).stdout.strip()
    diff = git.run(["diff", f"{parent}..{sha}"], cwd=ctx.workspace_path).stdout
    existing = await ctx.session.execute(
        select(CandidateCommit).where(CandidateCommit.execution_id == ctx.execution_id)
    )
    if existing.scalar_one_or_none() is not None:
        raise PathPolicyViolation("candidate commit already exists for execution")
    from core.execution.artifacts import ArtifactStore

    store = ArtifactStore()
    diff_artifact = await store.put(
        ctx.session,
        project_id=ctx.project_id,
        delivery_cycle_id=ctx.delivery_cycle_id,
        execution_id=ctx.execution_id,
        kind="CANDIDATE_DIFF",
        schema_name="GitDiff",
        schema_version="1",
        content=diff.encode("utf-8"),
    )
    cc_key = await next_project_key(ctx.session, ctx.project_id, "candidate_commit", prefix="CC")
    row = CandidateCommit(
        key=cc_key,
        execution_id=ctx.execution_id,
        task_id=ctx.task_id,
        repository_id=ctx.repository_id or uuid.UUID(int=0),
        branch=branch,
        sha=sha,
        parent_sha=parent,
        base_sha=parent,
        changed_files=changed,
        diff_artifact_id=diff_artifact.id,
        principal_symbols_declared=_symbol_list(params.get("principal_symbols")),
    )
    ctx.session.add(row)
    await ctx.session.flush()
    from core.domain.actors.models import Actor
    from core.domain.enums import ActorKind

    actor_id = ctx.actor_id
    if actor_id is None:
        actor_row = await ctx.session.execute(
            select(Actor).where(Actor.kind == ActorKind.SYSTEM).limit(1)
        )
        actor_id = actor_row.scalar_one().id
    await append_domain_event(
        ctx.session,
        aggregate_type="candidate_commit",
        aggregate_id=row.id,
        event_type="candidate_commit.created",
        payload={"execution_id": str(ctx.execution_id), "sha": sha, "branch": branch},
        actor_id=actor_id,
        correlation_id=ctx.correlation_id,
        project_id=ctx.project_id,
        delivery_cycle_id=ctx.delivery_cycle_id,
    )
    return {"sha": sha, "parent_sha": parent, "branch": branch, "diff_preview": diff[:8000]}
