"""Deterministic reproduction.run executor."""

from __future__ import annotations

import json
import tempfile
import uuid
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.assurance.enums import EvidenceProducer, EvidenceResult, EvidenceType
from core.assurance.models import Evidence
from core.assurance.reproduction.signature import (
    classify_junit_failure,
    extract_http_status_from_failure,
    match_signature,
)
from core.commands.context import CommandContext
from core.domain.actors.models import Actor
from core.domain.delivery_cycles.models import DeliveryCycle
from core.domain.enums import ActorKind
from core.domain.repositories.models import Repository, RepositoryWorkspace
from core.domain.sequences import next_project_key
from core.execution.artifacts import ArtifactStore
from core.execution.executors.base import ExecutionContext, ExecutorOutcome
from core.execution.worktrees.manager import WorktreeManager
from core.product_model.defects.models import Defect, Reproduction
from core.repositories.workspace_locator import WorkspaceLocator
from core.tools.handlers.test_runner import run_pytest_in_workspace
from core.traceability.models import RepositoryIndexPointer


def _parse_junit(path: Path) -> list[dict[str, Any]]:
    if not path.is_file():
        return []
    root = ET.parse(path).getroot()
    cases: list[dict[str, Any]] = []
    for case in root.iter("testcase"):
        nodeid = f"{case.get('classname', '')}::{case.get('name', '')}"
        failure = case.find("failure")
        error = case.find("error")
        failure_text = ""
        if failure is not None and failure.text:
            failure_text = failure.text
        if error is not None and error.text:
            failure_text = error.text
        failed = failure is not None or error is not None
        cases.append(
            {
                "nodeid": nodeid,
                "passed": not failed,
                "failure_text": failure_text,
                "error": error is not None,
            }
        )
    return cases


def _write_repro_conftest(repro_dir: Path) -> None:
    repro_dir.mkdir(parents=True, exist_ok=True)
    conftest = repro_dir / "conftest.py"
    if conftest.is_file():
        return
    conftest.write_text(
        """import logging

import app.models.ticket  # noqa: F401
import pytest
from app.db import Base, engine

Base.metadata.create_all(bind=engine)


@pytest.fixture(autouse=True)
def _capture_server_errors():
    records: list[str] = []
    handler = logging.Handler()
    handler.emit = lambda rec: records.append(rec.getMessage())  # type: ignore[method-assign]
    for name in ("uvicorn.error", "uvicorn", ""):
        log = logging.getLogger(name or None)
        log.addHandler(handler)
        log.setLevel(logging.ERROR)
    yield {"records": records}
""",
        encoding="utf-8",
    )


async def _load_test_source(session: AsyncSession, artifact_id: uuid.UUID) -> tuple[str, str]:
    from core.domain.artifacts.models import Artifact

    art = await session.get(Artifact, artifact_id)
    if art is None:
        raise ValueError("artifact missing")
    raw = ArtifactStore().read_bytes(art)
    payload = json.loads(raw.decode("utf-8"))
    return str(payload["relative_path"]), str(payload["test_source"])


