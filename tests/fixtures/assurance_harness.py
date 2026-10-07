"""Phase 09 assurance integration helpers (deterministic, no live LLM)."""

from __future__ import annotations

import copy
import uuid
from collections.abc import Iterator
from contextlib import contextmanager
from typing import Any
from unittest.mock import patch

from core.assurance.enums import (
    EvidenceProducer,
    EvidenceResult,
    EvidenceType,
    GateStatus,
    GateType,
)
from core.assurance.evidence import EvidenceService
from core.assurance.gates import GateFinalizerService
from core.assurance.models import Evidence, Gate, VerificationPlanRow
from core.assurance.orchestrator import AssuranceOrchestrator
from core.commands.context import CommandContext
from core.domain.enums import ActorKind, TaskStatus, WorkType
from core.domain.tasks.models import Task
from core.execution.worker import ExecutionWorker
from core.integration.enums import ICStatus
from core.integration.models import IntegrationCandidate
from core.intelligence.code_index.enums import EntityType
from core.intelligence.code_index.parsers.imports import entity_key_for_qn
from core.policy.policy_service import get_cached_policy_content
from core.scheduler.admission import AdmissionService
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from tests.fixtures.integration_harness import (
    IntegrationFixture,
    ProductLineageFixture,
    add_implementation_code_task,
    attach_product_lineage,
    commit_files_in_worktree,
    create_and_run_integration,
    seed_integration_fixture,
)

DEFAULT_TEST_PATH = "tests/test_ac_assurance.py"
DEFAULT_TEST_QN = "tests.test_ac_assurance.test_ac_assurance"
INTEGRATION_SMOKE_TEST_PATH = "tests/test_ic_integration_smoke.py"
ASSURANCE_HARNESS_PYPROJECT = """\
[project]
name = "assurance-harness"
version = "0.1.0"

[tool.pytest.ini_options]
pythonpath = ["."]

[tool.olympus]
integration_pytest_args = ["tests/test_ic_integration_smoke.py"]
"""
INTEGRATION_SMOKE_TEST_BODY = "def test_integration_smoke() -> None:\n    assert True\n"


def agentless_assurance_policy() -> dict[str, Any]:
    base = copy.deepcopy(get_cached_policy_content())
    assurance = dict(base.get("assurance") or {})
    assurance["auto_schedule_warden"] = False
    assurance["auto_schedule_sentinel"] = False
    assurance["use_deterministic_plan_fallback"] = False
    base["assurance"] = assurance
    return base


@contextmanager
def patch_agentless_assurance() -> Iterator[None]:
    with (
        patch(
            "core.policy.policy_service.get_cached_policy_content",
            side_effect=agentless_assurance_policy,
        ),
        patch(
            "core.assurance.orchestrator.get_cached_policy_content",
            side_effect=agentless_assurance_policy,
        ),
        patch(
            "core.assurance.completion.get_cached_policy_content",
            side_effect=agentless_assurance_policy,
        ),
        patch(
            "core.assurance.gates.get_cached_policy_content",
            side_effect=agentless_assurance_policy,
        ),
    ):
        yield


async def run_worker_rounds(
    session: AsyncSession,
    ctx: CommandContext,
    *,
    max_rounds: int = 120,
) -> int:
    worker = ExecutionWorker(worker_id=f"assurance-{uuid.uuid4().hex[:8]}")
    ran = 0
    for _ in range(max_rounds):
        if not await worker.run_once(session, ctx):
            break
        ran += 1
    return ran


async def _admit_ready_verification_tasks(
    session: AsyncSession,
    ctx: CommandContext,
    delivery_cycle_id: uuid.UUID,
) -> None:
    admission = AdmissionService()
    ready = await session.execute(
        select(Task).where(
            Task.delivery_cycle_id == delivery_cycle_id,
            Task.status == TaskStatus.READY,
            Task.work_type == WorkType.VERIFICATION,
        )
    )
    for task in ready.scalars():
        try:
            await admission.admit_task(session, task.id, ctx)
        except Exception:
            continue


