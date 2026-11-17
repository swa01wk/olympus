"""Releases arrive in the person's folder as a branch; folders map to one project."""

from __future__ import annotations

import subprocess
import uuid
from pathlib import Path
from unittest.mock import patch

import pytest
from core.autopilot.delivery import Delivery, _branch_sha, branch_for, deliver
from httpx import ASGITransport, AsyncClient

pytestmark = [pytest.mark.integration]

PRD = (Path(__file__).resolve().parents[2] / "fixtures" / "supportdesk" / "PRD.md").read_text()


def _git(folder: Path, *args: str) -> str:
    return subprocess.run(
        ["git", "-c", "user.name=dev", "-c", "user.email=dev@example.com", *args],
        cwd=folder,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()


def _repo(path: Path, files: dict[str, str]) -> str:
    path.mkdir(parents=True)
    _git(path, "init", "-q", "-b", "main")
    for name, text in files.items():
        (path / name).write_text(text)
    _git(path, "add", "-A")
    _git(path, "commit", "-qm", "commit")
    return _git(path, "rev-parse", "HEAD")


def _client(app, token: str) -> AsyncClient:  # type: ignore[no-untyped-def]
    return AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
        headers={"Authorization": f"Bearer {token}"},
    )


def test_branch_names_are_safe() -> None:
    assert branch_for("R1") == "olympus/r1"
    assert branch_for("REL 2 / hotfix") == "olympus/rel-2-hotfix"


@pytest.mark.asyncio
async def test_release_is_pushed_as_a_branch_without_touching_the_working_tree(
    tmp_path: Path,
) -> None:
    built_sha = _repo(tmp_path / "olympus-copy", {"app.py": "print('built by olympus')\n"})
    _repo(tmp_path / "mine", {"PRD.md": "# my app\n"})
    mine = tmp_path / "mine"
    (mine / "notes.txt").write_text("uncommitted work in progress\n")

    delivery = Delivery(
        target=mine, source=tmp_path / "olympus-copy", sha=built_sha, branch="olympus/r1"
    )
    await deliver(delivery)

    assert _branch_sha(mine, "olympus/r1") == built_sha
    assert _git(mine, "branch", "--show-current") == "main"
    assert (mine / "notes.txt").read_text() == "uncommitted work in progress\n"
    assert not (mine / "app.py").exists()


@pytest.mark.asyncio
async def test_existing_branch_is_never_overwritten(tmp_path: Path) -> None:
    first = _repo(tmp_path / "copy-a", {"app.py": "v1\n"})
    second = _repo(tmp_path / "copy-b", {"app.py": "v2\n"})
    _repo(tmp_path / "mine", {"PRD.md": "x\n"})
    mine = tmp_path / "mine"
    await deliver(Delivery(mine, tmp_path / "copy-a", first, "olympus/r1"))
    with pytest.raises(Exception, match="rejected|non-fast-forward|fetch first"):
        await deliver(Delivery(mine, tmp_path / "copy-b", second, "olympus/r1"))
    assert _branch_sha(mine, "olympus/r1") == first


@pytest.mark.asyncio
async def test_completed_new_app_delivers_once_then_reports_the_branch(
    control_app, operator_token, async_engine, tmp_path: Path
) -> None:
    from core.autopilot.service import AutopilotService, system_context
    from core.domain.delivery_cycles.models import DeliveryCycle
    from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

    built_sha = _repo(tmp_path / "olympus-copy", {"app.py": "print(1)\n"})
    mine = tmp_path / "mine"
    mine.mkdir()
    _git(mine, "init", "-q", "-b", "main")
    (mine / "PRD.md").write_text(PRD)

    async with _client(control_app, operator_token) as client:
        started = await client.post(
            "/start",
            json={"name": "Desk", "prd_text": PRD, "local_path": str(mine)},
        )
        assert started.status_code == 201, started.text
        cycle_id = uuid.UUID(started.json()["delivery_cycle_id"])

    factory = async_sessionmaker(bind=async_engine, class_=AsyncSession, expire_on_commit=False)
    async with factory() as session, session.begin():
        cycle = await session.get(DeliveryCycle, cycle_id)
        assert cycle is not None
        cycle.state = "COMPLETE"

    delivery = Delivery(mine, tmp_path / "olympus-copy", built_sha, "olympus/r1")

    async def _pending(_session, _cycle):  # type: ignore[no-untyped-def]
        return None if _branch_sha(mine, "olympus/r1") == built_sha else delivery

    with patch("core.autopilot.delivery.pending_delivery", _pending):
        async with factory() as session, session.begin():
            ctx = await system_context(session, "delivery-test")
            state = await AutopilotService().advance(session, cycle_id, ctx)
            assert (state.status, state.step) == ("WORKING", "deliver")
            assert "olympus/r1" in state.message
        assert _branch_sha(mine, "olympus/r1") == built_sha

        async with factory() as session, session.begin():
            ctx = await system_context(session, "delivery-test")
            state = await AutopilotService().advance(session, cycle_id, ctx)
            assert state.status == "DONE"


@pytest.mark.asyncio
async def test_start_validation_for_local_folders(control_app, operator_token, tmp_path) -> None:
    async with _client(control_app, operator_token) as client:
        no_prd = await client.post("/start", json={"name": "X", "local_path": str(tmp_path)})
        assert "PRD_REQUIRED" in no_prd.text

        relative = await client.post(
            "/start", json={"name": "X", "prd_text": PRD, "local_path": "some/folder"}
        )
        assert "INVALID_LOCAL_PATH" in relative.text

        not_git = await client.post(
            "/start",
            json={
                "journey": "BROWNFIELD_ONBOARDING",
                "name": "X",
                "local_path": str(tmp_path),
            },
        )
        assert "NOT_A_GIT_REPO" in not_git.text

        unknown = await client.get("/local-projects", params={"path": str(tmp_path / "nope")})
        assert unknown.status_code == 404

        ok = await client.post(
            "/start", json={"name": "Folder App", "prd_text": PRD, "local_path": str(tmp_path)}
        )
        assert ok.status_code == 201, ok.text
        home = (await client.get("/home")).json()
        row = next(p for p in home if p["name"] == "Folder App")
        assert row["local_path"] == str(tmp_path.resolve())


@pytest.mark.asyncio
async def test_review_with_nothing_pending_is_a_no_op(
    control_app, operator_token, tmp_path
) -> None:
    async with _client(control_app, operator_token) as client:
        cycle_id = (await client.post("/start", json={"name": "Quiet", "prd_text": PRD})).json()[
            "delivery_cycle_id"
        ]
        assert (await client.get(f"/delivery-cycles/{cycle_id}/autopilot/review")).json() == []
        done = await client.post(f"/delivery-cycles/{cycle_id}/autopilot/review", json={})
        assert done.status_code == 200, done.text
        bad = await client.post(
            f"/delivery-cycles/{cycle_id}/autopilot/review",
            json={"choices": [{"subject_type": "X", "subject_id": "y", "choice": "maybe"}]},
        )
        assert bad.status_code == 422
