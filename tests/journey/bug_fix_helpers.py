"""Helpers for Bug Fix journey."""

from __future__ import annotations

import uuid

from core.assurance.enums import EvidenceResult, EvidenceType
from core.assurance.models import Evidence
from core.commands.context import CommandContext
from core.domain.delivery_cycles.models import DeliveryCycle
from core.domain.delivery_cycles.service import DeliveryCycleService
from core.domain.enums import (
    ApprovalStatus,
    ExecutionStatus,
    SpecStatus,
    TaskOrigin,
    TaskStatus,
    WorkType,
)
from core.domain.exceptions import DomainError, GuardFailed
from core.domain.executions.models import Execution
from core.domain.repositories.models import Repository
from core.domain.tasks.models import Task
from core.domain.tasks.service import TaskService
from core.execution.artifacts import ArtifactStore
from core.integration.enums import ICStatus
from core.integration.models import IntegrationCandidate
from core.planning.implementation_specs.service import ImplementationSpecService
from core.planning.models import ImplementationSpec
from core.product_model.defects.completion import BugFixCompletionService
from core.product_model.defects.models import (
    Defect,
    ExpectedBehaviorResolution,
    Reproduction,
    TraceCorrelation,
)
from core.product_model.defects.orchestrator import BugFixOrchestrator
from core.product_model.defects.schemas import (
    DefectTriage,
    ExpectedBehaviorProposal,
    ReproductionPlan,
    ReproductionStep,
    RootCauseHypothesis,
)
from core.product_model.defects.service import DefectService
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from tests.journey.feature_change_helpers import (
    accept_task_plan_if_proposed,
    drain_workers_factory,
    run_cycle_command,
    wait_for_cycle_state,
    wait_for_development_tasks_complete,
    wait_for_task_plan_accepted,
    wait_for_task_plan_proposed,
)

__all__ = [
    "accept_task_plan_if_proposed",
    "approve_repair_implementation_specs",
    "bootstrap_bug_fix_to_root_cause",
    "drain_workers_factory",
    "finish_bug_fix_assurance_and_release_for_cycle",
    "maybe_advance_to_expected_behavior",
    "maybe_apply_expected_behavior_fallback",
    "maybe_apply_reproduce_fallback",
    "maybe_apply_root_cause_fallback",
    "maybe_apply_triage_fallback",
    "ensure_reproduction_started",
    "maybe_apply_repair_implementation_spec_fallback",
    "maybe_complete_expected_behavior_and_root_cause",
    "maybe_complete_pre_repair_reproduction",
    "run_bug_fix_regression_until_assurance",
    "run_cycle_command",
    "wait_for_cycle_state",
    "wait_for_defect_triaged",
    "wait_for_development_tasks_complete",
    "wait_for_task_plan_accepted",
    "wait_for_task_plan_proposed",
]

# PRE_REPAIR: expect 409, observe 500 → assertion failure + signature match.
REPRO_TEST_SOURCE = """import app.models.ticket  # noqa: F401
from app.db import Base, engine

Base.metadata.create_all(bind=engine)

from app.main import app
from fastapi.testclient import TestClient


def test_closed_ticket_update_reproduces_500_symptom():
    Base.metadata.create_all(bind=engine)
    client = TestClient(app, raise_server_exceptions=False)
    created = client.post("/tickets", json={"title": "x"})
    assert created.status_code == 201
    tid = created.json()["id"]
    client.patch(f"/tickets/{tid}", json={"status": "CLOSED"})
    resp = client.patch(f"/tickets/{tid}", json={"status": "OPEN"})
    assert resp.status_code == 409, resp.status_code
"""

REPRO_TEST_PATH = "tests/olympus_repro/test_closed_ticket_500.py"

_TERMINAL_TASK = {TaskStatus.COMPLETED, TaskStatus.FAILED, TaskStatus.CANCELLED}


async def _latest_execution_id_for_profile(
    session: AsyncSession,
    cycle_id: uuid.UUID,
    agent_profile: str,
) -> uuid.UUID | None:
    return (
        await session.execute(
            select(Execution.id)
            .where(
                Execution.delivery_cycle_id == cycle_id,
                Execution.agent_profile == agent_profile,
            )
            .order_by(Execution.created_at.desc())
            .limit(1)
        )
    ).scalar_one_or_none()


async def _complete_stale_control_plane_tasks(
    session: AsyncSession,
    cycle_id: uuid.UUID,
    *,
    keep_title_contains: str | None = None,
) -> None:
    """Mark non-terminal control-plane tasks completed so verification tasks can run."""
    tasks = (
        await session.execute(
            select(Task).where(
                Task.delivery_cycle_id == cycle_id,
                Task.origin == TaskOrigin.CONTROL_PLANE,
                Task.status.not_in(tuple(_TERMINAL_TASK)),
            )
        )
    ).scalars()
    for task in tasks:
        if keep_title_contains and keep_title_contains.lower() in task.title.lower():
            continue
        if task.work_type == WorkType.VERIFICATION:
            continue
        task.status = TaskStatus.COMPLETED
    await session.flush()


async def _ensure_reproduction_run_ready(
    session: AsyncSession,
    cycle_id: uuid.UUID,
    ctx: CommandContext,
) -> None:
    await _complete_stale_control_plane_tasks(
        session, cycle_id, keep_title_contains="Run reproduction test"
    )
    run_task = (
        await session.execute(
            select(Task).where(
                Task.delivery_cycle_id == cycle_id,
                Task.title == "Run reproduction test",
                Task.status.not_in(tuple(_TERMINAL_TASK)),
            )
        )
    ).scalar_one_or_none()
    if run_task is not None and run_task.status != TaskStatus.READY:
        await TaskService().mark_ready(session, run_task.id, ctx)