async def run_reproduction(
    session: AsyncSession,
    ctx: ExecutionContext,
    command_ctx: CommandContext,
) -> ExecutorOutcome:
    body = ctx.contract_payload if isinstance(ctx.contract_payload, dict) else {}
    defect_id = uuid.UUID(str(body.get("defect_id")))
    phase = str(body.get("phase", "PRE_REPAIR"))
    artifact_id = uuid.UUID(str(body["artifact_id"]))
    commit_sha = str(body.get("commit_sha", ""))
    signature = body.get("observed_symptom_signature") or {}
    stability_runs = int(body.get("stability_runs", 2))

    defect = await session.get(Defect, defect_id)
    if defect is None:
        return ExecutorOutcome(status="FAILED", error_code="NOT_FOUND", error_message="defect")
    cycle = await session.get(DeliveryCycle, defect.delivery_cycle_id)
    if cycle is None or cycle.repository_id is None:
        return ExecutorOutcome(status="FAILED", error_code="CYCLE_NOT_READY", error_message="cycle")
    if not commit_sha:
        commit_sha = defect.affected_sha if phase == "PRE_REPAIR" else str(body.get("commit_sha"))
    repo = await session.get(Repository, cycle.repository_id)
    if repo is None:
        return ExecutorOutcome(status="FAILED", error_code="NOT_FOUND", error_message="repo")

    actor = (
        await session.execute(select(Actor).where(Actor.kind == ActorKind.SYSTEM).limit(1))
    ).scalar_one()
    await WorktreeManager().create_readonly(
        session,
        ctx.execution,
        cycle.repository_id,
        commit_sha,
        actor_id=actor.id,
        correlation_id=str(ctx.execution.id),
        project_id=cycle.project_id,
    )
    from core.domain.execution_workspaces.models import ExecutionWorkspace

    ws = (
        await session.execute(
            select(ExecutionWorkspace).where(ExecutionWorkspace.execution_id == ctx.execution.id)
        )
    ).scalar_one()
    canonical_ws = await session.get(RepositoryWorkspace, repo.workspace_id)
    assert canonical_ws is not None
    wt_path = WorkspaceLocator().resolve(canonical_ws.storage_backend, ws.logical_location)

    rel_path, test_source = await _load_test_source(session, artifact_id)
    repro_dir = wt_path / "tests" / "olympus_repro"
    _write_repro_conftest(repro_dir)
    target = repro_dir / Path(rel_path).name
    target.write_text(test_source, encoding="utf-8")

    cases: list[dict[str, Any]] = []
    pytest_payload: dict[str, Any] = {}
    stable = True
    for run_idx in range(max(1, stability_runs)):
        with tempfile.TemporaryDirectory() as tmp:
            junit = Path(tmp) / "junit.xml"
            pytest_args = [f"--junitxml={junit}", str(target.relative_to(wt_path))]
            try:
                import pytest_cov  # type: ignore[import-not-found]  # noqa: F401

                pytest_args = ["--cov=app", *pytest_args]
            except ImportError:
                pass
            pytest_payload = await run_pytest_in_workspace(
                wt_path,
                {
                    "runner": "pytest",
                    "args": pytest_args,
                },
            )
            run_cases = _parse_junit(junit)
            run_class, _ = classify_junit_failure(run_cases)
            if run_idx == 0:
                cases = run_cases
            if phase == "PRE_REPAIR" and run_class != "ASSERTION":
                stable = False
                break
            if phase == "POST_REPAIR" and run_class != "PASS":
                stable = False
                break

    outcome_class, failure_detail = classify_junit_failure(cases)
    signature_matched = False
    http_status: int | None = None
    if failure_detail and phase == "PRE_REPAIR":
        failure_text = str(failure_detail.get("failure_text", ""))
        http_status = extract_http_status_from_failure(failure_text)
        signature_matched = match_signature(
            signature,
            http_status=http_status,
            message=failure_text,
        )

    if phase == "PRE_REPAIR":
        reproduced = outcome_class == "ASSERTION" and signature_matched and stable
    elif phase == "POST_REPAIR":
        reproduced = outcome_class == "PASS" and stable
    else:
        reproduced = False

    store = ArtifactStore()
    junit_art = await store.put(
        session,
        project_id=cycle.project_id,
        delivery_cycle_id=cycle.id,
        execution_id=ctx.execution.id,
        kind="JUNIT",
        schema_name="junit",
        schema_version="1",
        content={"cases": cases},
        created_by_actor_id=command_ctx.actor.id,
    )

    from core.domain.artifacts.models import Artifact

    art = await session.get(Artifact, artifact_id)
    art_hash = art.content_hash if art else ""

    outcome = "REPRODUCED" if reproduced and phase == "PRE_REPAIR" else "NOT_REPRODUCED"
    if phase in {"POST_REPAIR", "REGRESSION_VALIDATION"}:
        outcome = "PASS" if outcome_class == "PASS" else "FAIL"

    repro = Reproduction(
        defect_id=defect.id,
        phase=phase,
        commit_sha=commit_sha,
        artifact_id=artifact_id,
        artifact_hash=art_hash,
        execution_id=ctx.execution.id,
        outcome=outcome,
        signature_matched=signature_matched,
        runs=stability_runs,
        junit_artifact_id=junit_art.id,
    )
    session.add(repro)
    await session.flush()

    evidence: Evidence | None = None
    if phase in {"PRE_REPAIR", "POST_REPAIR"}:
        ev_key = await next_project_key(session, cycle.project_id, "evidence", prefix="EV")
        ev_type = EvidenceType.REPRODUCTION
        ev_result = (
            EvidenceResult.FAIL
            if phase == "PRE_REPAIR" and reproduced
            else EvidenceResult.PASS
            if phase == "POST_REPAIR" and outcome_class == "PASS"
            else EvidenceResult.FAIL
        )
        if phase == "PRE_REPAIR" and not reproduced:
            ev_result = EvidenceResult.FAIL
        ic_raw = body.get("integration_candidate_id")
        ic_uuid = uuid.UUID(str(ic_raw)) if ic_raw else None
        evidence = Evidence(
            key=ev_key,
            project_id=cycle.project_id,
            delivery_cycle_id=cycle.id,
            integration_candidate_id=ic_uuid,
            commit_sha=commit_sha,
            evidence_type=ev_type,
            result=ev_result,
            subject_type="DEFECT",
            subject_id=defect.id,
            check_ref=str(target.relative_to(wt_path)),
            producer=EvidenceProducer.SYSTEM,
            execution_id=ctx.execution.id,
            details={
                "phase": phase,
                "reproduced": bool(reproduced and phase == "PRE_REPAIR"),
                "signature_matched": signature_matched,
                "artifact_hash": art_hash,
            },
        )
        session.add(evidence)
        await session.flush()
        repro.evidence_id = evidence.id

        if phase == "PRE_REPAIR" and reproduced:
            defect.status = "REPRODUCED"
        elif phase == "PRE_REPAIR":
            defect.status = "NOT_REPRODUCIBLE"

    from core.intelligence.impact.trace import persist_trace_correlation

    pointer = await session.get(RepositoryIndexPointer, cycle.repository_id)
    if pointer and pointer.canonical_index_version_id and phase == "PRE_REPAIR":
        await persist_trace_correlation(
            session,
            repro.id,
            pointer.canonical_index_version_id,
            cases,
            failure_detail,
            body.get("entry_route_key"),
        )

    output: dict[str, Any] = {
        "reproduction_id": str(repro.id),
        "outcome": outcome,
        "phase": phase,
        "reproduced": reproduced or (phase == "POST_REPAIR" and outcome_class == "PASS"),
        "signature_matched": signature_matched,
        "cases": cases,
        "pytest": pytest_payload,
        "evidence_id": str(evidence.id) if evidence else None,
    }
    return ExecutorOutcome(status="OUTPUT_PRODUCED", output=output)


