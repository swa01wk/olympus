"""Autopilot drives a Greenfield cycle and pauses only for the person (fake models only)."""

from __future__ import annotations

import uuid
from pathlib import Path
from unittest.mock import patch

import pytest
from core.autopilot.models import AutopilotState
from core.autopilot.service import AutopilotService, system_context
from core.domain.enums import ApprovalStatus, TaskStatus
from core.domain.exceptions import DomainError
from core.domain.tasks.models import Task
from core.product_model.decomposition import DecompositionOrchestrator
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker
from tests.fixtures.planning_workflow_harness import (
    resolve_blocking_clarifications_for_cycle,
    run_supportdesk_decompose_worker,
)

pytestmark = [pytest.mark.integration]

PRD = Path(__file__).resolve().parents[2] / "fixtures" / "supportdesk" / "PRD.md"


def _factory(engine: AsyncEngine) -> async_sessionmaker[AsyncSession]:
    return async_sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False)


async def _tick(engine: AsyncEngine, cycle_id: str) -> AutopilotState:
    async with _factory(engine)() as session, session.begin():
        ctx = await system_context(session, "autopilot-test")
        state = await AutopilotService().advance(session, uuid.UUID(cycle_id), ctx)
        return state


async def _tasks(engine: AsyncEngine, cycle_id: str, title_prefix: str = "") -> list[Task]:
    async with _factory(engine)() as session:
        rows = await session.execute(
            select(Task)
            .where(Task.delivery_cycle_id == uuid.UUID(cycle_id))
            .order_by(Task.created_at)
        )
        return [t for t in rows.scalars() if t.title.startswith(title_prefix)]


async def _start(client: AsyncClient, name: str = "SupportDesk") -> dict[str, object]:
    resp = await client.post(
        "/start",
        json={"name": name, "prd_title": "PRD.md", "prd_text": PRD.read_text()},
    )
    assert resp.status_code == 201, resp.text
    return resp.json()


def _client(app, token: str) -> AsyncClient:  # type: ignore[no-untyped-def]
    return AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
        headers={"Authorization": f"Bearer {token}"},
    )


@pytest.mark.asyncio
async def test_start_creates_project_reads_prd_and_starts_breakdown_once(
    control_app, operator_token, async_engine
) -> None:
    async with _client(control_app, operator_token) as client:
        started = await _start(client)
        cycle_id = str(started["delivery_cycle_id"])
        autopilot = started["autopilot"]
        assert isinstance(autopilot, dict)
        assert autopilot["enabled"] is True
        assert autopilot["status"] == "WORKING"
        assert autopilot["step"] == "start_product_modeling"

        cycle = (await client.get(f"/delivery-cycles/{cycle_id}")).json()
        assert cycle["state"] == "PRODUCT_MODEL"

    state = await _tick(async_engine, cycle_id)
    assert (state.status, state.step) == ("WORKING", "decompose")
    assert state.message == "Breaking your PRD into features"

    # Another pass while the agent works must not start a second breakdown.
    state = await _tick(async_engine, cycle_id)
    assert (state.status, state.step) == ("WORKING", "decompose")
    decompose = [t for t in await _tasks(async_engine, cycle_id) if "ecompos" in t.title]
    assert len(decompose) == 1


@pytest.mark.asyncio
async def test_autopilot_pauses_for_scope_review_then_starts_design(
    control_app, operator_token, async_engine
) -> None:
    async with _client(control_app, operator_token) as client:
        cycle_id = str((await _start(client))["delivery_cycle_id"])
        await _tick(async_engine, cycle_id)
        (decompose,) = [t for t in await _tasks(async_engine, cycle_id) if "ecompos" in t.title]

        await run_supportdesk_decompose_worker(
            async_engine,
            str(decompose.id),
            correlation_id="autopilot-decompose",
            worker_id="autopilot-decompose",
            deterministic=True,
        )

        state = await _tick(async_engine, cycle_id)
        if state.step == "answer_questions":
            # The person answers the open questions; Autopilot never does.
            assert state.status == "NEEDS_YOU"
            async with _factory(async_engine)() as session, session.begin():
                await resolve_blocking_clarifications_for_cycle(session, uuid.UUID(cycle_id))
            state = await _tick(async_engine, cycle_id)

        assert state.step == "scope", state.message
        state = await _tick(async_engine, cycle_id)
        assert state.status == "NEEDS_YOU"
        assert state.step == "review"
        assert state.detail["approval_type"] == "SCOPE"
        assert state.message == "Review the features Olympus found in your PRD"

        view = (await client.get(f"/delivery-cycles/{cycle_id}/autopilot")).json()
        assert view["status"] == "NEEDS_YOU"
        (approval_id,) = view["detail"]["approval_ids"]

        decided = await client.post(
            f"/approvals/{approval_id}/decision",
            json={"decision": ApprovalStatus.APPROVED.value, "note": "looks right"},
        )
        assert decided.status_code == 200, decided.text

        state = await _tick(async_engine, cycle_id)
        assert state.step == "start_architecture"
        cycle = (await client.get(f"/delivery-cycles/{cycle_id}")).json()
        assert cycle["state"] == "ARCHITECTURE"

        state = await _tick(async_engine, cycle_id)
        assert (state.status, state.step) == ("WORKING", "design")
        assert [t.title for t in await _tasks(async_engine, cycle_id, "Propose architecture")]