async def _assert_integrated_sha_has_ticket_fix(
    session: AsyncSession,
    ic: IntegrationCandidate,
) -> None:
    from core.domain.repositories.models import Repository, RepositoryWorkspace
    from core.execution.worktrees.git import GitCli
    from core.repositories.workspace_locator import WorkspaceLocator

    if ic.integrated_sha is None:
        raise AssertionError("IC missing integrated_sha")
    repo = await session.get(Repository, ic.repository_id)
    assert repo is not None and repo.workspace_id is not None
    ws = await session.get(RepositoryWorkspace, repo.workspace_id)
    assert ws is not None
    git_dir = WorkspaceLocator().resolve(ws.storage_backend, ws.logical_location)
    git = GitCli()
    out = git.run(
        ["show", f"{ic.integrated_sha}:app/services/ticket_service.py"],
        cwd=git_dir,
    )
    text = out.stdout
    if "HTTPException" not in text or "409" not in text:
        raise AssertionError(
            f"integrated_sha {ic.integrated_sha} missing 409 fix in ticket_service.py"
        )


async def _prepare_regression_verifications(
    session: AsyncSession,
    cycle_id: uuid.UUID,
    ctx: CommandContext,
) -> None:
    """Once per REGRESSION entry: ensure verification tasks exist (journey harness)."""
    from core.assurance.enums import EvidenceResult, EvidenceType
    from core.assurance.models import Evidence
    from core.integration.enums import ICStatus
    from core.integration.models import IntegrationCandidate

    cycle = await session.get(DeliveryCycle, cycle_id)
    if cycle is None or cycle.state != "REGRESSION":
        return
    defect = await DefectService().get_by_cycle(session, cycle_id)
    ic = (
        await session.execute(
            select(IntegrationCandidate).where(
                IntegrationCandidate.delivery_cycle_id == cycle_id,
                IntegrationCandidate.status == ICStatus.READY,
            )
        )
    ).scalar_one_or_none()
    if defect is None or ic is None:
        return
    post_pass_ev = (
        await session.execute(
            select(Evidence.id).where(
                Evidence.integration_candidate_id == ic.id,
                Evidence.subject_id == defect.id,
                Evidence.evidence_type == EvidenceType.REPRODUCTION,
                Evidence.result == EvidenceResult.PASS,
            )
        )
    ).scalar_one_or_none()
    if post_pass_ev is not None:
        return
    for task in (
        await session.execute(
            select(Task).where(
                Task.delivery_cycle_id == cycle_id,
                Task.work_type == WorkType.VERIFICATION,
                Task.status != TaskStatus.CANCELLED,
            )
        )
    ).scalars():
        task.status = TaskStatus.CANCELLED
    await BugFixOrchestrator().run_regression_stage(session, cycle_id, ctx)


async def _drive_regression_stage(
    session: AsyncSession,
    cycle_id: uuid.UUID,
    ctx: CommandContext,
) -> None:
    cycle = await session.get(DeliveryCycle, cycle_id)
    if cycle is None or cycle.state != "REGRESSION":
        return
    await _complete_stale_control_plane_tasks(session, cycle_id)
    verif = list(
        (
            await session.execute(
                select(Task).where(
                    Task.delivery_cycle_id == cycle_id,
                    Task.work_type == WorkType.VERIFICATION,
                )
            )
        ).scalars()
    )
    if not verif:
        await BugFixOrchestrator().run_regression_stage(session, cycle_id, ctx)
        verif = list(
            (
                await session.execute(
                    select(Task).where(
                        Task.delivery_cycle_id == cycle_id,
                        Task.work_type == WorkType.VERIFICATION,
                    )
                )
            ).scalars()
        )
    for task in verif:
        if task.status in _TERMINAL_TASK or task.status == TaskStatus.READY:
            continue
        try:
            await TaskService().mark_ready(session, task.id, ctx)
        except (DomainError, GuardFailed):
            continue
    for _ in range(8):
        ran = await _execute_pending_regression_verifications(session, cycle_id, ctx)
        if not ran:
            break
    from core.assurance.reproduction.regression import finalize_regression_gates

    await finalize_regression_gates(session, cycle_id, ctx)


