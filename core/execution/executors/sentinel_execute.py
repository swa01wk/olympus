"""Deterministic sentinel.execute executor."""

from __future__ import annotations

import uuid
from pathlib import Path
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.assurance.coverage import CoverageService
from core.assurance.enums import EvidenceProducer, EvidenceResult, EvidenceType
from core.assurance.evidence import EvidenceService
from core.assurance.models import VerificationObligation, VerificationPlanRow
from core.assurance.schemas import PlannedCheck, VerificationPlan
from core.assurance.verification_workspace import VerificationWorkspaceService
from core.commands.context import CommandContext
from core.domain.delivery_cycles.models import DeliveryCycle
from core.domain.enums import ActorKind
from core.domain.exceptions import DomainError
from core.execution.executors.base import ExecutionContext, ExecutorOutcome
from core.integration.models import IntegrationCandidate
from core.tools.handlers.test_runner import run_probe_in_workspace, run_pytest_in_workspace


async def run_sentinel_execute(
    session: AsyncSession,
    ctx: ExecutionContext,
    command_ctx: CommandContext,
) -> ExecutorOutcome:
    ic_id, plan_id = _refs_from_contract(ctx)
    ic = await session.get(IntegrationCandidate, ic_id)
    if ic is None or ic.integrated_sha is None:
        return ExecutorOutcome(
            status="FAILED",
            error_code="IC_NOT_READY",
            error_message="Integration candidate not ready",
        )
    plan_row = await session.get(VerificationPlanRow, plan_id)
    if plan_row is None:
        return ExecutorOutcome(
            status="FAILED",
            error_code="PLAN_MISSING",
            error_message="Verification plan not found",
        )
    plan_payload = (plan_row.validation_report or {}).get("plan")
    if not plan_payload:
        return ExecutorOutcome(
            status="FAILED",
            error_code="PLAN_EMPTY",
            error_message="Plan payload missing",
        )
    plan = VerificationPlan.model_validate(plan_payload)
    cycle = await session.get(DeliveryCycle, ic.delivery_cycle_id)
    if cycle is None:
        return ExecutorOutcome(status="FAILED", error_code="NOT_FOUND", error_message="cycle")
    from core.domain.actors.models import Actor

    actor = (
        await session.execute(select(Actor).where(Actor.kind == ActorKind.SYSTEM).limit(1))
    ).scalar_one()
    _, overlay = await VerificationWorkspaceService().prepare(
        session,
        ctx.execution,
        ic.id,
        actor_id=actor.id,
        correlation_id=str(ctx.execution.id),
    )
    from core.domain.execution_workspaces.models import ExecutionWorkspace

    ws = (
        await session.execute(
            select(ExecutionWorkspace).where(ExecutionWorkspace.execution_id == ctx.execution.id)
        )
    ).scalar_one()
    from core.domain.repositories.models import Repository, RepositoryWorkspace
    from core.repositories.workspace_locator import WorkspaceLocator

    repo = await session.get(Repository, ic.repository_id)
    assert repo and repo.workspace_id
    canonical_ws = await session.get(RepositoryWorkspace, repo.workspace_id)
    assert canonical_ws is not None
    wt_path = WorkspaceLocator().resolve(canonical_ws.storage_backend, ws.logical_location)
    obligations = {
        o.subject_key: o
        for o in (
            await session.execute(
                select(VerificationObligation).where(
                    VerificationObligation.integration_candidate_id == ic.id
                )
            )
        ).scalars()
    }
    evidence_svc = EvidenceService()
    results: list[dict[str, Any]] = []
    for check in plan.checks:
        obl = obligations.get(check.obligation_key)
        if obl is None:
            continue
        outcome = await _run_check(wt_path, overlay, check)
        result = EvidenceResult.PASS if outcome.get("passed") else EvidenceResult.FAIL
        ev_type = EvidenceType.UNIT_TEST
        if check.kind == "API_PROBE":
            ev_type = EvidenceType.API_TEST
        await evidence_svc.record(
            session,
            project_id=cycle.project_id,
            delivery_cycle_id=cycle.id,
            integration_candidate_id=ic.id,
            commit_sha=ic.integrated_sha,
            evidence_type=ev_type,
            result=result,
            subject_type="AC",
            subject_id=obl.subject_id,
            check_ref=str(check.test_node_id or check.test_filename or check.kind),
            producer=EvidenceProducer.SENTINEL,
            ctx=command_ctx,
            obligation_id=obl.id,
            execution_id=ctx.execution.id,
            details=outcome,
        )
        results.append({"obligation": check.obligation_key, "passed": outcome.get("passed")})
    await CoverageService().recompute_for_ic(session, ic.id, command_ctx)
    return ExecutorOutcome(
        status="OUTPUT_PRODUCED",
        output={"checks": results, "integration_candidate_id": str(ic.id)},
    )


def _refs_from_contract(ctx: ExecutionContext) -> tuple[uuid.UUID, uuid.UUID]:
    ic_id: uuid.UUID | None = None
    plan_id: uuid.UUID | None = None
    for ref in ctx.contract.inputs:
        if ref.ref_type == "INTEGRATION_CANDIDATE":
            ic_id = ref.ref_id
        if ref.ref_type == "VERIFICATION_PLAN":
            plan_id = ref.ref_id
    if ic_id is None or plan_id is None:
        raise DomainError(code="CONTRACT_INPUTS", message="Missing IC or plan ref")
    return ic_id, plan_id


async def _run_check(
    wt_path: Path,
    overlay: Path,
    check: PlannedCheck,
) -> dict[str, Any]:
    if check.kind == "EXISTING_TEST" and check.test_node_id:
        junit = overlay / f"junit_{check.obligation_key}.xml"
        return await run_pytest_in_workspace(
            wt_path,
            {
                "runner": "pytest",
                "args": [check.test_node_id, f"--junitxml={junit}"],
            },
        )
    if check.kind == "AUTHORED_TEST" and check.test_code and check.test_filename:
        target = overlay / check.test_filename
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(check.test_code, encoding="utf-8")
        return await run_pytest_in_workspace(wt_path, {"runner": "pytest", "args": [str(target)]})
    if check.kind == "API_PROBE" and check.probe is not None:
        return await run_probe_in_workspace(
            wt_path,
            {"probes": [check.probe.model_dump(mode="json")]},
        )
    return {"passed": False, "error": "unsupported_check"}
