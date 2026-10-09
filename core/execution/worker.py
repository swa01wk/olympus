from __future__ import annotations

import asyncio
import uuid
from contextlib import suppress
from typing import Any, cast

from sqlalchemy.ext.asyncio import AsyncSession

from core.assurance.register import register_assurance_executors
from core.commands.context import CommandContext
from core.domain.delivery_cycles.models import DeliveryCycle
from core.domain.enums import ExecutionStatus, TaskStatus, WorkType
from core.domain.events.append import append_domain_event
from core.domain.executions.models import Execution, ExecutionLease, ExecutionSnapshot
from core.domain.task_contracts.models import TaskContract
from core.domain.task_contracts.schemas import TaskContractBody, parse_task_contract_body
from core.domain.tasks.models import Task
from core.domain.tasks.service import TaskService
from core.execution.artifacts import ArtifactStore
from core.execution.checkpoints import CheckpointService
from core.execution.executors.base import ExecutionContext, ExecutorOutcome
from core.execution.executors.deterministic import register_builtin_deterministic_executors
from core.execution.executors.registry import select_executor
from core.execution.leases.manager import LeaseManager
from core.execution.service import ExecutionService
from core.execution.snapshots.builder import SnapshotBuilder
from core.execution.validation import validate_required_outputs
from core.execution.worktrees.git import GitCliError
from core.integration.register import register_integration_executors
from core.intelligence.recovered_specs.register import register_brownfield_executors
from core.observability.logging import get_logger
from core.release.register import register_release_executors
from core.runtime.profiles.diagnostic import DiagnosticSummary
from core.state.machines import EXECUTION_TERMINAL
from core.state.transition_service import TransitionService

logger = get_logger(__name__)

# Required artifact kinds whose executors return the artifact body as output.
_OUTPUT_ARTIFACT_KINDS = frozenset(
    {
        "CHARACTERIZATION_PLAN",
        "BASELINE_RUN",
        "ARCHITECTURE_DELTA",
        "WARDEN_REVIEW",
        "VERIFICATION_PLAN",
        "VERIFICATION_EVIDENCE",
    }
)

register_builtin_deterministic_executors()
register_integration_executors()
register_assurance_executors()
register_release_executors()
register_brownfield_executors()