async def _execute_pending_regression_verifications(
    session: AsyncSession,
    cycle_id: uuid.UUID,
    ctx: CommandContext,
) -> bool:
    """Run one batch of deterministic repro/regression tasks; return True if any ran."""
    import uuid as uuid_mod

    from core.assurance.reproduction.register import _wrap_regression, _wrap_reproduction
    from core.domain.executions.models import Execution
    from core.domain.task_contracts.models import TaskContract
    from core.domain.task_contracts.schemas import parse_task_contract_body
    from core.execution.executors.base import ExecutionContext
    from core.execution.snapshots.builder import SnapshotBuilder
    from core.product_model.defects.completion import BugFixCompletionService
    from core.scheduler.admission import AdmissionService

    pending = list(
        (
            await session.execute(
                select(Task).where(
                    Task.delivery_cycle_id == cycle_id,
                    Task.work_type == WorkType.VERIFICATION,
                    Task.status.not_in(tuple(_TERMINAL_TASK)),
                )
            )
        ).scalars()
    )

    async def _task_phase(task: Task) -> str:
        contract_row = await session.get(TaskContract, task.current_contract_id)
        if contract_row and isinstance(contract_row.body, dict):
            return str(contract_row.body.get("phase") or "")
        return ""

    phase_order = {"POST_REPAIR": 0, "REGRESSION": 1, "REGRESSION_VALIDATION": 2}
    phased: list[tuple[int, Task]] = []
    for task in pending:
        phase = await _task_phase(task)
        phased.append((phase_order.get(phase, 99), task))
    phased.sort(key=lambda x: x[0])
    pending = [t for _, t in phased]
    if not pending:
        return False
    ran_any = False

    for task in pending:
        execution = (
            await session.execute(
                select(Execution)
                .where(
                    Execution.task_id == task.id,
                    Execution.status.not_in((ExecutionStatus.COMPLETED, ExecutionStatus.FAILED)),
                )
                .order_by(Execution.created_at.desc())
                .limit(1)
            )
        ).scalar_one_or_none()
        if execution is None:
            if task.status != TaskStatus.READY:
                try:
                    await TaskService().mark_ready(session, task.id, ctx)
                except (DomainError, GuardFailed):
                    continue
            if task.status != TaskStatus.READY:
                continue
            try:
                execution = await AdmissionService().admit_task(session, task.id, ctx)
            except DomainError:
                continue
        contract_row = await session.get(TaskContract, execution.task_contract_id)
        if contract_row is None:
            continue
        body = contract_row.body if isinstance(contract_row.body, dict) else {}
        det = str(body.get("deterministic_executor") or "")
        if det not in {"reproduction.run", "reproduction.regression"}:
            continue
        contract = parse_task_contract_body(contract_row.body)
        snapshot = await SnapshotBuilder().build(session, execution)
        exec_ctx = ExecutionContext(
            execution=execution,
            snapshot=snapshot,
            contract=contract,
            lease_id=uuid_mod.uuid4(),
            worker_id="bf-journey-regression",
            contract_payload=body,
            session=session,
        )
        runner = _wrap_regression if det == "reproduction.regression" else _wrap_reproduction
        outcome = await runner(exec_ctx)
        if outcome.status != "OUTPUT_PRODUCED" or not outcome.output:
            phase = str(body.get("phase") or task.title)
            raise RuntimeError(
                f"regression verification failed: {phase} "
                f"{outcome.error_code}: {outcome.error_message}"
            )
        phase = str(outcome.output.get("phase") or body.get("phase") or "")
        if phase == "POST_REPAIR" and not outcome.output.get("reproduced"):
            raise AssertionError(
                f"POST_REPAIR pytest did not pass at IC SHA: {outcome.output.get('pytest')}"
            )
        if phase == "REGRESSION" and not outcome.output.get("passed"):
            raise AssertionError(
                f"regression test did not pass at IC SHA: {outcome.output.get('pytest')}"
            )
        if phase == "REGRESSION_VALIDATION" and outcome.output.get("passed"):
            raise AssertionError(
                "regression validation expected failure at affected SHA but passed"
            )
        execution.output = outcome.output
        execution.status = ExecutionStatus.COMPLETED
        task.status = TaskStatus.COMPLETED
        await session.flush()
        await BugFixCompletionService().after_reproduction_run(
            session, execution, outcome.output, ctx
        )
        ran_any = True
    return ran_any


async def _maybe_start_assurance_after_regression(
    session: AsyncSession,
    cycle_id: uuid.UUID,
    ctx: CommandContext,
) -> bool:
    from core.product_model.defects.guards import reproduction_and_regression_pass

    cycle = await session.get(DeliveryCycle, cycle_id)
    if cycle is None or cycle.state != "REGRESSION":
        return False
    await _drive_regression_stage(session, cycle_id, ctx)
    from core.assurance.reproduction.regression import finalize_regression_gates

    await finalize_regression_gates(session, cycle_id, ctx)
    guard = await reproduction_and_regression_pass(session, cycle, ctx)
    if not guard.ok:
        return False
    svc = DeliveryCycleService()
    allowed = await svc.allowed_commands(session, cycle, ctx)
    cmd = next((c for c in allowed if c.get("command") == "start_assurance"), None)
    if cmd and cmd.get("allowed"):
        from unittest.mock import AsyncMock, patch

        noop_finalize = AsyncMock(return_value=None)
        try:
            with patch(
                "core.assurance.completion.AssuranceCompletionService._try_finalize_gates",
                noop_finalize,
            ):
                await svc.run_command(session, cycle_id, "start_assurance", "REGRESSION", ctx)
        except GuardFailed:
            return False
        return True
    return False


async def approve_repair_implementation_specs(
    session: AsyncSession,
    cycle_id: uuid.UUID,
    human_ctx: CommandContext,
) -> None:
    cycle = await session.get(DeliveryCycle, cycle_id)
    assert cycle is not None
    specs = (
        await session.execute(
            select(ImplementationSpec).where(
                ImplementationSpec.project_id == cycle.project_id,
                ImplementationSpec.kind == "REPAIR",
                ImplementationSpec.status == SpecStatus.PROPOSED,
            )
        )
    ).scalars()
    svc = ImplementationSpecService()
    from core.commands.handlers import handle_approval_decide

    for impl in specs:
        approval_id = await svc.request_approval(session, impl.id, cycle_id, human_ctx)
        await handle_approval_decide(
            session,
            human_ctx,
            {
                "approval_id": str(approval_id),
                "decision": ApprovalStatus.APPROVED.value,
                "note": "journey repair spec",
            },
        )
    actor = human_ctx.actor
    await BugFixCompletionService().maybe_start_task_plan_after_repair_impl_approval(
        session,
        cycle_id,
        CommandContext(actor=actor, correlation_id="bf-task-plan-kick"),
    )


async def wait_for_defect_triaged(
    factory: async_sessionmaker[AsyncSession],
    cycle_id: uuid.UUID,
) -> Defect:
    from tests.journey.helpers import wait_for

    async def _ok() -> bool:
        async with factory() as session:
            d = (
                await session.execute(select(Defect).where(Defect.delivery_cycle_id == cycle_id))
            ).scalar_one_or_none()
            return d is not None and d.status == "TRIAGED"

    await wait_for(_ok, timeout=600.0, interval=3.0)
    async with factory() as session:
        return (
            await session.execute(select(Defect).where(Defect.delivery_cycle_id == cycle_id))
        ).scalar_one()