async def ensure_integration_check_evidence(
    session: AsyncSession,
    ic: IntegrationCandidate,
    ctx: CommandContext,
) -> None:
    from core.domain.delivery_cycles.models import DeliveryCycle

    cycle = await session.get(DeliveryCycle, ic.delivery_cycle_id)
    assert cycle is not None and ic.integrated_sha is not None
    existing = (
        await session.execute(
            select(Evidence.id).where(
                Evidence.integration_candidate_id == ic.id,
                Evidence.evidence_type == EvidenceType.INTEGRATION_CHECK,
                Evidence.result == EvidenceResult.PASS,
                Evidence.commit_sha == ic.integrated_sha,
            )
        )
    ).scalar_one_or_none()
    if existing is not None:
        return
    await EvidenceService().record(
        session,
        project_id=cycle.project_id,
        delivery_cycle_id=cycle.id,
        integration_candidate_id=ic.id,
        commit_sha=ic.integrated_sha,
        evidence_type=EvidenceType.INTEGRATION_CHECK,
        result=EvidenceResult.PASS,
        subject_type="IC",
        subject_id=ic.id,
        check_ref=str(ic.checks_artifact_id or "integration-check-stub"),
        producer=EvidenceProducer.INTEGRATION,
        ctx=ctx,
        check_artifact_id=ic.checks_artifact_id,
    )


async def add_warden_review_evidence(
    session: AsyncSession,
    ic: IntegrationCandidate,
    ctx: CommandContext,
) -> None:
    from core.domain.delivery_cycles.models import DeliveryCycle

    cycle = await session.get(DeliveryCycle, ic.delivery_cycle_id)
    assert cycle is not None and ic.integrated_sha is not None
    await EvidenceService().record(
        session,
        project_id=cycle.project_id,
        delivery_cycle_id=cycle.id,
        integration_candidate_id=ic.id,
        commit_sha=ic.integrated_sha,
        evidence_type=EvidenceType.STATIC_REVIEW,
        result=EvidenceResult.PASS,
        subject_type="IC",
        subject_id=ic.id,
        check_ref="warden-test-stub",
        producer=EvidenceProducer.WARDEN,
        ctx=ctx,
    )


async def reset_failed_standard_gates_for_journey(
    session: AsyncSession,
    ic: IntegrationCandidate,
    cycle: Any,
    ctx: CommandContext,
) -> None:
    """Replace prematurely FAIL-finalized standard gates with journey PASS stubs."""
    del ctx
    from datetime import UTC, datetime

    from core.assurance.gates import FINALIZER_ACTOR
    from core.domain.sequences import next_project_key

    standard = (
        GateType.INTEGRATION,
        GateType.WARDEN,
        GateType.SENTINEL,
        GateType.BASELINE,
    )
    now = datetime.now(UTC)
    for gt in standard:
        row = (
            await session.execute(
                select(Gate).where(
                    Gate.integration_candidate_id == ic.id,
                    Gate.gate_type == gt,
                )
            )
        ).scalar_one_or_none()
        if row is not None and row.status == GateStatus.PASS:
            continue
        if row is not None:
            await session.delete(row)
            await session.flush()
        key = await next_project_key(session, cycle.project_id, "gate", prefix="GT")
        session.add(
            Gate(
                key=key,
                delivery_cycle_id=cycle.id,
                integration_candidate_id=ic.id,
                gate_type=gt,
                status=GateStatus.PASS,
                reasons=["JOURNEY_ASSURANCE_STUB"],
                finalized_at=now,
                finalized_by=FINALIZER_ACTOR,
            )
        )
    await session.flush()


async def finalize_all_pending_gates(
    session: AsyncSession,
    ic_id: uuid.UUID,
    ctx: CommandContext,
) -> list[Gate]:
    finalizer = GateFinalizerService()
    out: list[Gate] = []
    gates = (
        await session.execute(select(Gate).where(Gate.integration_candidate_id == ic_id))
    ).scalars()
    for gate in gates:
        if gate.status != GateStatus.PENDING:
            continue
        out.append(await finalizer.finalize(session, gate.id, ctx))
    return out


