from __future__ import annotations

import re
from collections.abc import Awaitable, Callable
from typing import Literal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.domain.artifacts.models import Artifact
from core.domain.executions.models import Execution
from core.domain.task_contracts.schemas import TaskContractBody

ValidatorFn = Callable[[AsyncSession, Execution, TaskContractBody, str], Awaitable[str | None]]

_REGISTRY: list[tuple[re.Pattern[str], ValidatorFn]] = []


def register_output_validator(pattern: str, fn: ValidatorFn) -> None:
    _REGISTRY.append((re.compile(pattern), fn))


async def _artifact_kind_validator(
    session: AsyncSession,
    execution: Execution,
    _contract: TaskContractBody,
    output_name: str,
) -> str | None:
    kind = output_name.split(":", 1)[1]
    result = await session.execute(
        select(Artifact).where(
            Artifact.execution_id == execution.id,
            Artifact.kind == kind,
        )
    )
    if result.scalar_one_or_none() is None:
        return f"missing artifact kind {kind}"
    return None


async def _candidate_commit_validator(
    session: AsyncSession,
    execution: Execution,
    contract: TaskContractBody,
    _output_name: str,
) -> str | None:
    from sqlalchemy import select

    from core.domain.candidate_commits.models import CandidateCommit
    from core.domain.enums import WorkType

    if contract.work_type != WorkType.CODE_CHANGE:
        return None
    result = await session.execute(
        select(CandidateCommit).where(CandidateCommit.execution_id == execution.id)
    )
    row = result.scalar_one_or_none()
    if row is None:
        return "missing candidate commit"
    if contract.allowed_scope:
        import fnmatch

        for item in row.changed_files:
            path = item.get("path", "")
            if not any(fnmatch.fnmatch(path, pattern) for pattern in contract.allowed_scope):
                return f"changed file {path} outside allowed_scope"
    return None


async def _changed_files_validator(
    session: AsyncSession,
    execution: Execution,
    contract: TaskContractBody,
    _output_name: str,
) -> str | None:
    from agents.forge.schemas import ImplementationResult
    from sqlalchemy import select

    from core.domain.candidate_commits.models import CandidateCommit

    if execution.output is None:
        return None
    try:
        impl = ImplementationResult.model_validate(execution.output)
    except Exception:
        return None
    result = await session.execute(
        select(CandidateCommit).where(CandidateCommit.execution_id == execution.id)
    )
    row = result.scalar_one_or_none()
    if row is None:
        return None
    actual = sorted({item.get("path", "") for item in row.changed_files})
    declared = sorted(impl.changed_files)
    if actual != declared:
        return f"changed_files mismatch: commit {actual} vs output {declared}"
    return None


async def _test_results_validator(
    session: AsyncSession,
    execution: Execution,
    contract: TaskContractBody,
    _output_name: str,
) -> str | None:
    if "unit_tests" not in contract.verification_requirements:
        return None
    from sqlalchemy import select

    from core.domain.actions.models import ActionRequest, ActionResult
    from core.domain.enums import ActionStatus

    q = await session.execute(
        select(ActionResult)
        .join(ActionRequest, ActionRequest.id == ActionResult.action_request_id)
        .where(
            ActionRequest.execution_id == execution.id,
            ActionRequest.tool == "test.run",
            ActionRequest.status == ActionStatus.SUCCEEDED,
        )
    )
    if q.scalar_one_or_none() is None:
        return "missing successful test.run action"
    return None


async def _product_decomposition_validator(
    session: AsyncSession,
    execution: Execution,
    _contract: TaskContractBody,
    _output_name: str,
) -> str | None:
    from agents.kira.schemas import ProductDecomposition

    from core.product_model.validation import sanitize_proposal_requirement_refs, validate_proposal

    if execution.output is None:
        return "missing decomposition output"
    try:
        proposal = ProductDecomposition.model_validate(execution.output)
    except Exception as exc:
        return f"invalid ProductDecomposition schema: {exc}"
    proposal = sanitize_proposal_requirement_refs(proposal)
    if execution.output != proposal.model_dump(mode="json"):
        execution.output = proposal.model_dump(mode="json")
        await session.flush()
    errors = validate_proposal(proposal)
    if errors:
        return "; ".join(errors)
    result = await session.execute(
        select(Artifact).where(
            Artifact.execution_id == execution.id,
            Artifact.kind == "PRODUCT_DECOMPOSITION",
        )
    )
    if result.scalar_one_or_none() is None:
        return "missing artifact kind PRODUCT_DECOMPOSITION"
    return None


async def _release_result_validator(
    _session: AsyncSession,
    execution: Execution,
    _contract: TaskContractBody,
    _output_name: str,
) -> str | None:
    if not isinstance(execution.output, dict):
        return "missing release output"
    if execution.output.get("status") != "RELEASED":
        return "release output status is not RELEASED"
    if not execution.output.get("integrated_sha"):
        return "release output missing integrated_sha"
    return None


async def _integration_result_validator(
    session: AsyncSession,
    execution: Execution,
    _contract: TaskContractBody,
    _output_name: str,
) -> str | None:
    if execution.output is None:
        return "missing integration output"
    payload = (
        execution.output.get("integration_result") if isinstance(execution.output, dict) else None
    )
    if not payload or not payload.get("integrated_sha"):
        return "integration_result missing integrated_sha"
    return None


def register_builtin_validators() -> None:
    if _REGISTRY:
        return
    register_output_validator(r"^release_result$", _release_result_validator)
    register_output_validator(r"^integration_result$", _integration_result_validator)
    register_output_validator(r"^artifact:PRODUCT_DECOMPOSITION$", _product_decomposition_validator)
    register_output_validator(r"^artifact:.+", _artifact_kind_validator)
    register_output_validator(r"^candidate_commit$", _candidate_commit_validator)
    register_output_validator(r"^changed_files$", _changed_files_validator)
    register_output_validator(r"^test_results$", _test_results_validator)


# Candidate commit and changed_files exist after the agent finishes (before execution `commit`).
_POST_COMMIT_VALIDATORS: frozenset[str] = frozenset()


async def validate_required_outputs(
    session: AsyncSession,
    execution: Execution,
    contract: TaskContractBody,
    *,
    phase: Literal["pre_commit", "post_commit", "all"] = "all",
) -> list[str]:
    register_builtin_validators()
    errors: list[str] = []
    for name in contract.required_outputs:
        if phase == "pre_commit" and name in _POST_COMMIT_VALIDATORS:
            continue
        if phase == "post_commit" and name not in _POST_COMMIT_VALIDATORS:
            continue
        matched = False
        for pattern, fn in _REGISTRY:
            if pattern.match(name):
                matched = True
                err = await fn(session, execution, contract, name)
                if err:
                    errors.append(err)
                break
        if not matched and phase == "all":
            errors.append(f"no validator for output {name}")
    return errors