async def _ensure_stub_execution_for_control_plane_task(
    session: AsyncSession,
    cycle_id: uuid.UUID,
    *,
    task_title: str,
    agent_profile: str,
) -> None:
    """Insert a COMPLETED execution so deterministic fallbacks can attach artifacts."""
    from datetime import UTC, datetime

    from core.domain.executions.models import Execution
    from core.domain.task_contracts.models import TaskContract

    if await _latest_execution_id_for_profile(session, cycle_id, agent_profile) is not None:
        return
    task = (
        await session.execute(
            select(Task).where(
                Task.delivery_cycle_id == cycle_id,
                Task.title == task_title,
            )
        )
    ).scalar_one_or_none()
    if task is None or task.current_contract_id is None:
        return
    contract = await session.get(TaskContract, task.current_contract_id)
    if contract is None:
        return
    latest = (
        await session.execute(
            select(Execution)
            .where(Execution.task_id == task.id)
            .order_by(Execution.attempt_number.desc())
            .limit(1)
        )
    ).scalar_one_or_none()
    attempt = (latest.attempt_number + 1) if latest else 1
    now = datetime.now(UTC)
    session.add(
        Execution(
            key=f"EX-stub-{uuid.uuid4().hex[:10]}",
            task_id=task.id,
            delivery_cycle_id=cycle_id,
            task_contract_id=contract.id,
            attempt_number=attempt,
            status=ExecutionStatus.COMPLETED,
            executor_kind="AGENT_RUNTIME",
            agent_profile=agent_profile,
            started_at=now,
            finished_at=now,
        )
    )
    await session.flush()


async def run_pre_repair_reproduction_for_cycle(
    session: AsyncSession,
    cycle_id: uuid.UUID,
    ctx: CommandContext,
) -> None:
    """Admit and run reproduction.run PRE_REPAIR (no worker queue)."""
    import uuid as uuid_mod

    from core.assurance.reproduction.register import _wrap_reproduction
    from core.domain.exceptions import DomainError
    from core.domain.executions.models import Execution
    from core.domain.task_contracts.models import TaskContract
    from core.domain.task_contracts.schemas import parse_task_contract_body
    from core.execution.executors.base import ExecutionContext
    from core.execution.snapshots.builder import SnapshotBuilder
    from core.scheduler.admission import AdmissionService

    task = (
        await session.execute(
            select(Task).where(
                Task.delivery_cycle_id == cycle_id,
                Task.title == "Run reproduction test",
            )
        )
    ).scalar_one()
    if task.status != TaskStatus.READY:
        await TaskService().mark_ready(session, task.id, ctx)
    try:
        execution = await AdmissionService().admit_task(session, task.id, ctx)
    except DomainError as exc:
        detail = exc.details or exc.message
        raise AssertionError(f"reproduction admission failed: {detail}") from exc
    execution = await session.get(Execution, execution.id)
    assert execution is not None
    contract_row = await session.get(TaskContract, execution.task_contract_id)
    assert contract_row is not None
    contract = parse_task_contract_body(contract_row.body)
    snapshot = await SnapshotBuilder().build(session, execution)
    exec_ctx = ExecutionContext(
        execution=execution,
        snapshot=snapshot,
        contract=contract,
        lease_id=uuid_mod.uuid4(),
        worker_id="bf-bootstrap-repro",
        contract_payload=contract_row.body if isinstance(contract_row.body, dict) else {},
        session=session,
    )
    outcome = await _wrap_reproduction(exec_ctx)
    assert outcome.status == "OUTPUT_PRODUCED", outcome.error_message
    assert outcome.output is not None
    assert outcome.output.get("reproduced") is True, outcome.output
    execution.output = outcome.output
    execution.status = ExecutionStatus.COMPLETED
    task.status = TaskStatus.COMPLETED
    await session.flush()
    await BugFixCompletionService().after_reproduction_run(session, execution, outcome.output, ctx)


async def bootstrap_bug_fix_to_root_cause(
    session: AsyncSession,
    cycle_id: uuid.UUID,
    ctx: CommandContext,
) -> None:
    """Deterministic path TRIAGE → ROOT_CAUSE with repair spec scheduling (no LLM)."""
    await maybe_apply_triage_fallback(session, cycle_id, ctx)
    cycle = await session.get(DeliveryCycle, cycle_id)
    assert cycle is not None
    if cycle.state == "TRIAGE":
        await DeliveryCycleService().run_command(
            session, cycle_id, "start_reproduction", "TRIAGE", ctx
        )
    await maybe_complete_pre_repair_reproduction(
        session,
        cycle_id,
        ctx,
        apply_reproduce_fallback=True,
        run_deterministic_if_missing=True,
    )
    await maybe_advance_to_expected_behavior(session, cycle_id, ctx)
    await maybe_complete_expected_behavior_and_root_cause(session, cycle_id, ctx)
    await session.refresh(cycle)
    assert cycle.state == "ROOT_CAUSE", f"expected ROOT_CAUSE, got {cycle.state}"


async def _pre_repair_reproduction_recorded(session: AsyncSession, cycle_id: uuid.UUID) -> bool:
    defect = (
        await session.execute(select(Defect).where(Defect.delivery_cycle_id == cycle_id))
    ).scalar_one_or_none()
    if defect is None:
        return False
    ev = (
        await session.execute(
            select(Evidence).where(
                Evidence.delivery_cycle_id == cycle_id,
                Evidence.subject_type == "DEFECT",
                Evidence.subject_id == defect.id,
                Evidence.evidence_type == EvidenceType.REPRODUCTION,
                Evidence.result == EvidenceResult.FAIL,
            )
        )
    ).scalar_one_or_none()
    if ev is None:
        return False
    details = ev.details or {}
    return bool(details.get("reproduced")) and details.get("phase") == "PRE_REPAIR"


async def maybe_complete_pre_repair_reproduction(
    session: AsyncSession,
    cycle_id: uuid.UUID,
    ctx: CommandContext,
    *,
    apply_reproduce_fallback: bool,
    run_deterministic_if_missing: bool,
) -> None:
    """Drive PRE_REPAIR reproduction.run when live workers did not finish."""
    cycle = await session.get(DeliveryCycle, cycle_id)
    if cycle is None or cycle.state != "REPRODUCTION":
        return
    if await _pre_repair_reproduction_recorded(session, cycle_id):
        return
    if apply_reproduce_fallback:
        await maybe_apply_reproduce_fallback(session, cycle_id, ctx)
    await _ensure_reproduction_run_ready(session, cycle_id, ctx)
    if await _pre_repair_reproduction_recorded(session, cycle_id):
        return
    if run_deterministic_if_missing:
        await run_pre_repair_reproduction_for_cycle(session, cycle_id, ctx)