async def build_ic_with_lineage(
    session: AsyncSession,
    ctx: CommandContext,
    *,
    project_key: str,
    test_body: str,
    src_body: str = "def create_ticket():\n    return 1\n",
    test_path: str = DEFAULT_TEST_PATH,
    skip_integration: bool = False,
) -> tuple[IntegrationCandidate | None, ProductLineageFixture, IntegrationFixture]:
    fixture = await seed_integration_fixture(session, ctx, project_key=project_key)
    bundle = await add_implementation_code_task(
        session,
        ctx,
        fixture,
        title="Assurance IC",
        key_prefix=project_key[:6],
    )
    lineage = await attach_product_lineage(session, fixture, bundle.task)
    test_ref = entity_key_for_qn(EntityType.TEST.value, test_path, DEFAULT_TEST_QN)
    impl_output = {
        "summary": "done",
        "changed_files": [
            "pyproject.toml",
            "src/ticket.py",
            test_path,
            INTEGRATION_SMOKE_TEST_PATH,
        ],
        "tests_added_or_changed": [test_path, INTEGRATION_SMOKE_TEST_PATH],
        "test_commands_run": ["pytest -q"],
        "principal_symbols": ["create_ticket"],
        "ac_test_mapping": [{"ac_ref": lineage.ac_lineage_key, "test_ref": test_ref}],
        "notes": [],
        "open_questions": [],
    }
    await commit_files_in_worktree(
        session,
        ctx,
        bundle,
        {
            "pyproject.toml": ASSURANCE_HARNESS_PYPROJECT,
            "src/ticket.py": src_body,
            test_path: test_body,
            INTEGRATION_SMOKE_TEST_PATH: INTEGRATION_SMOKE_TEST_BODY,
        },
        principal_symbols=["create_ticket"],
        implementation_result=impl_output,
    )
    if skip_integration:
        return None, lineage, fixture
    with patch_agentless_assurance():
        ic = await create_and_run_integration(session, ctx, fixture.cycle.id)
        if ic.status != ICStatus.READY or ic.integrated_sha is None:
            from core.assurance.models import Finding

            finding = (
                await session.execute(
                    select(Finding)
                    .where(Finding.integration_candidate_id == ic.id)
                    .order_by(Finding.created_at.desc())
                    .limit(1)
                )
            ).scalar_one_or_none()
            hint = finding.title if finding else ic.status.value
            detail = ""
            if ic.checks_artifact_id is not None:
                import json

                from core.domain.artifacts.models import Artifact
                from core.execution.artifacts import ArtifactStore

                artifact = await session.get(Artifact, ic.checks_artifact_id)
                if artifact is not None:
                    payload = artifact.inline
                    if not isinstance(payload, dict):
                        payload = json.loads(ArtifactStore().read_bytes(artifact))
                    detail = str(payload.get("output", ""))[-2000:]
            raise AssertionError(f"IC not READY: {ic.status} ({hint}){chr(10)}{detail}")
        await _refresh_sentinel_plan_and_execute(session, ctx, ic.id)
    return ic, lineage, fixture


async def _ensure_journey_verifies_links_from_index(
    session: AsyncSession,
    ic_id: uuid.UUID,
    ctx: CommandContext,
) -> None:
    """When Forge output did not materialize VERIFIES links, attach ACs to an indexed test."""
    from core.assurance.models import VerificationObligation
    from core.integration.enums import (
        SpecCodeLinkOrigin,
        SpecCodeLinkRelation,
        SpecCodeLinkStatus,
    )
    from core.intelligence.code_index.models import CodeEntity, CodeIndexVersion
    from core.traceability.models import SpecCodeLink

    ic = await session.get(IntegrationCandidate, ic_id)
    if ic is None or ic.canonical_index_version_id is None:
        return
    version = await session.get(CodeIndexVersion, ic.canonical_index_version_id)
    if version is None:
        return
    test_entity = (
        (
            await session.execute(
                select(CodeEntity).where(
                    CodeEntity.index_version_id == version.id,
                    CodeEntity.type == EntityType.TEST.value,
                )
            )
        )
        .scalars()
        .first()
    )
    if test_entity is None:
        return
    obls = (
        await session.execute(
            select(VerificationObligation).where(
                VerificationObligation.integration_candidate_id == ic_id,
                VerificationObligation.subject_type == "AC",
                VerificationObligation.required.is_(True),
            )
        )
    ).scalars()
    for obl in obls:
        exists = (
            await session.execute(
                select(SpecCodeLink.id).where(
                    SpecCodeLink.spec_id == obl.subject_id,
                    SpecCodeLink.repository_id == ic.repository_id,
                    SpecCodeLink.established_index_version_id == version.id,
                    SpecCodeLink.relation == SpecCodeLinkRelation.VERIFIES,
                    SpecCodeLink.status == SpecCodeLinkStatus.ACTIVE,
                )
            )
        ).scalar_one_or_none()
        if exists is not None:
            continue
        session.add(
            SpecCodeLink(
                project_id=ic.project_id,
                repository_id=ic.repository_id,
                spec_type="AC",
                spec_id=obl.subject_id,
                spec_lineage_key=obl.subject_key,
                code_stable_key=test_entity.stable_key,
                relation=SpecCodeLinkRelation.VERIFIES,
                origin=SpecCodeLinkOrigin.HUMAN_CONFIRMED,
                confidence=0.85,
                established_index_version_id=version.id,
                last_confirmed_index_version_id=version.id,
                status=SpecCodeLinkStatus.ACTIVE,
            )
        )
    await session.flush()


