#!/usr/bin/env python3
"""Read-only MVP Acceptance Evaluator (Phase 19 §4.7)."""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import uuid
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

import httpx
from core.config.settings import clear_settings_cache, get_settings
from core.db.engine import create_async_engine_from_settings, dispose_engine
from core.db.session import create_session_factory, reset_session_factory
from core.domain.delivery_cycles.models import DeliveryCycle
from core.domain.enums import ProjectReadiness
from core.domain.executions.models import Execution
from core.domain.model_calls.models import ModelCall
from core.domain.projects.models import Project
from core.domain.tasks.models import Task
from core.release.enums import ReleaseStatus
from core.release.models import Release
from scripts.acceptance.dod_checks import build_dod_checks
from scripts.acceptance.models import AcceptanceCheck, MvpAcceptanceReport
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession


def _api_base() -> str:
    return os.environ.get("OLYMPUS_API_BASE", "http://127.0.0.1:8000").rstrip("/")


def _viewer_token() -> str:
    token = os.environ.get("OLYMPUS_VIEWER_TOKEN") or os.environ.get("OLYMPUS_HUMAN_TOKEN")
    if not token:
        raise SystemExit("Set OLYMPUS_VIEWER_TOKEN or OLYMPUS_HUMAN_TOKEN")
    return token


def _parse_fingerprints(raw: str | None) -> dict[str, tuple[str, str]]:
    if not raw:
        return {}
    data = json.loads(raw)
    out: dict[str, tuple[str, str]] = {}
    for key, val in data.items():
        if isinstance(val, list | tuple) and len(val) == 2:
            out[key] = (str(val[0]), str(val[1]))
    return out


async def _resolve_project_id(session: AsyncSession, project_arg: str) -> tuple[uuid.UUID, str]:
    try:
        pid = uuid.UUID(project_arg)
        project = await session.get(Project, pid)
        if project is None:
            raise SystemExit(f"project not found: {pid}")
        return pid, project.key
    except ValueError:
        row = (
            await session.execute(
                select(Project)
                .where(Project.key.ilike(f"{project_arg}%"))
                .order_by(Project.created_at.desc())
                .limit(1)
            )
        ).scalar_one_or_none()
        if row is None:
            raise SystemExit(f"no project matching key prefix {project_arg!r}") from None
        return row.id, row.key


async def _http_checks(project_id: uuid.UUID, token: str) -> list[AcceptanceCheck]:
    checks: list[AcceptanceCheck] = []
    async with httpx.AsyncClient(
        base_url=_api_base(),
        headers={"Authorization": f"Bearer {token}"},
        timeout=60.0,
    ) as client:
        methods_used: set[str] = set()

        async def get(path: str) -> httpx.Response:
            resp = await client.get(path)
            methods_used.add("GET")
            return resp

        proj = await get(f"/projects/{project_id}")
        checks.append(
            AcceptanceCheck(
                name="project_exists",
                source="STATUS_DOD",
                ok=proj.status_code == 200,
                evidence_refs=[f"GET /projects/{project_id}"],
                query="project row reachable",
                detail=proj.text[:200] if proj.status_code != 200 else None,
            )
        )
        if proj.status_code == 200:
            key = proj.json().get("key", "")
            checks.append(
                AcceptanceCheck(
                    name="supportdesk_project_key",
                    source="ARCH_26",
                    ok=key.upper().startswith("SUPPORTDESK"),
                    evidence_refs=[f"project.key={key}"],
                    query="PROJECT: SUPPORTDESK",
                )
            )

        lineage = await get(f"/projects/{project_id}/lineage")
        checks.append(
            AcceptanceCheck(
                name="product_to_code_lineage_queryable",
                source="STATUS_DOD",
                ok=lineage.status_code == 200,
                evidence_refs=[f"GET /projects/{project_id}/lineage"],
                query="lineage API",
            )
        )

        audit = await get(f"/projects/{project_id}/audit/verify")
        checks.append(
            AcceptanceCheck(
                name="audit_chain_valid",
                source="TECH_32",
                ok=audit.status_code == 200 and audit.json().get("valid", False),
                evidence_refs=[f"GET /projects/{project_id}/audit/verify"],
                query="audit/verify",
            )
        )

        assert "POST" not in methods_used and "PATCH" not in methods_used
        checks.append(
            AcceptanceCheck(
                name="evaluator_read_only",
                source="TECH_32",
                ok=methods_used <= {"GET"},
                evidence_refs=sorted(methods_used),
                query="HTTP methods used by evaluator",
            )
        )
    return checks