async def ensure_reproduction_started(
    session: AsyncSession,
    cycle_id: uuid.UUID,
    ctx: CommandContext,
) -> bool:
    cycle = await session.get(DeliveryCycle, cycle_id)
    if cycle is None or cycle.state != "TRIAGE":
        return False
    defect = (
        await session.execute(select(Defect).where(Defect.delivery_cycle_id == cycle_id))
    ).scalar_one_or_none()
    if defect is None or defect.status != "TRIAGED":
        return False
    await run_cycle_command(session, cycle_id, "start_reproduction", "TRIAGE", ctx)
    return True


async def maybe_advance_to_expected_behavior(
    session: AsyncSession,
    cycle_id: uuid.UUID,
    ctx: CommandContext,
) -> bool:
    cycle = await session.get(DeliveryCycle, cycle_id)
    if cycle is None or cycle.state != "REPRODUCTION":
        return False
    defect = await DefectService().get_by_cycle(session, cycle_id)
    recorded = await _pre_repair_reproduction_recorded(session, cycle_id)
    if not recorded and (defect is None or defect.status != "REPRODUCED"):
        return False
    await run_cycle_command(session, cycle_id, "resolve_expected_behavior", "REPRODUCTION", ctx)
    return True


async def maybe_apply_triage_fallback(
    session: AsyncSession,
    cycle_id: uuid.UUID,
    ctx: CommandContext,
    *,
    feature_key: str = "FEAT-TICKETS",
) -> bool:
    """Deterministic triage when live kira.defect_triage did not complete."""
    defect = (
        await session.execute(select(Defect).where(Defect.delivery_cycle_id == cycle_id))
    ).scalar_one_or_none()
    cycle = await session.get(DeliveryCycle, cycle_id)
    if defect is None or cycle is None or defect.status != "REPORTED":
        return False
    from core.intelligence.code_index.retrieval.hybrid import HybridRetrieval

    candidates = await HybridRetrieval(session).resolve_feature(
        defect.description, defect.project_id
    )
    candidate_keys = {c.feature_key for c in candidates if c.feature_key}
    feature_keys = [feature_key] if feature_key in candidate_keys else []
    if not feature_keys and candidate_keys:
        feature_keys = [sorted(candidate_keys)[0]]
    if not feature_keys:
        from core.product_model.models import Feature

        feat = (
            await session.execute(
                select(Feature).where(
                    Feature.project_id == defect.project_id,
                    Feature.key == feature_key,
                )
            )
        ).scalar_one_or_none()
        if feat is not None:
            feature_keys = [feature_key]
        else:
            return False
    triage = DefectTriage(
        feature_keys=feature_keys,
        suspected_ac_lineage_keys=["AC-TICKET-CLOSED-UPDATE-409"],
        suspected_baseline_keys=["BL-TICKET-CREATE"],
        severity="S2",
        reproduction_plan=ReproductionPlan(
            preconditions=["A ticket exists in CLOSED status"],
            steps=[
                ReproductionStep(
                    kind="http",
                    description="PATCH closed ticket to OPEN",
                    method="PATCH",
                    path="/tickets/{id}",
                    body={"status": "OPEN"},
                )
            ],
            observed_symptom="HTTP 500 instead of 409 on invalid transition",
        ),
        observed_symptom_signature={"kind": "http_status", "value": 500},
    )
    await DefectService().persist_triage(session, cycle_id, triage, uuid.uuid4(), ctx)
    await _complete_stale_control_plane_tasks(session, cycle_id)
    if cycle.state == "TRIAGE":
        svc = DeliveryCycleService()
        allowed = await svc.allowed_commands(session, cycle, ctx)
        cmd = next((c for c in allowed if c.get("command") == "start_reproduction"), None)
        if cmd and cmd.get("allowed"):
            await svc.run_command(session, cycle_id, "start_reproduction", cycle.state, ctx)
    return True


async def maybe_apply_reproduce_fallback(
    session: AsyncSession,
    cycle_id: uuid.UUID,
    ctx: CommandContext,
) -> bool:
    """Author reproduction artifact + schedule reproduction.run when Sentinel did not."""
    cycle = await session.get(DeliveryCycle, cycle_id)
    if cycle is None or cycle.state != "REPRODUCTION":
        return False
    if await _pre_repair_reproduction_recorded(session, cycle_id):
        return False
    defect = await DefectService().get_by_cycle(session, cycle_id)
    if defect is None:
        return False
    store = ArtifactStore()
    art = await store.put(
        session,
        project_id=cycle.project_id,
        delivery_cycle_id=cycle.id,
        execution_id=None,
        kind="REPRODUCTION_TEST",
        schema_name="reproduction_test",
        schema_version="1",
        content={
            "relative_path": REPRO_TEST_PATH,
            "test_source": REPRO_TEST_SOURCE,
        },
        created_by_actor_id=ctx.actor.id,
    )
    triage = dict(defect.triage or {})
    triage["observed_symptom_signature"] = {"kind": "http_status", "value": 500}
    defect.triage = triage
    await session.flush()
    await BugFixOrchestrator().schedule_reproduction_run(session, cycle_id, art.id, ctx)
    await _ensure_reproduction_run_ready(session, cycle_id, ctx)
    return True