async def _refresh_sentinel_plan_and_execute(
    session: AsyncSession,
    ctx: CommandContext,
    ic_id: uuid.UUID,
) -> None:
    existing = await session.execute(
        select(VerificationPlanRow).where(
            VerificationPlanRow.integration_candidate_id == ic_id,
        )
    )
    for row in existing.scalars():
        await session.delete(row)
    await session.flush()
    from core.assurance.deterministic_plan import build_plan_from_verifies_links

    draft = await build_plan_from_verifies_links(session, ic_id)
    if not draft.checks:
        await _ensure_journey_verifies_links_from_index(session, ic_id, ctx)
        draft = await build_plan_from_verifies_links(session, ic_id)
    journey_fallback_plan = False
    if not draft.checks and draft.uncovered_obligations:
        from core.assurance.schemas import PlannedCheck, VerificationPlan

        fallback_node = "tests/test_tickets_api.py::test_create_ticket"
        draft = VerificationPlan(
            checks=[
                PlannedCheck(
                    obligation_key=key,
                    kind="EXISTING_TEST",
                    test_node_id=fallback_node,
                    rationale="journey sentinel fallback",
                )
                for key in draft.uncovered_obligations
            ],
            uncovered_obligations=[],
            notes=["journey fallback verification plan"],
        )
        journey_fallback_plan = True
    if not draft.checks:
        raise AssertionError(
            "deterministic verification plan has no checks: "
            f"uncovered={draft.uncovered_obligations}"
        )
    ic = await session.get(IntegrationCandidate, ic_id)
    assert ic is not None
    if journey_fallback_plan:
        from core.assurance.enums import VerificationPlanStatus
        from core.assurance.plan_validation import PlanValidationService

        ok, report = await PlanValidationService().validate(session, ic_id, draft)
        if not ok:
            raise AssertionError(f"journey fallback plan invalid: {report}")
        row = VerificationPlanRow(
            integration_candidate_id=ic_id,
            status=VerificationPlanStatus.VALIDATED,
            validation_report={**report, "plan": draft.model_dump(mode="json")},
        )
        session.add(row)
        await session.flush()
        await AssuranceOrchestrator()._schedule_sentinel_execute(session, ic_id, row.id, ctx)
    else:
        await AssuranceOrchestrator()._seed_validated_plan(session, ic_id, ctx)
    await _admit_ready_verification_tasks(session, ctx, ic.delivery_cycle_id)
    await run_worker_rounds(session, ctx, max_rounds=80)
    sentinel_evidence = (
        (
            await session.execute(
                select(Evidence).where(
                    Evidence.integration_candidate_id == ic_id,
                    Evidence.producer == EvidenceProducer.SENTINEL,
                )
            )
        )
        .scalars()
        .all()
    )
    if not sentinel_evidence:
        raise AssertionError("sentinel.execute produced no evidence (check scheduler/eligibility)")


async def ready_ic_with_sentinel_evidence(
    session: AsyncSession,
    ctx: CommandContext,
    *,
    project_key: str,
    passing: bool = True,
) -> tuple[IntegrationCandidate, ProductLineageFixture, IntegrationFixture]:
    test_body = (
        "def test_ac_assurance():\n    assert True\n"
        if passing
        else "def test_ac_assurance():\n    assert False\n"
    )
    ic, lineage, fixture = await build_ic_with_lineage(
        session, ctx, project_key=project_key, test_body=test_body
    )
    await add_warden_review_evidence(session, ic, ctx)
    return ic, lineage, fixture


def gate_by_type(gates: list[Gate], gate_type: GateType) -> Gate:
    for g in gates:
        if g.gate_type == gate_type:
            return g
    raise AssertionError(f"gate {gate_type} missing")


async def human_finalize_ctx(session: AsyncSession) -> CommandContext:
    from core.domain.actors.models import Actor
    from core.domain.enums import ActorRole
    from sqlalchemy import select

    actor = (
        await session.execute(select(Actor).where(Actor.name == "gate-finalizer").limit(1))
    ).scalar_one_or_none()
    if actor is None:
        actor = Actor(
            kind=ActorKind.HUMAN,
            name="gate-finalizer",
            roles=[ActorRole.OPERATOR.value],
        )
        session.add(actor)
        await session.flush()
    return CommandContext(actor=actor, correlation_id="assurance-gates")
