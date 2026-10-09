"""Execute baseline checks at repository SHA (evidence subject_type=BASELINE)."""

from __future__ import annotations

import tempfile
import uuid
import xml.etree.ElementTree as ET
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.assurance.enums import EvidenceProducer, EvidenceResult, EvidenceType
from core.assurance.evidence import EvidenceService
from core.assurance.pytest_node import junit_case_node_id, legacy_node_to_path
from core.commands.context import CommandContext
from core.domain.delivery_cycles.models import DeliveryCycle
from core.domain.enums import ActorKind, KnowledgeClass, KnowledgeItemStatus
from core.domain.repositories.models import Repository, RepositoryWorkspace
from core.execution.worktrees.manager import WorktreeManager
from core.intelligence.baselines.authored import load_authored_test, materialize
from core.intelligence.baselines.enums import BaselineCheckKind, BaselineStatus
from core.intelligence.baselines.models import BehavioralBaseline
from core.product_model.models import KnowledgeItem
from core.repositories.workspace_locator import WorkspaceLocator
from core.tools.handlers.test_runner import run_probe_in_workspace, run_pytest_in_workspace


def _parse_junit(path: Path, workspace: Path) -> dict[str, bool]:
    if not path.is_file():
        return {}
    root = ET.parse(path).getroot()
    out: dict[str, bool] = {}
    for case in root.iter("testcase"):
        nodeid = junit_case_node_id(workspace, case.get("classname", ""), case.get("name", ""))
        failed = case.find("failure") is not None or case.find("error") is not None
        out[nodeid] = not failed
    return out