async def maybe_complete_expected_behavior_and_root_cause(
    session: AsyncSession,
    cycle_id: uuid.UUID,
    ctx: CommandContext,
) -> None:
    """Deterministic EXPECTED_BEHAVIOR → ROOT_CAUSE when live agent tasks did not finish."""
    cycle = await session.get(DeliveryCycle, cycle_id)
    if cycle is None:
        return
    if cycle.state == "EXPECTED_BEHAVIOR":
        await _ensure_stub_execution_for_control_plane_task(
            session,
            cycle_id,
            task_title="Resolve expected behavior",
            agent_profile="kira.expected_behavior",
        )
        await maybe_apply_expected_behavior_fallback(session, cycle_id, ctx)
        # start_root_cause just queued the live warden.root_cause task; a fallback RCA now would
        # be a second RCA once that task runs.
        return
    if cycle.state == "ROOT_CAUSE":
        await _ensure_stub_execution_for_control_plane_task(
            session,
            cycle_id,
            task_title="Root cause analysis",
            agent_profile="warden.root_cause",
        )
        await maybe_apply_root_cause_fallback(session, cycle_id, ctx)


async def approve_expected_behavior_if_pending(
    session: AsyncSession,
    cycle_id: uuid.UUID,
    human_ctx: CommandContext,
) -> bool:
    from core.commands.handlers import handle_approval_decide
    from core.domain.approvals.models import Approval
    from core.domain.enums import ApprovalType

    defect = await DefectService().get_by_cycle(session, cycle_id)
    if defect is None:
        return False
    row = await DefectService().latest_expected_behavior_resolution(session, defect.id)
    if row is None or row.approval_id is None:
        return False
    approval = await session.get(Approval, row.approval_id)
    if approval is None or approval.status != ApprovalStatus.PENDING:
        return False
    if approval.approval_type != ApprovalType.EXPECTED_BEHAVIOR:
        return False
    await handle_approval_decide(
        session,
        human_ctx,
        {
            "approval_id": str(approval.id),
            "decision": ApprovalStatus.APPROVED.value,
            "note": "journey expected behavior",
        },
    )
    return True


async def maybe_apply_expected_behavior_fallback(
    session: AsyncSession,
    cycle_id: uuid.UUID,
    ctx: CommandContext,
) -> bool:
    cycle = await session.get(DeliveryCycle, cycle_id)
    if cycle is None or cycle.state != "EXPECTED_BEHAVIOR":
        return False
    defect = await DefectService().get_by_cycle(session, cycle_id)
    if defect is None:
        return False
    existing = (
        await session.execute(
            select(ExpectedBehaviorResolution)
            .where(ExpectedBehaviorResolution.defect_id == defect.id)
            .limit(1)
        )
    ).scalar_one_or_none()
    if existing is not None:
        from tests.fixtures.brownfield_phase12_harness import ensure_human_approver

        _human, human_ctx = await ensure_human_approver(session)
        await approve_expected_behavior_if_pending(session, cycle_id, human_ctx)
        cycle = await session.get(DeliveryCycle, cycle_id)
        if cycle is not None and cycle.state == "EXPECTED_BEHAVIOR":
            await run_cycle_command(session, cycle_id, "start_root_cause", "EXPECTED_BEHAVIOR", ctx)
        return True
    execution_id = await _latest_execution_id_for_profile(
        session, cycle_id, "kira.expected_behavior"
    )
    if execution_id is None:
        return False
    proposal = ExpectedBehaviorProposal(
        classification="SPECIFIED",
        cited_ac_lineage_keys=["AC-TICKET-CLOSED-UPDATE-409"],
        expected_behavior_statement=(
            "PATCH on a CLOSED ticket must be rejected with HTTP 409 Conflict"
        ),
    )
    await DefectService().persist_expected_behavior(session, cycle_id, proposal, execution_id, ctx)
    from tests.fixtures.brownfield_phase12_harness import ensure_human_approver

    _human, human_ctx = await ensure_human_approver(session)
    await approve_expected_behavior_if_pending(session, cycle_id, human_ctx)
    cycle = await session.get(DeliveryCycle, cycle_id)
    if cycle is not None and cycle.state == "EXPECTED_BEHAVIOR":
        await run_cycle_command(session, cycle_id, "start_root_cause", "EXPECTED_BEHAVIOR", ctx)
    return True


async def maybe_apply_root_cause_fallback(
    session: AsyncSession,
    cycle_id: uuid.UUID,
    ctx: CommandContext,
) -> bool:
    cycle = await session.get(DeliveryCycle, cycle_id)
    if cycle is None or cycle.state != "ROOT_CAUSE":
        return False
    defect = await DefectService().get_by_cycle(session, cycle_id)
    if defect is None:
        return False
    from core.product_model.defects.models import RootCauseAnalysis

    rca = (
        await session.execute(
            select(RootCauseAnalysis).where(RootCauseAnalysis.defect_id == defect.id).limit(1)
        )
    ).scalar_one_or_none()
    if rca is not None:
        return False
    trace = (
        await session.execute(
            select(TraceCorrelation)
            .join(Reproduction, TraceCorrelation.reproduction_id == Reproduction.id)
            .where(Reproduction.defect_id == defect.id)
            .order_by(TraceCorrelation.created_at.desc())
            .limit(1)
        )
    ).scalar_one_or_none()
    candidate_keys = {
        str(c.get("stable_key")) for c in (trace.candidates if trace else []) if c.get("stable_key")
    }
    faulty = "FUNC:TicketService.update_status"
    if faulty not in candidate_keys:
        candidate_keys.add(faulty)
    hypothesis = RootCauseHypothesis(
        faulty_stable_keys=[faulty],
        explanation="TRANSITIONS map omits CLOSED, causing KeyError on status update",
        confidence=0.85,
        fix_outline="Add CLOSED to TRANSITIONS with no outgoing transitions; use safe lookup",
    )
    if trace is None:
        return False
    rca_execution_id = await _latest_execution_id_for_profile(
        session, cycle_id, "warden.root_cause"
    )
    if rca_execution_id is None:
        return False
    await DefectService().persist_root_cause(
        session,
        cycle_id,
        hypothesis,
        trace.id,
        rca_execution_id,
        ctx,
        candidate_keys=candidate_keys,
    )
    from core.intelligence.impact.engine import ImpactEngine
    from core.traceability.models import RepositoryIndexPointer

    pointer = await session.get(RepositoryIndexPointer, cycle.repository_id)
    if pointer and pointer.canonical_index_version_id:
        await ImpactEngine().assess(
            session,
            cycle_id,
            seed_stable_keys=hypothesis.faulty_stable_keys,
            index_version_id=pointer.canonical_index_version_id,
            ctx=ctx,
        )
    await BugFixOrchestrator().schedule_repair_implementation_spec(session, cycle_id, ctx)
    return True