class ExecutionWorker:
    def __init__(
        self,
        *,
        worker_id: str,
        executions: ExecutionService | None = None,
        leases: LeaseManager | None = None,
        transitions: TransitionService | None = None,
        tasks: TaskService | None = None,
    ) -> None:
        self.worker_id = worker_id
        self._executions = executions or ExecutionService()
        self._leases = leases or LeaseManager()
        self._transitions = transitions or TransitionService()
        self._tasks = tasks or TaskService()
        self._snapshots = SnapshotBuilder()
        self._artifacts = ArtifactStore()
        self._checkpoints = CheckpointService()

    async def run_once(self, session: AsyncSession, ctx: CommandContext) -> bool:
        lease = await self._leases.claim(session, self.worker_id, ctx)
        if lease is None:
            return False
        execution = await session.get(Execution, lease.execution_id)
        if execution is None:
            await self._leases.release(session, lease)
            return True
        execution_id = execution.id
        lease_id = lease.id
        try:
            # The lease claim sits outside the savepoint: if it rolled back with the
            # failure, the execution would be re-queued and its agent re-run forever.
            async with session.begin_nested():
                await self._run_execution(session, execution, lease, ctx)
        except Exception as exc:
            logger.exception("execution_worker.execution_crashed", execution_id=str(execution_id))
            await self._fail_crashed_execution(session, execution_id, lease_id, exc, ctx)
        finally:
            fresh = await session.get(ExecutionLease, lease_id)
            if fresh and fresh.state.value == "ACTIVE":
                await self._leases.release(session, fresh)
        return True

    async def _fail_crashed_execution(
        self,
        session: AsyncSession,
        execution_id: uuid.UUID,
        lease_id: uuid.UUID,
        exc: Exception,
        ctx: CommandContext,
    ) -> None:
        # The savepoint rollback also undid lease heartbeats, so the lease may read as
        # expired; the claim's row lock still makes this worker the owner.
        execution = await session.get(Execution, execution_id, populate_existing=True)
        if execution is None or execution.status.value in EXECUTION_TERMINAL:
            return
        if execution.status == ExecutionStatus.LEASED:
            await self._executions.transition(session, execution_id, "start", ctx)
        task = await session.get(Task, execution.task_id, populate_existing=True)
        if task and task.status == TaskStatus.QUEUED:
            await self._transitions.transition(
                session, "task", task.id, TaskStatus.QUEUED.value, "start_execution", ctx
            )
        execution = await self._executions.transition(
            session,
            execution_id,
            "fail",
            ctx,
            payload={
                "failure_class": f"WORKER_{type(exc).__name__.upper()}",
                "failure_detail": {"message": str(exc)[:2000]},
                "retriable": False,
            },
        )
        if task:
            await self._executions.sync_task_on_failure(session, execution, task, ctx)

    async def _run_execution(
        self,
        session: AsyncSession,
        execution: Execution,
        lease: ExecutionLease,
        ctx: CommandContext,
    ) -> None:
        from core.observability.instrumentation import execution_span

        with execution_span(
            execution_id=str(execution.id),
            snapshot_id=str(execution.snapshot_id) if execution.snapshot_id else None,
            task_id=str(execution.task_id),
            correlation_id=ctx.correlation_id,
        ):
            await self._run_execution_inner(session, execution, lease, ctx)

    async def _run_execution_inner(
        self,
        session: AsyncSession,
        execution: Execution,
        lease: ExecutionLease,
        ctx: CommandContext,
    ) -> None:
        contract_row = await session.get(TaskContract, execution.task_contract_id)
        if contract_row is None:
            return
        contract = parse_task_contract_body(contract_row.body)
        snapshot = await self._snapshots.build(session, execution)
        await self._executions.transition(session, execution.id, "start", ctx, lease_id=lease.id)
        task = await session.get(Task, execution.task_id)
        if task and task.status == TaskStatus.QUEUED:
            await self._transitions.transition(
                session,
                "task",
                task.id,
                TaskStatus.QUEUED.value,
                "start_execution",
                ctx,
            )
        await session.refresh(execution)

        raw_body = contract_row.body if isinstance(contract_row.body, dict) else {}
        heartbeat_stop = asyncio.Event()
        heartbeat_task = asyncio.create_task(
            self._heartbeat_loop(session, lease.id, heartbeat_stop)
        )
        try:
            executor = select_executor(contract, session)
            exec_ctx = ExecutionContext(
                execution=execution,
                snapshot=snapshot,
                contract=contract,
                lease_id=lease.id,
                worker_id=self.worker_id,
                contract_payload=raw_body,
                session=session,
            )
            timeout_s = contract.timeouts.get("wall_clock_s", 1800)
            outcome = await asyncio.wait_for(executor.execute(exec_ctx), timeout=timeout_s)
        except TimeoutError:
            task = await session.get(Task, execution.task_id)
            await self._executions.transition(
                session,
                execution.id,
                "timeout",
                ctx,
                lease_id=lease.id,
                payload={"failure_class": "TIMEOUT", "retriable": True},
            )
            await session.refresh(execution)
            if task:
                await self._executions.sync_task_on_failure(session, execution, task, ctx)
            return
        except (OSError, RuntimeError, ValueError, GitCliError) as exc:
            task = await session.get(Task, execution.task_id)
            await self._executions.transition(
                session,
                execution.id,
                "fail",
                ctx,
                lease_id=lease.id,
                payload={
                    "failure_class": f"EXECUTOR_{type(exc).__name__.upper()}",
                    "failure_detail": {"message": str(exc)},
                    "retriable": False,
                },
            )
            await session.refresh(execution)
            if task:
                await self._executions.sync_task_on_failure(session, execution, task, ctx)
            return
        finally:
            heartbeat_stop.set()
            heartbeat_task.cancel()
            with suppress(asyncio.CancelledError):
                await heartbeat_task

        await self._apply_outcome(
            session, execution, snapshot, contract, lease, outcome, ctx, raw_body
        )

    async def _heartbeat_loop(
        self,
        session: AsyncSession,
        lease_id: uuid.UUID,
        stop: asyncio.Event,
    ) -> None:
        from core.config.settings import get_settings

        interval = get_settings().execution_heartbeat_interval_seconds
        while not stop.is_set():
            await asyncio.sleep(interval)
            if stop.is_set():
                break
            lease = await session.get(ExecutionLease, lease_id)
            if lease is None:
                break
            try:
                await self._leases.heartbeat(session, lease)
            except Exception:
                break

    async def _apply_outcome(
        self,
        session: AsyncSession,
        execution: Execution,
        snapshot: ExecutionSnapshot,
        contract: TaskContractBody,
        lease: ExecutionLease,
        outcome: object,
        ctx: CommandContext,
        contract_payload: dict[str, Any] | None = None,
    ) -> None:
        from core.execution.executors.base import ExecutorOutcome

        if not isinstance(outcome, ExecutorOutcome):
            return
        if outcome.status == "CHECKPOINT_REQUESTED":
            question = ""
            if outcome.checkpoint:
                questions = outcome.checkpoint.get("questions") or []
                question = str(questions[0]) if questions else "Clarification required"
            await self._checkpoints.handle_checkpoint(
                session,
                execution,
                snapshot,
                lease.id,
                question=question,
                ctx=ctx,
            )
            return
        if outcome.status == "CANCELLED":
            await self._executions.transition(
                session, execution.id, "cancel", ctx, lease_id=lease.id
            )
            return
        if outcome.status == "FAILED":
            task = await session.get(Task, execution.task_id)
            await self._executions.transition(
                session,
                execution.id,
                "fail",
                ctx,
                lease_id=lease.id,
                payload={
                    "failure_class": outcome.error_code or "RUNTIME_ERROR",
                    "failure_detail": {"message": outcome.error_message},
                    "retriable": True,
                    "runtime_metadata": outcome.runtime_metadata,
                },
            )
            if task:
                await self._executions.sync_task_on_failure(session, execution, task, ctx)
            return

        if contract.agent_profile == "orchestrator.converse" and outcome.output:
            from agents.orchestrator.schemas import OrchestratorTurn

            turn = cast(
                OrchestratorTurn,
                await self._canonical_orchestrator_turn(
                    session, outcome.output, contract_payload, ctx
                ),
            )
            outcome.output = turn.model_dump(mode="json")

        await self._executions.transition(
            session,
            execution.id,
            "output_produced",
            ctx,
            lease_id=lease.id,
            payload={
                "output": outcome.output,
                "runtime_metadata": outcome.runtime_metadata,
            },
        )
        cycle = await session.get(DeliveryCycle, execution.delivery_cycle_id)
        if cycle and outcome.output and contract.agent_profile == "kira.decompose":
            from agents.kira.schemas import ProductDecomposition

            proposal = ProductDecomposition.model_validate(outcome.output)
            await self._artifacts.put(
                session,
                project_id=cycle.project_id,
                delivery_cycle_id=cycle.id,
                execution_id=execution.id,
                kind="PRODUCT_DECOMPOSITION",
                schema_name="ProductDecomposition",
                schema_version="1",
                content=proposal.model_dump(mode="json"),
            )
            await append_domain_event(
                session,
                aggregate_type="artifact",
                aggregate_id=execution.id,
                event_type="artifact.created",
                payload={"kind": "PRODUCT_DECOMPOSITION", "execution_id": str(execution.id)},
                actor_id=ctx.actor.id,
                correlation_id=ctx.correlation_id,
                project_id=cycle.project_id,
                delivery_cycle_id=cycle.id,
            )
        if cycle and outcome.output and contract.agent_profile == "kira.change_interpret":
            from agents.kira.schemas import ChangeInterpretation

            parsed = ChangeInterpretation.model_validate(outcome.output)
            await self._artifacts.put(
                session,
                project_id=cycle.project_id,
                delivery_cycle_id=cycle.id,
                execution_id=execution.id,
                kind="CHANGE_INTERPRETATION",
                schema_name="ChangeInterpretation",
                schema_version="1",
                content=parsed.model_dump(mode="json"),
            )

        if cycle and outcome.output and contract.agent_profile == "kira.defect_triage":
            from core.product_model.defects.schemas import DefectTriage

            triage = DefectTriage.model_validate(outcome.output)
            await self._artifacts.put(
                session,
                project_id=cycle.project_id,
                delivery_cycle_id=cycle.id,
                execution_id=execution.id,
                kind="DEFECT_TRIAGE",
                schema_name="DefectTriage",
                schema_version="1",
                content=triage.model_dump(mode="json"),
            )

        if cycle and outcome.output and contract.agent_profile == "sentinel.reproduce":
            from core.product_model.defects.schemas import ReproductionTestArtifact

            repro = ReproductionTestArtifact.model_validate(outcome.output)
            await self._artifacts.put(
                session,
                project_id=cycle.project_id,
                delivery_cycle_id=cycle.id,
                execution_id=execution.id,
                kind="REPRODUCTION_TEST",
                schema_name="reproduction_test",
                schema_version="1",
                content={
                    "relative_path": repro.relative_path,
                    "test_source": repro.test_source,
                },
            )

        if cycle and outcome.output and contract.agent_profile == "kira.expected_behavior":
            from core.product_model.defects.schemas import ExpectedBehaviorProposal

            eb_proposal = ExpectedBehaviorProposal.model_validate(outcome.output)
            await self._artifacts.put(
                session,
                project_id=cycle.project_id,
                delivery_cycle_id=cycle.id,
                execution_id=execution.id,
                kind="EXPECTED_BEHAVIOR",
                schema_name="ExpectedBehaviorProposal",
                schema_version="1",
                content=eb_proposal.model_dump(mode="json"),
            )

        if cycle and outcome.output and contract.agent_profile == "warden.root_cause":
            from core.product_model.defects.schemas import RootCauseHypothesis

            raw_hyp = outcome.output.get("hypothesis") if isinstance(outcome.output, dict) else None
            hypothesis = RootCauseHypothesis.model_validate(raw_hyp or outcome.output)
            await self._artifacts.put(
                session,
                project_id=cycle.project_id,
                delivery_cycle_id=cycle.id,
                execution_id=execution.id,
                kind="ROOT_CAUSE",
                schema_name="RootCauseHypothesis",
                schema_version="1",
                content=hypothesis.model_dump(mode="json"),
            )

        if cycle and outcome.output and contract.agent_profile == "atlas.propose_architecture":
            from agents.atlas.schemas import ArchitectureProposal

            arch_proposal = ArchitectureProposal.model_validate(outcome.output)
            await self._artifacts.put(
                session,
                project_id=cycle.project_id,
                delivery_cycle_id=cycle.id,
                execution_id=execution.id,
                kind="ARCHITECTURE_PROPOSAL",
                schema_name="ArchitectureProposal",
                schema_version="1",
                content=arch_proposal.model_dump(mode="json"),
            )
            await append_domain_event(
                session,
                aggregate_type="artifact",
                aggregate_id=execution.id,
                event_type="artifact.created",
                payload={"kind": "ARCHITECTURE_PROPOSAL", "execution_id": str(execution.id)},
                actor_id=ctx.actor.id,
                correlation_id=ctx.correlation_id,
                project_id=cycle.project_id,
                delivery_cycle_id=cycle.id,
            )

        if cycle and outcome.output and contract.agent_profile == "kira.implementation_spec":
            from agents.kira.schemas import ImplementationSpecDraft

            draft = ImplementationSpecDraft.model_validate(outcome.output)
            await self._artifacts.put(
                session,
                project_id=cycle.project_id,
                delivery_cycle_id=cycle.id,
                execution_id=execution.id,
                kind="IMPLEMENTATION_SPEC_DRAFT",
                schema_name="ImplementationSpecDraft",
                schema_version="1",
                content=draft.model_dump(mode="json"),
            )
            await append_domain_event(
                session,
                aggregate_type="artifact",
                aggregate_id=execution.id,
                event_type="artifact.created",
                payload={"kind": "IMPLEMENTATION_SPEC_DRAFT", "execution_id": str(execution.id)},
                actor_id=ctx.actor.id,
                correlation_id=ctx.correlation_id,
                project_id=cycle.project_id,
                delivery_cycle_id=cycle.id,
            )

        if cycle and outcome.output and contract.agent_profile == "kira.task_plan":
            from agents.kira.schemas import TaskPlan

            plan = TaskPlan.model_validate(outcome.output)
            await self._artifacts.put(
                session,
                project_id=cycle.project_id,
                delivery_cycle_id=cycle.id,
                execution_id=execution.id,
                kind="TASK_PLAN",
                schema_name="TaskPlan",
                schema_version="1",
                content=plan.model_dump(mode="json"),
            )
            await append_domain_event(
                session,
                aggregate_type="artifact",
                aggregate_id=execution.id,
                event_type="artifact.created",
                payload={"kind": "TASK_PLAN", "execution_id": str(execution.id)},
                actor_id=ctx.actor.id,
                correlation_id=ctx.correlation_id,
                project_id=cycle.project_id,
                delivery_cycle_id=cycle.id,
            )

        if cycle and outcome.output and contract.agent_profile == "diagnostic.structured_echo":
            DiagnosticSummary.model_validate(outcome.output)
            await self._artifacts.put(
                session,
                project_id=cycle.project_id,
                delivery_cycle_id=cycle.id,
                execution_id=execution.id,
                kind="DIAGNOSTIC_SUMMARY",
                schema_name="DiagnosticSummary",
                schema_version="1",
                content=outcome.output,
            )
            await append_domain_event(
                session,
                aggregate_type="artifact",
                aggregate_id=execution.id,
                event_type="artifact.created",
                payload={"kind": "DIAGNOSTIC_SUMMARY", "execution_id": str(execution.id)},
                actor_id=ctx.actor.id,
                correlation_id=ctx.correlation_id,
                project_id=cycle.project_id,
                delivery_cycle_id=cycle.id,
            )

        if cycle and outcome.output and contract.agent_profile == "orchestrator.converse":
            from agents.orchestrator.schemas import OrchestratorTurn

            from core.domain.actors.models import Actor
            from core.orchestrator.models import OrchestratorSession
            from core.orchestrator.service import OrchestratorService

            turn = OrchestratorTurn.model_validate(outcome.output)
            payload = contract_payload or {}
            session_id_raw = payload.get("orchestrator_session_id")
            orch = None
            if session_id_raw:
                orch = await session.get(OrchestratorSession, uuid.UUID(str(session_id_raw)))
            operator = ctx.actor
            if orch is not None:
                owner = await session.get(Actor, orch.actor_id)
                if owner is not None:
                    operator = owner
            await self._artifacts.put(
                session,
                project_id=cycle.project_id,
                delivery_cycle_id=cycle.id,
                execution_id=execution.id,
                kind="ORCHESTRATOR_TURN",
                schema_name="OrchestratorTurn",
                schema_version="1",
                content=turn.model_dump(mode="json"),
            )
            if orch is not None:
                await OrchestratorService().complete_turn(
                    session,
                    orch,
                    execution_id=execution.id,
                    turn=turn,
                    ctx=CommandContext(
                        actor=operator,
                        correlation_id=ctx.correlation_id,
                        idempotency_key=ctx.idempotency_key,
                        command_log_id=ctx.command_log_id,
                    ),
                )

        if (
            cycle
            and outcome.output
            and contract.deterministic_executor == "brownfield.run_existing_tests"
        ):
            await self._artifacts.put(
                session,
                project_id=cycle.project_id,
                delivery_cycle_id=cycle.id,
                execution_id=execution.id,
                kind="TEST_RUN",
                schema_name="BrownfieldTestRun",
                schema_version="1",
                content=outcome.output,
            )

        if cycle and outcome.output and contract.agent_profile == "scout.survey":
            from agents.scout.schemas import RepositorySurvey

            survey = RepositorySurvey.model_validate(outcome.output)
            await self._artifacts.put(
                session,
                project_id=cycle.project_id,
                delivery_cycle_id=cycle.id,
                execution_id=execution.id,
                kind="REPOSITORY_SURVEY",
                schema_name="RepositorySurvey",
                schema_version="1",
                content=survey.model_dump(mode="json"),
            )

        if cycle and outcome.output and contract.agent_profile == "scout.recover_feature":
            from agents.scout.schemas import RecoveredFeatureSpec

            recovered = RecoveredFeatureSpec.model_validate(outcome.output)
            await self._artifacts.put(
                session,
                project_id=cycle.project_id,
                delivery_cycle_id=cycle.id,
                execution_id=execution.id,
                kind="RECOVERED_FEATURE_SPEC",
                schema_name="RecoveredFeatureSpec",
                schema_version="1",
                content=recovered.model_dump(mode="json"),
            )

        if cycle and outcome.output:
            await self._put_missing_output_artifacts(session, cycle, execution, contract, outcome)

        await self._executions.transition(session, execution.id, "validate", ctx, lease_id=lease.id)
        from typing import Literal

        pre_phase: Literal["pre_commit", "post_commit", "all"] = (
            "pre_commit" if contract.work_type == WorkType.CODE_CHANGE else "all"
        )
        errors = await validate_required_outputs(session, execution, contract, phase=pre_phase)
        if errors:
            task = await session.get(Task, execution.task_id)
            await self._executions.transition(
                session,
                execution.id,
                "fail",
                ctx,
                lease_id=lease.id,
                payload={
                    "failure_class": "VALIDATION_FAILED",
                    "failure_detail": {"errors": errors},
                    "retriable": False,
                },
            )
            if task:
                await self._executions.sync_task_on_failure(session, execution, task, ctx)
            return

        await session.refresh(execution)
        if contract.work_type == WorkType.CODE_CHANGE:
            await self._executions.transition(
                session, execution.id, "commit", ctx, lease_id=lease.id
            )
            errors = await validate_required_outputs(
                session, execution, contract, phase="post_commit"
            )
            if errors:
                task = await session.get(Task, execution.task_id)
                await self._executions.transition(
                    session,
                    execution.id,
                    "fail",
                    ctx,
                    lease_id=lease.id,
                    payload={
                        "failure_class": "VALIDATION_FAILED",
                        "failure_detail": {"errors": errors},
                        "retriable": False,
                    },
                )
                if task:
                    await self._executions.sync_task_on_failure(session, execution, task, ctx)
                await self._cleanup_execution_workspace(session, execution.id, ctx, retain=True)
                return

        if contract.agent_profile == "kira.decompose" and execution.output:
            await self._persist_kira_proposal(session, execution, ctx)

        if contract.work_type == WorkType.CODE_CHANGE:
            from core.intelligence.code_index.canonical_service import CanonicalIndexService

            with suppress(Exception):
                await CanonicalIndexService().build_candidate(session, execution.id, ctx)

        if contract.work_type == WorkType.RELEASE and execution.output:
            from core.release.completion import ReleaseCompletionService

            await ReleaseCompletionService().finalize_if_release_execution(
                session,
                execution,
                contract,
                execution.output,
                ctx,
            )

        if contract.work_type == WorkType.INTEGRATION and execution.output:
            from core.domain.exceptions import DomainError
            from core.integration.completion import IntegrationCompletionService

            try:
                await IntegrationCompletionService().promote_if_validating(
                    session,
                    execution,
                    contract,
                    execution.output,
                    ctx,
                )
            except DomainError as exc:
                task = await session.get(Task, execution.task_id)
                await self._executions.transition(
                    session,
                    execution.id,
                    "fail",
                    ctx,
                    lease_id=lease.id,
                    payload={
                        "failure_class": exc.code,
                        "failure_detail": exc.details or {"message": exc.message},
                        "retriable": False,
                    },
                )
                if task:
                    await self._executions.sync_task_on_failure(session, execution, task, ctx)
                return

        if (
            contract.agent_profile
            in {
                "kira.defect_triage",
                "sentinel.reproduce",
                "kira.expected_behavior",
                "warden.root_cause",
            }
            and execution.output
        ):
            from core.domain.exceptions import DomainError
            from core.product_model.defects.completion import BugFixCompletionService

            try:
                await BugFixCompletionService().persist_from_execution(
                    session,
                    execution,
                    contract.agent_profile or "",
                    execution.output,
                    ctx,
                )
            except DomainError as exc:
                task = await session.get(Task, execution.task_id)
                await self._executions.transition(
                    session,
                    execution.id,
                    "fail",
                    ctx,
                    lease_id=lease.id,
                    payload={
                        "failure_class": exc.code,
                        "failure_detail": exc.details or {"message": exc.message},
                        "retriable": False,
                    },
                )
                if task:
                    await self._executions.sync_task_on_failure(session, execution, task, ctx)
                return

        if (
            contract.agent_profile
            in {
                "kira.change_interpret",
                "atlas.architecture_delta",
            }
            and execution.output
        ):
            from core.domain.exceptions import DomainError
            from core.product_model.changes.completion import FeatureChangeCompletionService

            try:
                await FeatureChangeCompletionService().persist_from_execution(
                    session,
                    execution,
                    contract.agent_profile or "",
                    execution.output,
                    ctx,
                )
            except DomainError as exc:
                task = await session.get(Task, execution.task_id)
                await self._executions.transition(
                    session,
                    execution.id,
                    "fail",
                    ctx,
                    lease_id=lease.id,
                    payload={
                        "failure_class": exc.code,
                        "failure_detail": exc.details or {"message": exc.message},
                        "retriable": False,
                    },
                )
                if task:
                    await self._executions.sync_task_on_failure(session, execution, task, ctx)
                return

        if (
            contract.agent_profile
            in {
                "atlas.propose_architecture",
                "kira.implementation_spec",
                "kira.task_plan",
            }
            and execution.output
        ):
            from core.domain.exceptions import DomainError
            from core.planning.completion import PlanningCompletionService

            try:
                await PlanningCompletionService().persist_from_execution(
                    session,
                    execution,
                    contract.agent_profile or "",
                    execution.output,
                    ctx,
                )
            except DomainError as exc:
                task = await session.get(Task, execution.task_id)
                await self._executions.transition(
                    session,
                    execution.id,
                    "fail",
                    ctx,
                    lease_id=lease.id,
                    payload={
                        "failure_class": exc.code,
                        "failure_detail": exc.details or {"message": exc.message},
                        "retriable": False,
                    },
                )
                if task:
                    await self._executions.sync_task_on_failure(session, execution, task, ctx)
                return

        if (
            contract.agent_profile
            in {
                "warden.review",
                "sentinel.plan",
                "sentinel.summarize",
            }
            and execution.output
        ):
            from core.assurance.completion import AssuranceCompletionService

            await AssuranceCompletionService().persist_from_execution(
                session,
                execution,
                contract.agent_profile or "",
                execution.output,
                ctx,
            )

        if contract.deterministic_executor == "sentinel.execute":
            from core.assurance.completion import AssuranceCompletionService

            await AssuranceCompletionService().after_deterministic_verification(
                session, execution, ctx
            )

        if (
            contract.deterministic_executor in {"reproduction.run", "reproduction.regression"}
            and execution.output
        ):
            from core.product_model.defects.completion import BugFixCompletionService

            await BugFixCompletionService().after_reproduction_run(
                session, execution, execution.output, ctx
            )

        if contract.deterministic_executor == "brownfield.run_existing_tests" and execution.output:
            from core.intelligence.recovered_specs.completion import BrownfieldCompletionService

            await BrownfieldCompletionService().after_existing_tests(
                session, execution, execution.output, ctx
            )

        if contract.agent_profile == "sentinel.characterize" and execution.output:
            from core.intelligence.baselines.completion import BaselineCompletionService

            await BaselineCompletionService().persist_characterization(
                session,
                execution,
                contract,
                execution.output,
                ctx,
            )

        if contract.agent_profile in {"scout.survey", "scout.recover_feature"} and execution.output:
            from core.intelligence.recovered_specs.completion import BrownfieldCompletionService

            await BrownfieldCompletionService().persist_from_execution(
                session,
                execution,
                contract.agent_profile or "",
                execution.output,
                ctx,
            )

        await self._executions.transition(session, execution.id, "complete", ctx, lease_id=lease.id)
        from core.tools.tokens import revoke_tokens_for_execution

        await revoke_tokens_for_execution(session, execution.id)
        await self._cleanup_execution_workspace(session, execution.id, ctx, retain=False)
        await self._executions.sync_task_on_execution_complete(session, execution, ctx)
        await self._unblock_dependents(session, execution.task_id)

        if contract.agent_profile in {"scout.survey", "scout.recover_feature"} and execution.output:
            from core.intelligence.recovered_specs.completion import BrownfieldCompletionService

            # Runs after the task sync so this task no longer counts as pending.
            await BrownfieldCompletionService().try_finalize_recovery(
                session, execution.delivery_cycle_id, ctx
            )

        if contract.agent_profile == "sentinel.characterize":
            from core.intelligence.baselines.orchestrator import BaselineOrchestrator

            await BaselineOrchestrator().schedule_execution_if_characterized(
                session, execution.delivery_cycle_id, ctx
            )

    async def _put_missing_output_artifacts(
        self,
        session: AsyncSession,
        cycle: DeliveryCycle,
        execution: Execution,
        contract: TaskContractBody,
        outcome: ExecutorOutcome,
    ) -> None:
        """Record the executor output as each required artifact kind not already written."""
        from sqlalchemy import select

        from core.domain.artifacts.models import Artifact

        if outcome.output is None:
            return
        for name in contract.required_outputs:
            if not name.startswith("artifact:"):
                continue
            kind = name.split(":", 1)[1]
            if kind not in _OUTPUT_ARTIFACT_KINDS:
                continue
            existing = await session.execute(
                select(Artifact.id).where(
                    Artifact.execution_id == execution.id, Artifact.kind == kind
                )
            )
            if existing.first() is not None:
                continue
            await self._artifacts.put(
                session,
                project_id=cycle.project_id,
                delivery_cycle_id=cycle.id,
                execution_id=execution.id,
                kind=kind,
                schema_name=kind,
                schema_version="1",
                content=outcome.output,
            )

    async def _cleanup_execution_workspace(
        self,
        session: AsyncSession,
        execution_id: uuid.UUID,
        ctx: CommandContext,
        *,
        retain: bool,
    ) -> None:
        from sqlalchemy import select

        from core.domain.execution_workspaces.models import ExecutionWorkspace
        from core.execution.worktrees.manager import WorktreeManager

        ws = await session.execute(
            select(ExecutionWorkspace).where(ExecutionWorkspace.execution_id == execution_id)
        )
        workspace = ws.scalar_one_or_none()
        if workspace is not None:
            await WorktreeManager().remove(session, workspace, retain=retain, actor_id=ctx.actor.id)

    async def _persist_kira_proposal(
        self,
        session: AsyncSession,
        execution: Execution,
        ctx: CommandContext,
    ) -> None:
        from agents.kira.schemas import ProductDecomposition

        from core.domain.tasks.models import Task
        from core.product_model.service import ProductModelService

        task = await session.get(Task, execution.task_id)
        if task is None or task.governing_ref_id is None:
            return
        cycle = await session.get(DeliveryCycle, execution.delivery_cycle_id)
        if cycle is None:
            return
        proposal = ProductDecomposition.model_validate(execution.output)
        await ProductModelService().persist_proposal(
            session,
            project_id=cycle.project_id,
            delivery_cycle_id=cycle.id,
            product_source_version_id=task.governing_ref_id,
            execution_id=execution.id,
            proposal=proposal,
            ctx=ctx,
        )

    async def _canonical_orchestrator_turn(
        self,
        session: AsyncSession,
        raw_output: dict[str, Any],
        contract_payload: dict[str, Any] | None,
        ctx: CommandContext,
    ) -> object:
        from agents.orchestrator.schemas import OrchestratorTurn
        from sqlalchemy import select

        from core.commands.catalog import export_command_catalog
        from core.domain.actors.models import Actor
        from core.orchestrator.models import OrchestratorSession
        from core.orchestrator.service import fallback_turn
        from core.orchestrator.validator import OrchestratorValidationError, validate_turn

        turn = OrchestratorTurn.model_validate(raw_output)
        payload = contract_payload or {}
        session_id_raw = payload.get("orchestrator_session_id")
        validate_actor = ctx.actor
        orch = None
        if session_id_raw:
            orch = await session.get(OrchestratorSession, uuid.UUID(str(session_id_raw)))
            if orch is not None:
                owner = await session.get(Actor, orch.actor_id)
                if owner is not None:
                    validate_actor = owner
        actor_roles = payload.get("actor_roles") or []
        if actor_roles and list(validate_actor.roles or []) != list(actor_roles):
            validate_actor = Actor(
                id=validate_actor.id,
                kind=validate_actor.kind,
                name=validate_actor.name,
                roles=list(actor_roles),
            )
        open_ids: set[str] = set()
        if orch is not None and orch.delivery_cycle_id is not None:
            from core.domain.enums import ClarificationStatus
            from core.domain.executions.models import Clarification

            rows = await session.execute(
                select(Clarification.id).where(
                    Clarification.delivery_cycle_id == orch.delivery_cycle_id,
                    Clarification.status == ClarificationStatus.OPEN,
                )
            )
            open_ids = {str(cid) for cid in rows.scalars()}
        try:
            return validate_turn(turn, actor=validate_actor, open_clarification_ids=open_ids)
        except OrchestratorValidationError:
            return fallback_turn(export_command_catalog())

    async def _unblock_dependents(self, session: AsyncSession, task_id: uuid.UUID) -> None:
        from sqlalchemy import select

        from core.domain.tasks.models import TaskDependency

        deps = await session.execute(
            select(TaskDependency).where(TaskDependency.depends_on_task_id == task_id)
        )
        for dep in deps.scalars():
            await self._tasks.on_dependency_completed(session, dep.task_id)