class BaselineExecutionService:
    async def execute_proposed(
        self,
        session: AsyncSession,
        cycle_id: uuid.UUID,
        execution_id: uuid.UUID,
        ctx: CommandContext,
    ) -> list[BehavioralBaseline]:
        cycle = await session.get(DeliveryCycle, cycle_id)
        if cycle is None or cycle.repository_id is None or cycle.base_sha is None:
            raise ValueError("cycle not ready")
        rows = (
            (
                await session.execute(
                    select(BehavioralBaseline).where(
                        BehavioralBaseline.project_id == cycle.project_id,
                        BehavioralBaseline.status == BaselineStatus.PROPOSED,
                        BehavioralBaseline.established_sha == cycle.base_sha,
                    )
                )
            )
            .scalars()
            .all()
        )
        if not rows:
            return []
        from core.domain.actors.models import Actor
        from core.domain.executions.models import Execution

        execution = await session.get(Execution, execution_id)
        if execution is None:
            raise ValueError("execution missing")
        actor = (
            await session.execute(select(Actor).where(Actor.kind == ActorKind.SYSTEM).limit(1))
        ).scalar_one()
        await WorktreeManager().create_readonly(
            session,
            execution,
            cycle.repository_id,
            cycle.base_sha,
            actor_id=actor.id,
            correlation_id=str(execution_id),
            project_id=cycle.project_id,
        )
        from core.domain.execution_workspaces.models import ExecutionWorkspace

        ws = (
            await session.execute(
                select(ExecutionWorkspace).where(ExecutionWorkspace.execution_id == execution_id)
            )
        ).scalar_one()
        repo = await session.get(Repository, cycle.repository_id)
        assert repo and repo.workspace_id
        canonical_ws = await session.get(RepositoryWorkspace, repo.workspace_id)
        assert canonical_ws is not None
        wt_path = WorkspaceLocator().resolve(canonical_ws.storage_backend, ws.logical_location)
        evidence_svc = EvidenceService()
        for baseline in rows:
            authored = await load_authored_test(session, baseline)
            if authored is not None:
                materialize(wt_path, *authored)
            passed, details = await self._run_check(wt_path, baseline, authored)
            result = EvidenceResult.PASS if passed else EvidenceResult.FAIL
            ev_type = (
                EvidenceType.API_TEST
                if baseline.check_kind == BaselineCheckKind.API_PROBE
                else EvidenceType.UNIT_TEST
            )
            ev = await evidence_svc.record(
                session,
                project_id=cycle.project_id,
                delivery_cycle_id=cycle.id,
                integration_candidate_id=None,
                commit_sha=cycle.base_sha,
                evidence_type=ev_type,
                result=result,
                subject_type="BASELINE",
                subject_id=baseline.id,
                check_ref=baseline.check_ref,
                producer=EvidenceProducer.SENTINEL,
                ctx=ctx,
                execution_id=execution_id,
                details=details,
            )
            baseline.established_evidence_id = ev.id
            if passed:
                from core.domain.events.append import append_domain_event

                await append_domain_event(
                    session,
                    aggregate_type="baseline",
                    aggregate_id=baseline.id,
                    event_type="baseline.executed",
                    payload={"result": "PASS", "commit_sha": cycle.base_sha},
                    actor_id=ctx.actor.id,
                    correlation_id=ctx.correlation_id,
                    project_id=cycle.project_id,
                    delivery_cycle_id=cycle.id,
                )
            else:
                baseline.status = BaselineStatus.FAILED_AT_BASE
                await self._record_failure_uncertainty(session, cycle, baseline, ctx)
                from core.domain.events.append import append_domain_event

                await append_domain_event(
                    session,
                    aggregate_type="baseline",
                    aggregate_id=baseline.id,
                    event_type="baseline.failed_at_base",
                    payload={"check_ref": baseline.check_ref},
                    actor_id=ctx.actor.id,
                    correlation_id=ctx.correlation_id,
                    project_id=cycle.project_id,
                    delivery_cycle_id=cycle.id,
                )
            await session.flush()
        return list(rows)

    async def _run_check(
        self,
        wt_path: Path,
        baseline: BehavioralBaseline,
        authored: tuple[str, str] | None = None,
    ) -> tuple[bool, dict[str, object]]:
        if baseline.check_kind == BaselineCheckKind.API_PROBE:
            method, _, path = baseline.check_ref.partition(":")
            probe: dict[str, object] = {
                "method": method or "GET",
                "path": path or baseline.check_ref,
            }
            outcome = await run_probe_in_workspace(wt_path, {"probes": [probe]})
            return bool(outcome.get("passed")), {"probe": probe, "outcome": outcome}
        if baseline.check_kind == BaselineCheckKind.AUTHORED_TEST and authored is None:
            return False, {"error": "authored test code missing"}
        node = authored[0] if authored else legacy_node_to_path(wt_path, baseline.check_ref)
        with tempfile.TemporaryDirectory() as tmp:
            junit = Path(tmp) / "junit.xml"
            args = ["--junitxml=" + str(junit), node]
            result = await run_pytest_in_workspace(
                wt_path,
                {"runner": "pytest", "args": args},
            )
            cases = _parse_junit(junit, wt_path)
            if node in cases:
                passed = cases[node]
            else:
                selected = [v for k, v in cases.items() if k.startswith(node.split("::")[0])]
                passed = bool(selected) and all(selected) and bool(result.get("passed"))
            return passed, {"pytest": result, "cases": cases, "node": node}

    async def _record_failure_uncertainty(
        self,
        session: AsyncSession,
        cycle: DeliveryCycle,
        baseline: BehavioralBaseline,
        ctx: CommandContext,
    ) -> None:
        stmt = f"Baseline {baseline.lineage_key} failed at base SHA for check {baseline.check_ref}"
        item = KnowledgeItem(
            project_id=cycle.project_id,
            delivery_cycle_id=cycle.id,
            knowledge_class=KnowledgeClass.UNCERTAINTY,
            statement=stmt,
            subject_refs=[{"baseline_id": str(baseline.id)}],
            provenance={"origin": "BASELINE_EXECUTION"},
            evidence_refs=[],
            status=KnowledgeItemStatus.ACTIVE,
        )
        session.add(item)
        await session.flush()