@pytest.mark.asyncio
async def test_failed_action_stops_and_runs_again_only_on_retry(
    control_app, operator_token, async_engine
) -> None:
    calls: list[int] = []

    async def _boom(*_args: object, **_kwargs: object) -> None:
        calls.append(1)
        raise DomainError(code="BOOM", message="model provider unavailable")

    async with _client(control_app, operator_token) as client:
        cycle_id = str((await _start(client))["delivery_cycle_id"])
        with patch.object(DecompositionOrchestrator, "start_decomposition", _boom):
            state = await _tick(async_engine, cycle_id)
            assert state.status == "BLOCKED"
            assert state.step == "decompose"
            assert "model provider unavailable" in state.message
            assert state.detail["retryable"] is True

            await _tick(async_engine, cycle_id)
            await _tick(async_engine, cycle_id)
            assert len(calls) == 1, "a failed step must not loop"

            retried = await client.post(f"/delivery-cycles/{cycle_id}/autopilot/retry")
            assert retried.status_code == 200, retried.text
            assert len(calls) == 2
            assert retried.json()["status"] == "BLOCKED"

        retried = await client.post(f"/delivery-cycles/{cycle_id}/autopilot/retry")
        assert retried.status_code == 200, retried.text
        body = retried.json()
        assert (body["status"], body["step"]) == ("WORKING", "decompose")


@pytest.mark.asyncio
async def test_failed_agent_task_blocks_and_retry_starts_a_new_run(
    control_app, operator_token, async_engine
) -> None:
    async with _client(control_app, operator_token) as client:
        cycle_id = str((await _start(client))["delivery_cycle_id"])
        await _tick(async_engine, cycle_id)
        (decompose,) = [t for t in await _tasks(async_engine, cycle_id) if "ecompos" in t.title]
        async with _factory(async_engine)() as session, session.begin():
            task = await session.get(Task, decompose.id)
            assert task is not None
            task.status = TaskStatus.FAILED
            task.blocked_reason = "schema validation failed twice"

        state = await _tick(async_engine, cycle_id)
        assert state.status == "BLOCKED"
        assert "schema validation failed twice" in state.message
        assert state.detail["task_ids"] == [str(decompose.id)]

        retried = await client.post(f"/delivery-cycles/{cycle_id}/autopilot/retry")
        assert retried.json()["status"] == "WORKING"
        decompose_runs = [t for t in await _tasks(async_engine, cycle_id) if "ecompos" in t.title]
        assert len(decompose_runs) == 2


@pytest.mark.asyncio
async def test_turning_autopilot_off_and_unsupported_journeys(
    control_app, operator_token, async_engine
) -> None:
    async with _client(control_app, operator_token) as client:
        cycle_id = str((await _start(client))["delivery_cycle_id"])
        off = await client.put(f"/delivery-cycles/{cycle_id}/autopilot", json={"enabled": False})
        assert off.json()["status"] == "OFF"
        async with _factory(async_engine)() as session, session.begin():
            ctx = await system_context(session, "autopilot-test")
            assert await AutopilotService().tick(session, ctx) >= 0
        assert not [t for t in await _tasks(async_engine, cycle_id) if "ecompos" in t.title]

        project = (await client.get(f"/delivery-cycles/{cycle_id}")).json()["project_id"]
        other = await client.post(
            f"/projects/{project}/delivery-cycles",
            json={"type": "FEATURE_CHANGE", "objective": "later"},
        )
        if other.status_code == 201:
            resp = await client.put(
                f"/delivery-cycles/{other.json()['id']}/autopilot", json={"enabled": True}
            )
            assert resp.status_code >= 400
            assert "AUTOPILOT_UNSUPPORTED" in resp.text


