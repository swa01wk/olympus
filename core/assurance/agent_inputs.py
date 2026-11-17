"""What Warden and Sentinel get to see about an integration candidate.

Both agents are planned from the contract's ``_snapshot``; without these inputs Warden reviews
an empty prompt and Sentinel invents obligation keys that plan validation then rejects.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.assurance.models import VerificationObligation
from core.domain.delivery_cycles.models import DeliveryCycle
from core.domain.enums import SpecStatus
from core.domain.repositories.models import Repository, RepositoryWorkspace
from core.execution.worktrees.git import GitCli
from core.integration.models import IntegrationCandidate
from core.planning.models import ImplementationSpec
from core.product_model.models import AcceptanceCriterion
from core.repositories.workspace_locator import WorkspaceLocator

MAX_DIFF_CHARS = 60_000
MAX_SPECS_CHARS = 100_000  # a 19-spec app is ~57k; cutting specs makes Warden flag in-scope code
_TEST_DEF = re.compile(r"^(?P<indent>\s*)(?:async\s+)?def\s+(?P<name>test_\w+)\s*\(", re.M)
_CLASS_DEF = re.compile(r"^class\s+(?P<name>Test\w*)\b", re.M)


async def _git_dir(session: AsyncSession, ic: IntegrationCandidate) -> Path | None:
    repo = await session.get(Repository, ic.repository_id)
    if repo is None or repo.workspace_id is None:
        return None
    ws = await session.get(RepositoryWorkspace, repo.workspace_id)
    if ws is None:
        return None
    return WorkspaceLocator().resolve(ws.storage_backend, ws.logical_location)


def _pytest_nodes(git: GitCli, git_dir: Path, sha: str) -> list[str]:
    files = git.run(
        ["ls-tree", "-r", "--name-only", sha, "--", "tests"], git_dir=git_dir, check=False
    ).stdout.split()
    nodes: list[str] = []
    for path in files:
        name = path.rsplit("/", 1)[-1]
        if not (name.startswith("test_") and name.endswith(".py")):
            continue
        text = git.run(["show", f"{sha}:{path}"], git_dir=git_dir, check=False).stdout
        current_class: str | None = None
        for line in text.splitlines():
            cls = _CLASS_DEF.match(line)
            if cls:
                current_class = cls.group("name")
                continue
            if line and not line[0].isspace():
                current_class = None
            fn = _TEST_DEF.match(line)
            if fn is None:
                continue
            if fn.group("indent") and current_class:
                nodes.append(f"{path}::{current_class}::{fn.group('name')}")
            elif not fn.group("indent"):
                nodes.append(f"{path}::{fn.group('name')}")
    return nodes


async def sentinel_plan_inputs(session: AsyncSession, ic: IntegrationCandidate) -> dict[str, Any]:
    rows = await session.execute(
        select(VerificationObligation)
        .where(VerificationObligation.integration_candidate_id == ic.id)
        .order_by(VerificationObligation.subject_key)
    )
    obligations: list[dict[str, Any]] = []
    for ob in rows.scalars():
        statement = None
        if ob.subject_type == "AC" and ob.subject_id is not None:
            ac = await session.get(AcceptanceCriterion, ob.subject_id)
            statement = ac.statement if ac is not None else None
        obligations.append(
            {
                "obligation_key": ob.subject_key,
                "required": ob.required,
                "statement": statement,
                "allowed_evidence_types": list(ob.allowed_evidence_types or []),
            }
        )
    tests: list[str] = []
    git_dir = await _git_dir(session, ic)
    if git_dir is not None and ic.integrated_sha:
        tests = _pytest_nodes(GitCli(), git_dir, ic.integrated_sha)
    return {"obligations": obligations, "tests": tests}


async def warden_review_inputs(session: AsyncSession, ic: IntegrationCandidate) -> dict[str, Any]:
    cycle = await session.get(DeliveryCycle, ic.delivery_cycle_id)
    diff = ""
    git_dir = await _git_dir(session, ic)
    if git_dir is not None and ic.integrated_sha:
        base = (cycle.base_sha if cycle else None) or ic.base_sha
        diff = (
            GitCli()
            .run(["diff", f"{base}..{ic.integrated_sha}"], git_dir=git_dir, check=False)
            .stdout
        )
        if len(diff) > MAX_DIFF_CHARS:
            diff = diff[:MAX_DIFF_CHARS] + f"\n... diff truncated ({len(diff)} chars total)\n"
    specs: list[dict[str, Any]] = []
    if cycle is not None:
        rows = await session.execute(
            select(ImplementationSpec)
            .where(
                ImplementationSpec.project_id == cycle.project_id,
                ImplementationSpec.status == SpecStatus.APPROVED,
            )
            .order_by(ImplementationSpec.lineage_key, ImplementationSpec.version.desc())
        )
        seen: set[str] = set()
        used = 0
        for spec in rows.scalars():
            if spec.lineage_key in seen:
                continue
            seen.add(spec.lineage_key)
            entry = {"lineage_key": spec.lineage_key, "body": spec.body}
            used += len(str(entry))
            if used > MAX_SPECS_CHARS:
                specs.append({"note": "further specs omitted for length"})
                break
            specs.append(entry)
    return {"integrated_diff": diff, "specs": specs}