async def maybe_apply_repair_implementation_spec_fallback(
    session: AsyncSession,
    cycle_id: uuid.UUID,
    ctx: CommandContext,
) -> bool:
    """Persist PROPOSED REPAIR ImplementationSpec when live kira.implementation_spec did not."""
    from core.planning.schemas import AcCoverageEntry, ImplementationSpecDraft, TestRequirement
    from core.product_model.defects.models import RootCauseAnalysis

    cycle = await session.get(DeliveryCycle, cycle_id)
    if cycle is None:
        return False
    existing = (
        await session.execute(
            select(ImplementationSpec.id).where(
                ImplementationSpec.project_id == cycle.project_id,
                ImplementationSpec.kind == "REPAIR",
                ImplementationSpec.status.in_((SpecStatus.PROPOSED, SpecStatus.APPROVED)),
            )
        )
    ).scalar_one_or_none()
    if existing is not None:
        return False
    defect = await DefectService().get_by_cycle(session, cycle_id)
    if defect is None:
        return False
    rca = (
        await session.execute(
            select(RootCauseAnalysis.id).where(RootCauseAnalysis.defect_id == defect.id).limit(1)
        )
    ).scalar_one_or_none()
    if rca is None:
        return False
    base_impl = (
        await session.execute(
            select(ImplementationSpec)
            .where(
                ImplementationSpec.project_id == cycle.project_id,
                ImplementationSpec.kind != "REPAIR",
                ImplementationSpec.status == SpecStatus.APPROVED,
            )
            .order_by(ImplementationSpec.version.desc())
            .limit(1)
        )
    ).scalar_one_or_none()
    if base_impl is None:
        return False
    base_body = ImplementationSpecService().parse_body(base_impl)
    body = base_body.model_copy(
        update={
            "required_tests": [
                *base_body.required_tests,
                TestRequirement(
                    kind="api",
                    ac_keys=["AC-TICKET-CLOSED-UPDATE-409"],
                    description="tests/test_closed_ticket_update.py regression for 409",
                ),
            ],
            "ac_coverage": [
                *base_body.ac_coverage,
                AcCoverageEntry(
                    ac_key="AC-TICKET-CLOSED-UPDATE-409",
                    locations=["tests/test_closed_ticket_update.py"],
                ),
            ],
        }
    )
    draft = ImplementationSpecDraft(body=body)
    await ImplementationSpecService().persist_repair_draft(
        session,
        feature_spec_id=base_impl.feature_spec_id,
        draft=draft,
        execution_id=await _latest_execution_id_for_profile(
            session, cycle_id, "kira.implementation_spec"
        ),
        ctx=ctx,
    )
    return True


async def run_bug_fix_regression_until_assurance(
    factory: async_sessionmaker[AsyncSession],
    cycle_id: uuid.UUID,
    ctx: CommandContext,
    *,
    max_drain_rounds: int = 40,
) -> None:
    """After IC READY: start_regression and drain until ASSURANCE or timeout."""
    async with factory() as session, session.begin():
        cycle = await session.get(DeliveryCycle, cycle_id)
        assert cycle is not None
        if cycle.state == "DEVELOPMENT":
            from tests.fixtures.release_harness import integration_ic_after_start_integration
            from tests.journey.bug_fix_dev import (
                complete_bug_fix_repair_tasks,
                complete_stale_code_change_tasks,
            )

            repo = (
                await session.get(Repository, cycle.repository_id) if cycle.repository_id else None
            )
            if repo is not None and cycle.base_sha:
                await complete_bug_fix_repair_tasks(
                    session,
                    ctx,
                    repository=repo,
                    cycle=cycle,
                    base_sha=cycle.base_sha,
                )
            await complete_stale_code_change_tasks(session, cycle_id)
            from core.integration.guards import all_code_tasks_completed

            guard = await all_code_tasks_completed(session, cycle, ctx)
            if not guard.ok:
                raise AssertionError(f"pre-integration code tasks incomplete: {guard.reasons}")
            ic_row = await integration_ic_after_start_integration(session, ctx, cycle_id)
            await _assert_integrated_sha_has_ticket_fix(session, ic_row)
            await session.refresh(cycle)
        if cycle.state == "INTEGRATION":
            await run_cycle_command(session, cycle_id, "start_regression", "INTEGRATION", ctx)
        if cycle.state == "REGRESSION":
            await _prepare_regression_verifications(session, cycle_id, ctx)
            await _drive_regression_stage(session, cycle_id, ctx)
            defect = await DefectService().get_by_cycle(session, cycle_id)
            ic_ready = (
                await session.execute(
                    select(IntegrationCandidate).where(
                        IntegrationCandidate.delivery_cycle_id == cycle_id,
                        IntegrationCandidate.status == ICStatus.READY,
                    )
                )
            ).scalar_one_or_none()
            if defect and ic_ready:
                from core.assurance.enums import EvidenceResult, EvidenceType
                from core.assurance.models import Evidence

                post = (
                    await session.execute(
                        select(Evidence.id).where(
                            Evidence.integration_candidate_id == ic_ready.id,
                            Evidence.subject_id == defect.id,
                            Evidence.evidence_type == EvidenceType.REPRODUCTION,
                            Evidence.result == EvidenceResult.PASS,
                        )
                    )
                ).scalar_one_or_none()
                if post is None:
                    verif_states = list(
                        (
                            await session.execute(
                                select(Task.title, Task.status).where(
                                    Task.delivery_cycle_id == cycle_id,
                                    Task.work_type == WorkType.VERIFICATION,
                                )
                            )
                        ).all()
                    )
                    raise AssertionError(
                        "POST_REPAIR reproduction PASS evidence missing after regression drive; "
                        f"verification_tasks={verif_states}"
                    )
            await _maybe_start_assurance_after_regression(session, cycle_id, ctx)

    async def _assurance_ready() -> bool:
        async with factory() as session:
            cycle = await session.get(DeliveryCycle, cycle_id)
            if cycle is not None and cycle.state == "ASSURANCE":
                return True
        async with factory() as session, session.begin():
            if await _maybe_start_assurance_after_regression(session, cycle_id, ctx):
                return True
        return False

    for i in range(max_drain_rounds):
        await drain_workers_factory(factory, correlation_prefix=f"bf-reg-{i}", rounds=8)
        async with factory() as session, session.begin():
            await _drive_regression_stage(session, cycle_id, ctx)
        if await _assurance_ready():
            break
    else:
        async with factory() as session:
            cycle = await session.get(DeliveryCycle, cycle_id)
            state = cycle.state if cycle else None
            from core.product_model.defects.guards import reproduction_and_regression_pass

            guard = await reproduction_and_regression_pass(session, cycle, ctx) if cycle else None
        raise TimeoutError(
            f"bug-fix regression stage did not reach ASSURANCE (last state={state}, guard={guard})"
        )
    await wait_for_cycle_state(factory, cycle_id, "ASSURANCE")