async def _cycle_in_development(engine: AsyncEngine, cycle_id: str) -> list[uuid.UUID]:
    """Jump a started cycle to DEVELOPMENT with two code tasks (one done, one running)."""
    from core.domain.delivery_cycles.models import DeliveryCycle
    from core.domain.enums import TaskOrigin, WorkType
    from core.domain.tasks.service import TaskService

    async with _factory(engine)() as session, session.begin():
        ctx = await system_context(session, "autopilot-test")
        cycle = await session.get(DeliveryCycle, uuid.UUID(cycle_id))
        assert cycle is not None
        cycle.state = "DEVELOPMENT"
        ids = []
        for title, status in (
            ("Create ticket API", TaskStatus.COMPLETED),
            ("List tickets", TaskStatus.RUNNING),
        ):
            task = await TaskService().create_task(
                session, cycle.id, title, WorkType.CODE_CHANGE, TaskOrigin.IMPLEMENTATION_PLAN, ctx
            )
            task.status = status
            ids.append(task.id)
        return ids


@pytest.mark.asyncio
async def test_development_reports_progress_and_retries_failed_task_as_the_person(
    control_app, operator_token, async_engine
) -> None:
    async with _client(control_app, operator_token) as client:
        cycle_id = str((await _start(client))["delivery_cycle_id"])
        _done, running = await _cycle_in_development(async_engine, cycle_id)

        state = await _tick(async_engine, cycle_id)
        assert (state.status, state.step) == ("WORKING", "development")
        assert state.message == "Writing code (1 of 2 tasks done)"
        assert (state.detail["done"], state.detail["total"]) == (1, 2)

        async with _factory(async_engine)() as session, session.begin():
            task = await session.get(Task, running)
            assert task is not None
            task.status = TaskStatus.FAILED
            task.blocked_reason = "tests kept failing"
            task.max_attempts = 0  # used up: the scheduler would never run it again

        state = await _tick(async_engine, cycle_id)
        assert state.status == "BLOCKED"
        assert state.message == "The task “List tickets” failed: tests kept failing"

        retried = await client.post(f"/delivery-cycles/{cycle_id}/autopilot/retry")
        assert retried.status_code == 200, retried.text
        assert retried.json()["status"] == "WORKING"
        async with _factory(async_engine)() as session:
            task = await session.get(Task, running)
            assert task is not None
            assert task.status == TaskStatus.READY
            assert task.max_attempts == 3  # Try again grants a fresh set of attempts


@pytest.mark.asyncio
async def test_home_lists_projects_with_latest_run_and_activity_is_plain_language(
    control_app, operator_token, async_engine
) -> None:
    async with _client(control_app, operator_token) as client:
        started = await _start(client, name="Home Check")
        cycle_id = str(started["delivery_cycle_id"])
        await _tick(async_engine, cycle_id)

        home = (await client.get("/home")).json()
        row = next(p for p in home if p["id"] == str(started["project_id"]))
        assert row["name"] == "Home Check"
        assert row["key"].startswith("HOME-CHECK-")
        assert row["latest_run"]["delivery_cycle_id"] == cycle_id
        assert row["latest_run"]["autopilot"]["message"] == "Breaking your PRD into features"

        activity = (
            await client.get(
                f"/delivery-cycles/{cycle_id}/events",
                params={"event_type": "autopilot.updated", "latest": "true", "limit": 1},
            )
        ).json()
        assert [e["payload"]["message"] for e in activity] == ["Breaking your PRD into features"]

        everything = (await client.get(f"/delivery-cycles/{cycle_id}/events")).json()
        assert len(everything) > 1
        assert everything == sorted(everything, key=lambda e: e["sequence"])


@pytest.mark.asyncio
async def test_local_token_is_reused_and_refused_outside_local(
    async_engine, tmp_path, monkeypatch
) -> None:
    from apps.control_api.cli import local_token
    from core.config.settings import clear_settings_cache

    token_file = tmp_path / "local-token"
    first = await local_token.ensure_local_token(token_file)
    second = await local_token.ensure_local_token(token_file)
    assert first == second
    assert token_file.read_text().strip() == first
    assert oct(token_file.stat().st_mode & 0o777) == "0o600"

    token_file.write_text("not-a-real-token\n")
    third = await local_token.ensure_local_token(token_file)
    assert third != first

    monkeypatch.setenv("OLYMPUS_ENV", "journey")
    clear_settings_cache()
    with pytest.raises(SystemExit):
        local_token.main()
    clear_settings_cache()