async def _db_checks(
    session: AsyncSession,
    project_id: uuid.UUID,
    *,
    fingerprints: dict[str, tuple[str, str]],
    chaos: bool,
) -> list[AcceptanceCheck]:
    checks: list[AcceptanceCheck] = []
    project = await session.get(Project, project_id)
    checks.append(
        AcceptanceCheck(
            name="project_readiness_ready_for_change",
            source="ARCH_26",
            ok=project is not None and project.readiness_state == ProjectReadiness.READY_FOR_CHANGE,
            evidence_refs=[f"projects.readiness_state={getattr(project, 'readiness_state', None)}"],
            query="READY_FOR_CHANGE after four journeys",
        )
    )

    releases = list(
        (
            await session.execute(
                select(Release).where(
                    Release.project_id == project_id, Release.status == ReleaseStatus.RELEASED
                )
            )
        ).scalars()
    )
    rel_keys = sorted({r.key for r in releases})
    checks.append(
        AcceptanceCheck(
            name="releases_r1_r2_r3_released",
            source="ARCH_26",
            ok=all(k in rel_keys for k in ("R1", "R2", "R3")),
            evidence_refs=[f"releases={rel_keys}"],
            query="R1,R2,R3 RELEASED",
        )
    )

    cycles = list(
        (
            await session.execute(
                select(DeliveryCycle).where(DeliveryCycle.project_id == project_id)
            )
        ).scalars()
    )
    terminal = {str(c.type): c.state for c in cycles}
    checks.append(
        AcceptanceCheck(
            name="four_delivery_cycles_terminal",
            source="STATUS_DOD",
            ok=terminal.get("GREENFIELD_BUILD") == "COMPLETE"
            and terminal.get("BROWNFIELD_ONBOARDING") == "READY"
            and terminal.get("FEATURE_CHANGE") == "COMPLETE"
            and terminal.get("BUG_FIX") == "COMPLETE",
            evidence_refs=[f"cycles={terminal}"],
            query="four journey terminal states",
        )
    )

    fake_calls = (
        await session.execute(
            select(func.count()).select_from(ModelCall).where(ModelCall.provider == "fake")
        )
    ).scalar_one()
    checks.append(
        AcceptanceCheck(
            name="live_LLM_required_flows_do_not_depend_on_mock_outputs",
            source="TECH_32",
            ok=fake_calls == 0,
            evidence_refs=[f"model_calls.provider=fake count={fake_calls}"],
            query="no fake provider in journey env",
        )
    )

    from core.assurance.models import Finding
    from core.integration.enums import FindingStatus

    open_blockers = (
        await session.execute(
            select(func.count())
            .select_from(Finding)
            .where(
                Finding.project_id == project_id,
                Finding.status == FindingStatus.OPEN,
                Finding.blocking.is_(True),
            )
        )
    ).scalar_one()
    checks.append(
        AcceptanceCheck(
            name="no_blocking_findings_remain",
            source="STATUS_DOD",
            ok=open_blockers == 0,
            evidence_refs=[f"open_blocker_findings={open_blockers}"],
            query="no OPEN BLOCKER findings",
        )
    )

    budget = os.environ.get("LLM_TEST_BUDGET_USD", "")
    total_cost = await session.scalar(
        select(func.coalesce(func.sum(ModelCall.cost_usd_estimate), 0))
        .select_from(ModelCall)
        .join(Execution, Execution.id == ModelCall.execution_id)
        .join(Task, Task.id == Execution.task_id)
        .join(DeliveryCycle, DeliveryCycle.id == Task.delivery_cycle_id)
        .where(DeliveryCycle.project_id == project_id)
    )
    under_budget = True
    if budget:
        try:
            under_budget = float(total_cost or 0) <= float(budget)
        except ValueError:
            under_budget = False
    checks.append(
        AcceptanceCheck(
            name="llm_spend_within_budget",
            source="STATUS_DOD",
            ok=under_budget,
            evidence_refs=[f"cost_usd={total_cost}", f"budget={budget}"],
            query="LLM_TEST_BUDGET_USD ceiling",
        )
    )

    checks.extend(
        await build_dod_checks(session, project_id, fingerprints=fingerprints, chaos=chaos)
    )
    return checks


