"""Assurance integration tests stub sentinel verification execution."""

from __future__ import annotations

from collections.abc import Iterator

import pytest
from core.assurance.coverage import CoverageService
from core.assurance.enums import EvidenceProducer, EvidenceResult, EvidenceType
from core.assurance.evidence import EvidenceService
from core.assurance.models import VerificationObligation, VerificationPlanRow
from core.assurance.schemas import VerificationPlan
from core.domain.delivery_cycles.models import DeliveryCycle
from core.execution.executors.base import ExecutorOutcome
from core.execution.executors.sentinel_execute import _refs_from_contract
from core.integration.models import IntegrationCandidate
from sqlalchemy import select

# Mutable flag (not ContextVar): execution worker tasks do not inherit context vars.
_force_sentinel_fail: bool = False


async def _stub_run_sentinel_execute(session, ctx, command_ctx) -> ExecutorOutcome:
    ic_id, plan_id = _refs_from_contract(ctx)
    ic = await session.get(IntegrationCandidate, ic_id)
    plan_row = await session.get(VerificationPlanRow, plan_id)
    if ic is None or plan_row is None or ic.integrated_sha is None:
        return ExecutorOutcome(status="FAILED", error_code="IC_NOT_READY", error_message="missing")
    cycle = await session.get(DeliveryCycle, ic.delivery_cycle_id)
    if cycle is None:
        return ExecutorOutcome(status="FAILED", error_code="NOT_FOUND", error_message="cycle")
    plan_payload = (plan_row.validation_report or {}).get("plan")
    if not plan_payload:
        return ExecutorOutcome(status="FAILED", error_code="PLAN_EMPTY", error_message="no plan")
    plan = VerificationPlan.model_validate(plan_payload)
    obligations = {
        o.subject_key: o
        for o in (
            await session.execute(
                select(VerificationObligation).where(
                    VerificationObligation.integration_candidate_id == ic.id,
                )
            )
        ).scalars()
    }
    passed = not _force_sentinel_fail
    evidence_svc = EvidenceService()
    results: list[dict[str, object]] = []
    for check in plan.checks:
        obl = obligations.get(check.obligation_key)
        if obl is None:
            continue
        await evidence_svc.record(
            session,
            project_id=cycle.project_id,
            delivery_cycle_id=cycle.id,
            integration_candidate_id=ic.id,
            commit_sha=ic.integrated_sha,
            evidence_type=EvidenceType.UNIT_TEST,
            result=EvidenceResult.PASS if passed else EvidenceResult.FAIL,
            subject_type="AC",
            subject_id=obl.subject_id,
            check_ref=str(check.test_node_id or check.obligation_key),
            producer=EvidenceProducer.SENTINEL,
            ctx=command_ctx,
            obligation_id=obl.id,
            execution_id=ctx.execution.id,
            details={"passed": passed, "stub": True},
        )
        results.append({"obligation": check.obligation_key, "passed": passed})
    await CoverageService().recompute_for_ic(session, ic.id, command_ctx)
    return ExecutorOutcome(
        status="OUTPUT_PRODUCED",
        output={"checks": results, "integration_candidate_id": str(ic.id)},
    )


@pytest.fixture
def force_sentinel_fail() -> Iterator[None]:
    global _force_sentinel_fail
    prior = _force_sentinel_fail
    _force_sentinel_fail = True
    try:
        yield
    finally:
        _force_sentinel_fail = prior


@pytest.fixture(autouse=True)
def _patch_sentinel_execute(
    request: pytest.FixtureRequest,
    monkeypatch: pytest.MonkeyPatch,
) -> Iterator[None]:
    if request.node.get_closest_marker("live_llm"):
        yield
        return

    global _force_sentinel_fail
    _force_sentinel_fail = False

    async def _wrapper(ctx) -> ExecutorOutcome:
        session = ctx.session
        if session is None:
            return ExecutorOutcome(
                status="FAILED",
                error_code="NO_SESSION",
                error_message="sentinel.execute requires database session",
            )
        from core.commands.context import CommandContext
        from core.domain.actors.models import Actor
        from core.domain.enums import ActorKind
        from sqlalchemy import select

        actor = (
            await session.execute(select(Actor).where(Actor.kind == ActorKind.SYSTEM).limit(1))
        ).scalar_one()
        command_ctx = CommandContext(
            actor=actor,
            correlation_id=str(ctx.execution.id),
        )
        return await _stub_run_sentinel_execute(session, ctx, command_ctx)

    from core.execution.executors import deterministic as deterministic_executors

    monkeypatch.setitem(deterministic_executors._REGISTRY, "sentinel.execute", _wrapper)
    monkeypatch.setattr(
        "core.execution.executors.sentinel_execute.run_sentinel_execute",
        _stub_run_sentinel_execute,
    )
    yield
    _force_sentinel_fail = False