@pytest.mark.asyncio
async def test_start_with_idempotency_key_replays_instead_of_conflicting(
    control_app, operator_token, async_engine
) -> None:
    """The browser sends an Idempotency-Key; /start runs several commands under it."""
    body = {"name": "Replay Check", "prd_title": "PRD.md", "prd_text": PRD.read_text()}
    key = f"start-{uuid.uuid4()}"
    async with _client(control_app, operator_token) as client:
        first = await client.post("/start", json=body, headers={"Idempotency-Key": key})
        assert first.status_code == 201, first.text
        again = await client.post("/start", json=body, headers={"Idempotency-Key": key})
        assert again.status_code == 201, again.text
        assert again.json()["project_id"] == first.json()["project_id"]
        assert again.json()["delivery_cycle_id"] == first.json()["delivery_cycle_id"]

        home = (await client.get("/home")).json()
        assert sum(1 for p in home if p["name"] == "Replay Check") == 1


@pytest.mark.asyncio
async def test_failed_merge_checks_block_retryable_and_retry_sends_them_to_be_fixed(
    control_app, operator_token, async_engine
) -> None:
    from core.assurance.findings import FindingService
    from core.assurance.models import Finding
    from core.domain.delivery_cycles.models import DeliveryCycle
    from core.domain.task_contracts.models import TaskContract
    from core.integration.enums import FindingSeverity, FindingSource, FindingStatus, ICStatus
    from core.integration.models import IntegrationCandidate

    async with _client(control_app, operator_token) as client:
        cycle_id = str((await _start(client))["delivery_cycle_id"])
        await _cycle_in_development(async_engine, cycle_id)
        async with _factory(async_engine)() as session, session.begin():
            ctx = await system_context(session, "autopilot-test")
            for task in await _tasks(async_engine, cycle_id):
                row = await session.get(Task, task.id)
                assert row is not None
                row.status = TaskStatus.COMPLETED
            cycle = await session.get(DeliveryCycle, uuid.UUID(cycle_id))
            assert cycle is not None
            if cycle.repository_id is None:
                pytest.skip("started cycle has no repository in this environment")
            cycle.state = "INTEGRATION"
            ic = IntegrationCandidate(
                key="IC-T1",
                delivery_cycle_id=cycle.id,
                repository_id=cycle.repository_id,
                base_sha="a" * 40,
                integration_branch="olympus/integration/IC-T1",
                status=ICStatus.FAILED,
                ordering=[],
            )
            session.add(ic)
            await session.flush()
            finding = await FindingService().create(
                session,
                project_id=cycle.project_id,
                delivery_cycle_id=cycle.id,
                source=FindingSource.INTEGRATION,
                category="INTEGRATION_CHECK_FAILED",
                severity=FindingSeverity.BLOCKER,
                title="Integration checks failed",
                detail={"merged_head_sha": "b" * 40, "summary": "FAILED tests/test_x.py::t"},
                ctx=ctx,
                integration_candidate_id=ic.id,
            )
            finding_id = finding.id

        state = await _tick(async_engine, cycle_id)
        assert (state.status, state.step) == ("BLOCKED", "integration")
        assert state.detail["retryable"] is True
        assert "still fails its checks" in state.message

        retried = await client.post(f"/delivery-cycles/{cycle_id}/autopilot/retry")
        assert retried.status_code == 200, retried.text
        async with _factory(async_engine)() as session:
            row = await session.get(Finding, finding_id)
            assert row is not None
            assert row.status == FindingStatus.IN_REMEDIATION
            assert row.detail["auto_fix"] is False  # a person's retry restarts the auto rounds
            fix = await session.get(Task, row.remediation_task_id)
            assert fix is not None
            assert fix.title == "Fix failing checks in IC-T1"
            contract = await session.get(TaskContract, fix.current_contract_id)
            assert contract is not None
            assert contract.body["base_commit"] == "b" * 40
            assert "FAILED tests/test_x.py::t" in contract.body["objective"]

        state = await _tick(async_engine, cycle_id)
        async with _factory(async_engine)() as session:
            cycle = await session.get(DeliveryCycle, uuid.UUID(cycle_id))
            assert cycle is not None
            assert cycle.state == "DEVELOPMENT"  # the fix is coded, merged and checked again