async def finish_bug_fix_assurance_and_release_for_cycle(
    session: AsyncSession,
    system_ctx: CommandContext,
    approver_ctx: CommandContext,
    cycle_id: uuid.UUID,
    *,
    live_assurance: bool = False,
) -> tuple[IntegrationCandidate, object]:
    """Assurance + release for BUG_FIX cycles already in ASSURANCE."""
    from core.product_model.guards import scope_approved
    from core.product_model.models import FeatureSpec
    from core.release.enums import ReleaseStatus
    from core.release.service import ReleaseService
    from tests.fixtures.assurance_harness import (
        add_warden_review_evidence,
        finalize_all_pending_gates,
        human_finalize_ctx,
        patch_agentless_assurance,
        run_worker_rounds,
    )
    from tests.fixtures.release_harness import (
        _stub_unsatisfied_required_obligations,
        _waive_open_blocking_findings,
        approve_and_execute_release,
        seed_approved_scope_for_feature_spec,
    )

    cycle = await session.get(DeliveryCycle, cycle_id)
    assert cycle is not None and cycle.state == "ASSURANCE"
    ic = (
        await session.execute(
            select(IntegrationCandidate)
            .where(
                IntegrationCandidate.delivery_cycle_id == cycle_id,
                IntegrationCandidate.status == ICStatus.READY,
            )
            .order_by(IntegrationCandidate.created_at.desc())
            .limit(1)
        )
    ).scalar_one()

    from core.assurance.orchestrator import AssuranceOrchestrator

    await AssuranceOrchestrator().on_integration_ready(session, ic.id, system_ctx)

    if not live_assurance:
        from tests.fixtures.assurance_harness import _refresh_sentinel_plan_and_execute

        with patch_agentless_assurance():
            await _refresh_sentinel_plan_and_execute(session, system_ctx, ic.id)
        await add_warden_review_evidence(session, ic, system_ctx)
        await _stub_unsatisfied_required_obligations(session, ic, system_ctx)
    else:
        await run_worker_rounds(session, system_ctx, max_rounds=200)
        from core.assurance.enums import GateStatus, GateType
        from core.assurance.models import Gate
        from tests.fixtures.assurance_harness import _refresh_sentinel_plan_and_execute

        gates = list(
            (
                await session.execute(select(Gate).where(Gate.integration_candidate_id == ic.id))
            ).scalars()
        )
        need_fallback = any(
            g.gate_type in {GateType.WARDEN, GateType.SENTINEL, GateType.BASELINE}
            and g.status != GateStatus.PASS
            for g in gates
        )
        if need_fallback:
            with patch_agentless_assurance():
                await _refresh_sentinel_plan_and_execute(session, system_ctx, ic.id)
            await add_warden_review_evidence(session, ic, system_ctx)
            await run_worker_rounds(session, system_ctx, max_rounds=80)

    scope_ok = await scope_approved(session, cycle, None)
    if not scope_ok.ok:
        specs = await session.execute(
            select(FeatureSpec).where(
                FeatureSpec.project_id == cycle.project_id,
                FeatureSpec.status == SpecStatus.APPROVED,
            )
        )
        fs = specs.scalars().first()
        assert fs is not None
        await seed_approved_scope_for_feature_spec(session, cycle, fs.id, approver_ctx)

    fin_ctx = await human_finalize_ctx(session)
    await finalize_all_pending_gates(session, ic.id, fin_ctx)
    await _waive_open_blocking_findings(session, cycle_id, ic.id)
    from core.assurance.coverage import CoverageService

    await CoverageService().recompute_for_ic(session, ic.id, system_ctx)
    await _stub_unsatisfied_required_obligations(session, ic, system_ctx)
    await finalize_all_pending_gates(session, ic.id, fin_ctx)
    await ReleaseService().maybe_advance_cycle_to_release(session, cycle_id, system_ctx)
    release = await ReleaseService().create_release(session, cycle_id, system_ctx)
    await session.refresh(release)
    if release.status != ReleaseStatus.ELIGIBLE:
        from core.release.models import ReleaseEligibilityEvaluation

        ev = await session.get(ReleaseEligibilityEvaluation, release.latest_eligibility_id)
        detail = ev.conditions if ev else []
        raise AssertionError(f"release not eligible: {release.status}; {detail}")
    release = await approve_and_execute_release(session, release, approver_ctx, system_ctx)
    return ic, release
