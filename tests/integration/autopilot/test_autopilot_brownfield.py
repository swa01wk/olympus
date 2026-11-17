"""`olympus start` in an existing repo: onboarding driven by Autopilot (fake models only)."""

from __future__ import annotations

import subprocess
import uuid
from pathlib import Path
from unittest.mock import patch

import pytest
from core.autopilot.service import AutopilotService, system_context
from core.domain.delivery_cycles.models import DeliveryCycle
from core.execution.worker import ExecutionWorker
from core.repositories.materialization_loop import MaterializationLoop
from core.runtime.providers.fake_provider import FakeProvider
from core.scheduler.admission import AdmissionService
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

pytestmark = [pytest.mark.integration]


def _factory(engine: AsyncEngine) -> async_sessionmaker[AsyncSession]:
    return async_sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False)


def _client(app, token: str) -> AsyncClient:  # type: ignore[no-untyped-def]
    return AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
        headers={"Authorization": f"Bearer {token}"},
    )


def _git(folder: Path, *args: str) -> str:
    return subprocess.run(
        ["git", "-c", "user.name=dev", "-c", "user.email=dev@example.com", *args],
        cwd=folder,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()


def make_repo(root: Path) -> Path:
    repo = root / "notes-app"
    (repo / "notes").mkdir(parents=True)
    (repo / "tests").mkdir()
    (repo / "notes" / "__init__.py").write_text("")
    (repo / "notes" / "store.py").write_text(
        "NOTES: list[str] = []\n\n\n"
        "def add_note(text: str) -> int:\n"
        "    if not text:\n"
        "        raise ValueError('empty note')\n"
        "    NOTES.append(text)\n"
        "    return len(NOTES)\n"
    )
    (repo / "tests" / "test_store.py").write_text(
        "from notes.store import add_note\n\n\n"
        "def test_add_note() -> None:\n"
        "    assert add_note('hi') >= 1\n"
    )
    (repo / "README.md").write_text("# Notes\n")
    _git(repo, "init", "-q", "-b", "main")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-qm", "notes app")
    return repo


async def _tick(engine: AsyncEngine, cycle_id: str):  # type: ignore[no-untyped-def]
    async with _factory(engine)() as session, session.begin():
        ctx = await system_context(session, "bf-test")
        return await AutopilotService().advance(session, uuid.UUID(cycle_id), ctx)


async def _scheduler_and_worker(engine: AsyncEngine, rounds: int = 3) -> None:
    """One scheduler pass (clone + admit) and worker passes, with a fake model only."""
    fake = FakeProvider()
    with patch(
        "core.runtime.model_router.build_providers",
        side_effect=lambda **kw: {"anthropic": fake, "openai": fake},
    ):
        for _ in range(rounds):
            async with _factory(engine)() as session, session.begin():
                ctx = await system_context(session, "bf-test-worker")
                await MaterializationLoop().run_once(session, ctx)
                await AdmissionService().admit_batch(session, 10, ctx)
                for _ in range(6):
                    if not await ExecutionWorker(worker_id="bf-test").run_once(session, ctx):
                        break


@pytest.mark.asyncio
async def test_existing_repo_is_cloned_indexed_and_learned_without_touching_it(
    control_app, operator_token, async_engine, tmp_path
) -> None:
    repo = make_repo(tmp_path)
    head_before = _git(repo, "rev-parse", "HEAD")

    async with _client(control_app, operator_token) as client:
        started = await client.post(
            "/start",
            json={
                "journey": "BROWNFIELD_ONBOARDING",
                "name": "Notes",
                "local_path": str(repo),
            },
        )
        assert started.status_code == 201, started.text
        cycle_id = started.json()["delivery_cycle_id"]
        assert started.json()["autopilot"]["message"] == "Copying your repository"

        found = (await client.get("/local-projects", params={"path": str(repo)})).json()
        assert found["name"] == "Notes"
        assert found["latest_run"]["delivery_cycle_id"] == cycle_id

        again = await client.post(
            "/start",
            json={"journey": "BROWNFIELD_ONBOARDING", "name": "Notes", "local_path": str(repo)},
        )
        assert again.status_code >= 400
        assert "FOLDER_ALREADY_A_PROJECT" in again.text

    seen: list[tuple[str, str, str]] = []
    for _ in range(12):
        await _scheduler_and_worker(async_engine)
        state = await _tick(async_engine, cycle_id)
        async with _factory(async_engine)() as session:
            cycle = await session.get(DeliveryCycle, uuid.UUID(cycle_id))
            assert cycle is not None
            seen.append((cycle.state, state.status, state.message))
        if cycle.state == "RECOVERED_SPEC":
            break
    assert ("CODE_INDEX", "WORKING", "Reading your code") in seen, seen
    assert seen[-1] == ("RECOVERED_SPEC", "WORKING", "Working out what your app does"), seen

    # The fake model has no answers scripted, so Scout fails: Autopilot must stop with a
    # readable reason and offer a retry, not loop.
    for _ in range(8):
        await _scheduler_and_worker(async_engine)
        state = await _tick(async_engine, cycle_id)
        if state.status != "WORKING":
            break
    assert state.status == "BLOCKED", state.message
    assert state.message.startswith("Working out what your app does failed")
    assert state.detail["retryable"] is True
    assert state.detail["retry_tasks"] is True
    (failed_task,) = state.detail["task_ids"]

    async with _client(control_app, operator_token) as client:
        retried = await client.post(f"/delivery-cycles/{cycle_id}/autopilot/retry")
        assert retried.status_code == 200, retried.text
        assert (retried.json()["status"], retried.json()["message"]) == (
            "WORKING",
            "Working out what your app does",
        )
    async with _factory(async_engine)() as session:
        from core.domain.enums import TaskStatus
        from core.domain.tasks.models import Task

        task = await session.get(Task, uuid.UUID(failed_task))
        assert task is not None and task.status == TaskStatus.READY
    # Olympus works on its own clone: the person's repo is untouched.
    assert _git(repo, "rev-parse", "HEAD") == head_before
    assert _git(repo, "status", "--porcelain") == ""