async def run_regression_test(
    session: AsyncSession,
    ctx: ExecutionContext,
    command_ctx: CommandContext,
) -> ExecutorOutcome:
    body = ctx.contract_payload if isinstance(ctx.contract_payload, dict) else {}
    test_path = str(body["regression_test_path"]).strip().replace("\\", "/")
    if not test_path.endswith(".py"):
        return ExecutorOutcome(
            status="FAILED",
            error_code="INVALID_INPUT",
            error_message=f"regression_test_path must be a concrete test file: {test_path!r}",
        )
    commit_sha = str(body["commit_sha"])
    defect_id = uuid.UUID(str(body["defect_id"]))
    ic_raw = body.get("integration_candidate_id")
    ic_id = uuid.UUID(str(ic_raw)) if ic_raw else None

    defect = await session.get(Defect, defect_id)
    cycle = await session.get(DeliveryCycle, defect.delivery_cycle_id if defect else None)
    if cycle is None or cycle.repository_id is None:
        return ExecutorOutcome(status="FAILED", error_code="CYCLE_NOT_READY", error_message="cycle")
    repo = await session.get(Repository, cycle.repository_id)
    if repo is None:
        return ExecutorOutcome(status="FAILED", error_code="NOT_FOUND", error_message="repo")

    actor = (
        await session.execute(select(Actor).where(Actor.kind == ActorKind.SYSTEM).limit(1))
    ).scalar_one()
    await WorktreeManager().create_readonly(
        session,
        ctx.execution,
        cycle.repository_id,
        commit_sha,
        actor_id=actor.id,
        correlation_id=str(ctx.execution.id),
        project_id=cycle.project_id,
    )
    from core.domain.execution_workspaces.models import ExecutionWorkspace

    ws = (
        await session.execute(
            select(ExecutionWorkspace).where(ExecutionWorkspace.execution_id == ctx.execution.id)
        )
    ).scalar_one()
    canonical_ws = await session.get(RepositoryWorkspace, repo.workspace_id)
    assert canonical_ws is not None
    wt_path = WorkspaceLocator().resolve(canonical_ws.storage_backend, ws.logical_location)

    with tempfile.TemporaryDirectory() as tmp:
        junit = Path(tmp) / "junit.xml"
        result = await run_pytest_in_workspace(
            wt_path,
            {"runner": "pytest", "args": [f"--junitxml={junit}", test_path]},
        )
        cases = _parse_junit(junit)

    outcome_class, _ = classify_junit_failure(cases)
    passed = outcome_class == "PASS"
    phase = str(body.get("phase", "REGRESSION"))
    is_validation = phase == "REGRESSION_VALIDATION"

    if defect and ic_id and not is_validation and passed:
        ev_key = await next_project_key(session, cycle.project_id, "evidence", prefix="EV")
        evidence = Evidence(
            key=ev_key,
            project_id=cycle.project_id,
            delivery_cycle_id=cycle.id,
            integration_candidate_id=ic_id,
            commit_sha=commit_sha,
            evidence_type=EvidenceType.REGRESSION_TEST,
            result=EvidenceResult.PASS,
            subject_type="DEFECT",
            subject_id=defect.id,
            check_ref=test_path,
            producer=EvidenceProducer.SYSTEM,
            execution_id=ctx.execution.id,
            details={
                "regression_test_validated": False,
                "phase": phase,
            },
        )
        session.add(evidence)
        await session.flush()
    elif defect and ic_id and is_validation and not passed:
        ev_key = await next_project_key(session, cycle.project_id, "evidence", prefix="EV")
        validation_ev = Evidence(
            key=ev_key,
            project_id=cycle.project_id,
            delivery_cycle_id=cycle.id,
            integration_candidate_id=ic_id,
            commit_sha=commit_sha,
            evidence_type=EvidenceType.REGRESSION_TEST,
            result=EvidenceResult.PASS,
            subject_type="DEFECT",
            subject_id=defect.id,
            check_ref=test_path,
            producer=EvidenceProducer.SYSTEM,
            execution_id=ctx.execution.id,
            details={
                "phase": "REGRESSION_VALIDATION",
                "regression_test_validated": True,
            },
        )
        session.add(validation_ev)
        await session.flush()

    return ExecutorOutcome(
        status="OUTPUT_PRODUCED",
        output={
            "passed": passed,
            "cases": cases,
            "pytest": result,
            "phase": phase,
            "validation": is_validation,
        },
    )
