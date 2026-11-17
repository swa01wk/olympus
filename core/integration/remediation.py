"""Remediation task creation for integration findings."""

from __future__ import annotations

import re

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
    *,
    conflict_sha: str | None = None,
    candidate_sha: str | None = None,
    task_key: str = "",
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
    files = ", ".join(allowed) or "(none reported)"
    body = TaskContractBody(
        objective=(
            f"Resolve the merge conflict in {ic.key}. Your workspace is the half-finished merge "
            f"of task {task_key or '?'} (commit {(candidate_sha or '?')[:10]}) into the code "
            f"merged so far. These files still contain git conflict markers (<<<<<<<, =======, "
            f">>>>>>>): {files}. Edit each one so it keeps the behaviour of both sides, remove "
            "every marker, run the tests, then call git.commit."
        ),
        work_type=WorkType.CODE_CHANGE,
        inputs=[],
        repository_id=ic.repository_id,
        base_policy="EXPLICIT_SHA",
        # The conflict commit holds the markers; without it the agent would start from the
        # integration base and see none of the conflicting code.
        base_commit=conflict_sha or ic.integrated_sha or ic.base_sha,
        allowed_scope=allowed or ["**"],
        allowed_actions=[
            "repo.read",
            "repo.list",
            "repo.search",
            "repo.write",
            "git.status",
            "git.diff",
            "git.commit",
            "test.run",
            "shell.run",
        ],
        constraints=[
            "Only edit the files that contain conflict markers.",
            "No conflict marker may remain in any file.",
        ],
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


# Automatic fix rounds for failed integration checks before Autopilot asks the person. Each
# round is one coding task, so this bounds the model calls a stubborn failure can use.
MAX_AUTO_CHECK_FIXES = 3

_LOCATION = re.compile(r"^\S+\.py:\d+: \w+")  # "app/api/links.py:21: ValidationError"
_RESULT = re.compile(r"\b\d+ (failed|errors?)\b")  # "2 failed, 25 passed in 1.29s"


def summarize_check_output(output: str, *, limit: int = 4000) -> str:
    """The lines a fixer needs from a check run (what failed, where and why), not the whole
    log. Falls back to the end of the log when nothing matches."""
    picked: list[str] = []
    for raw in output.splitlines():
        line = raw.rstrip()
        stripped = line.strip()
        if stripped.startswith(("/", "../")) or "site-packages" in stripped:
            continue  # frames and warnings from installed libraries, not the project's code
        if (
            stripped.startswith(("FAILED ", "ERROR ", "E ", "*** "))
            or _LOCATION.match(stripped)
            or _RESULT.search(stripped)
        ):
            picked.append(line)
    text = "\n".join(dict.fromkeys(picked)) or output[-limit:]
    return text[:limit]


async def auto_check_fixes_in_a_row(session: AsyncSession, cycle_id: object) -> int:
    """How many of the latest failed-check findings got an automatic fix, newest first,
    stopping at the first one a person sent to be fixed (that resets the count)."""
    from sqlalchemy import select

    rows = (
        await session.execute(
            select(Finding)
            .where(
                Finding.delivery_cycle_id == cycle_id,
                Finding.category == "INTEGRATION_CHECK_FAILED",
                Finding.remediation_task_id.is_not(None),
            )
            .order_by(Finding.created_at.desc())
        )
    ).scalars()
    count = 0
    for row in rows:
        detail = row.detail if isinstance(row.detail, dict) else {}
        if not detail.get("auto_fix"):
            break
        count += 1
    return count


async def create_check_failure_remediation(
    session: AsyncSession,
    ic: IntegrationCandidate,
    finding: Finding,
    ctx: CommandContext,
    *,
    merged_head_sha: str | None = None,
    auto: bool,
) -> bool:
    """Create a coding task that makes the merged code pass its checks.

    ``auto`` is True when Olympus does this on its own; then it stops after
    MAX_AUTO_CHECK_FIXES rounds in a row and leaves the finding open for the person.
    Returns whether a task was created.
    """
    from core.domain.delivery_cycles.models import DeliveryCycle

    if finding.status != FindingStatus.OPEN:
        return False
    if auto and await auto_check_fixes_in_a_row(session, finding.delivery_cycle_id) >= (
        MAX_AUTO_CHECK_FIXES
    ):
        return False
    cycle = await session.get(DeliveryCycle, ic.delivery_cycle_id)
    if cycle is None:
        return False
    detail = dict(finding.detail) if isinstance(finding.detail, dict) else {}
    head = (
        merged_head_sha
        or str(detail.get("merged_head_sha") or "")
        or ic.integrated_sha
        or await _integration_branch_head(session, ic)
    )
    summary = str(detail.get("summary") or "").strip() or await _summary_from_artifact(
        session, detail.get("artifact_id")
    )
    task = await TaskService().create_task(
        session,
        cycle.id,
        f"Fix failing checks in {ic.key}",
        WorkType.CODE_CHANGE,
        TaskOrigin.REMEDIATION,
        ctx,
        priority=0,
    )
    objective = (
        f"The code of every finished task was merged for {ic.key}, and the merged code fails "
        "its checks (compile, test collection, or pytest). Your workspace is that merged code. "
        "Find out why each failing test fails: the code may be wrong, or a test may disagree "
        "with the approved specs or with code another task wrote. Fix the cause, keeping the "
        "behaviour the specs require; do not delete or skip a test just to make it pass. Run "
        "the full test suite until it passes, then call git.commit."
    )
    if summary:
        objective += f"\n\nWhat failed:\n{summary}"
    body = TaskContractBody(
        objective=objective,
        work_type=WorkType.CODE_CHANGE,
        inputs=[],
        repository_id=ic.repository_id,
        base_policy="EXPLICIT_SHA" if head else "QUEUE_TIP",
        base_commit=head or None,
        allowed_scope=["**"],
        allowed_actions=[
            "repo.read",
            "repo.list",
            "repo.search",
            "repo.write",
            "git.status",
            "git.diff",
            "git.commit",
            "test.run",
            "shell.run",
        ],
        constraints=[
            f"finding:{finding.key}",
            "The full test suite must pass before you commit.",
            "Do not delete, skip or weaken tests to make them pass.",
        ],
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
    detail["auto_fix"] = auto
    finding.detail = detail
    finding.remediation_task_id = task.id
    finding.status = FindingStatus.IN_REMEDIATION
    await session.flush()
    return True


async def _integration_branch_head(session: AsyncSession, ic: IntegrationCandidate) -> str | None:
    """Findings recorded before the merged head was saved: the candidate's integration branch
    points at the merged code its checks ran on."""
    from core.domain.repositories.models import Repository, RepositoryWorkspace
    from core.repositories.git_inspect import GitInspector
    from core.repositories.workspace_locator import WorkspaceLocator

    repo = await session.get(Repository, ic.repository_id)
    ws = await session.get(RepositoryWorkspace, repo.workspace_id) if repo else None
    if ws is None:
        return None
    git_dir = WorkspaceLocator().resolve(ws.storage_backend, ws.logical_location)
    try:
        return GitInspector().resolve_ref(git_dir, f"refs/heads/{ic.integration_branch}")
    except ValueError:
        return None


async def _summary_from_artifact(session: AsyncSession, artifact_id: object) -> str:
    """Findings recorded before the summary was saved: rebuild it from the stored check run."""
    import json
    import uuid

    from core.domain.artifacts.models import Artifact
    from core.execution.artifacts import ArtifactStore

    try:
        artifact = await session.get(Artifact, uuid.UUID(str(artifact_id)))
        if artifact is None:
            return ""
        content = json.loads(ArtifactStore().read_bytes(artifact))
    except (ValueError, OSError, TypeError):
        return ""
    return summarize_check_output(str(content.get("output") or "")) if content else ""