async def evaluate(
    project_id: uuid.UUID,
    run_id: str,
    chaos: bool,
    fingerprints: dict[str, tuple[str, str]],
) -> MvpAcceptanceReport:
    started = datetime.now(UTC)
    token = _viewer_token()
    checks = await _http_checks(project_id, token)

    settings = get_settings()
    create_async_engine_from_settings(settings)
    factory = create_session_factory()
    project_key = "SUPPORTDESK"
    cycles_map: dict[str, str] = {}
    releases_map: dict[str, str] = {}
    llm_summary: dict[str, Decimal | int | float] = {"calls": 0, "cost_usd": 0}

    async with factory() as session:
        _pid, project_key = await _resolve_project_id(session, str(project_id))
        checks.extend(await _db_checks(session, project_id, fingerprints=fingerprints, chaos=chaos))
        cycles = list(
            (
                await session.execute(
                    select(DeliveryCycle).where(DeliveryCycle.project_id == project_id)
                )
            ).scalars()
        )
        cycles_map = {c.key: c.state for c in cycles}
        rels = list(
            (
                await session.execute(select(Release).where(Release.project_id == project_id))
            ).scalars()
        )
        releases_map = {r.key: r.integrated_sha for r in rels if r.integrated_sha}
        call_count = await session.scalar(
            select(func.count())
            .select_from(ModelCall)
            .join(Execution, Execution.id == ModelCall.execution_id)
            .join(Task, Task.id == Execution.task_id)
            .join(DeliveryCycle, DeliveryCycle.id == Task.delivery_cycle_id)
            .where(DeliveryCycle.project_id == project_id)
        )
        cost = await session.scalar(
            select(func.coalesce(func.sum(ModelCall.cost_usd_estimate), 0))
            .select_from(ModelCall)
            .join(Execution, Execution.id == ModelCall.execution_id)
            .join(Task, Task.id == Execution.task_id)
            .join(DeliveryCycle, DeliveryCycle.id == Task.delivery_cycle_id)
            .where(DeliveryCycle.project_id == project_id)
        )
        llm_summary = {"calls": int(call_count or 0), "cost_usd": float(cost or 0)}

    await dispose_engine()
    reset_session_factory()
    clear_settings_cache()

    finished = datetime.now(UTC)
    report = MvpAcceptanceReport(
        run_id=run_id,
        started_at=started,
        finished_at=finished,
        chaos=chaos,
        project_key=project_key,
        cycles=cycles_map,
        releases=releases_map,
        llm=llm_summary,
        restart_fingerprints=fingerprints,
        checks=checks,
        mvp_complete=all(c.ok for c in checks),
    )
    return report


def _write_report(report: MvpAcceptanceReport, out_dir: Path) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    json_path = out_dir / f"mvp_acceptance_{report.run_id}.json"
    json_path.write_text(report.model_dump_json(indent=2), encoding="utf-8")
    md_path = out_dir / f"mvp_acceptance_{report.run_id}.md"
    lines = [
        f"# MVP Acceptance — {report.run_id}",
        "",
        f"- **mvp_complete:** {report.mvp_complete}",
        f"- **chaos:** {report.chaos}",
        f"- **started:** {report.started_at.isoformat()}",
        f"- **finished:** {report.finished_at.isoformat()}",
        "",
        "## Checks",
        "",
    ]
    for check in report.checks:
        mark = "PASS" if check.ok else "FAIL"
        lines.append(f"- [{mark}] `{check.name}` ({check.source}) — {check.query}")
    md_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Evaluate MVP Definition of Done")
    parser.add_argument(
        "--project",
        required=True,
        help="Project UUID or SUPPORTDESK key prefix",
    )
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--out", type=Path, default=Path("var/olympus/reports"))
    parser.add_argument("--chaos", action="store_true")
    parser.add_argument(
        "--fingerprints",
        type=Path,
        default=None,
        help="JSON map boundary -> [before, after] hashes",
    )
    args = parser.parse_args()

    fp_raw = os.environ.get("MVP_FINGERPRINTS_JSON")
    if args.fingerprints and args.fingerprints.is_file():
        fp_raw = args.fingerprints.read_text(encoding="utf-8")
    fingerprints = _parse_fingerprints(fp_raw)

    settings = get_settings()
    create_async_engine_from_settings(settings)
    factory = create_session_factory()

    async def _resolve() -> uuid.UUID:
        async with factory() as session:
            pid, _ = await _resolve_project_id(session, args.project)
            return pid

    project_id = asyncio.run(_resolve())
    await dispose_engine()
    reset_session_factory()
    clear_settings_cache()

    report = asyncio.run(evaluate(project_id, args.run_id, args.chaos, fingerprints))
    _write_report(report, args.out)
    print(json.dumps({"mvp_complete": report.mvp_complete, "checks": len(report.checks)}))
    return 0 if report.mvp_complete else 1


if __name__ == "__main__":
    raise SystemExit(main())
