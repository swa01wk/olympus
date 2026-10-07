from __future__ import annotations

import json
import uuid

import pytest
from core.commands.context import CommandContext
from core.domain.actors.models import Actor
from core.domain.enums import ActorKind, ActorRole, ApprovalStatus, ApprovalType
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from tests.fixtures.repositories import materialize_existing_repository

pytestmark = [pytest.mark.integration]


@pytest.mark.asyncio
async def test_illegal_transition_409_and_rejection_audit(api_client) -> None:
    project = await api_client.post("/projects", json={"key": "rej", "name": "Rej"})
    assert project.status_code == 201
    cycle = await api_client.post(
        f"/projects/{project.json()['id']}/delivery-cycles",
        json={"type": "GREENFIELD_BUILD", "objective": "x"},
    )
    assert cycle.status_code == 201
    cycle_id = cycle.json()["id"]
    bad = await api_client.post(
        f"/delivery-cycles/{cycle_id}/commands/complete",
        json={"expected_state": "DISCOVERY"},
    )
    assert bad.status_code == 409
    audit = await api_client.get(
        "/audit",
        params={"target_type": "delivery_cycle", "target_id": cycle_id},
    )
    assert audit.status_code == 200
    actions = [row["action"] for row in audit.json()]
    assert "transition.rejected" in actions


@pytest.mark.asyncio
async def test_idempotent_task_create(api_client) -> None:
    project = await api_client.post("/projects", json={"key": "task-idem", "name": "T"})
    cycle = await api_client.post(
        f"/projects/{project.json()['id']}/delivery-cycles",
        json={"type": "GREENFIELD_BUILD", "objective": "t"},
    )
    cycle_id = cycle.json()["id"]
    headers = {"Idempotency-Key": "task-dup"}
    body = {"title": "Work", "work_type": "ANALYSIS"}
    first = await api_client.post(
        f"/delivery-cycles/{cycle_id}/tasks",
        json=body,
        headers=headers,
    )
    second = await api_client.post(
        f"/delivery-cycles/{cycle_id}/tasks",
        json=body,
        headers=headers,
    )
    assert first.status_code == 201 and second.status_code == 201
    assert first.json()["id"] == second.json()["id"]


async def test_idempotent_delivery_cycle_transition(api_client) -> None:
    project = await api_client.post("/projects", json={"key": "tr-idem", "name": "Tr"})
    cycle = await api_client.post(
        f"/projects/{project.json()['id']}/delivery-cycles",
        json={"type": "GREENFIELD_BUILD", "objective": "t"},
    )
    cycle_id = cycle.json()["id"]
    headers = {"Idempotency-Key": "cancel-once"}
    body = {"expected_state": "DISCOVERY"}
    url = f"/delivery-cycles/{cycle_id}/commands/cancel"
    first = await api_client.post(url, json=body, headers=headers)
    second = await api_client.post(url, json=body, headers=headers)
    assert first.status_code == 200 and second.status_code == 200
    assert first.json() == second.json()


async def test_idempotent_delivery_cycle_create(api_client) -> None:
    project = await api_client.post("/projects", json={"key": "idem", "name": "Idem"})
    project_id = project.json()["id"]
    headers = {"Idempotency-Key": "cycle-dup-key"}
    body = {"type": "GREENFIELD_BUILD", "objective": "same"}
    first = await api_client.post(
        f"/projects/{project_id}/delivery-cycles",
        json=body,
        headers=headers,
    )
    second = await api_client.post(
        f"/projects/{project_id}/delivery-cycles",
        json=body,
        headers=headers,
    )
    assert first.status_code == 201 and second.status_code == 201
    assert first.json()["id"] == second.json()["id"]


@pytest.mark.asyncio
async def test_brownfield_repository_guard_and_pin(
    api_client,
    async_engine,
    tmp_path,
) -> None:
    fixture_dir = tmp_path / "origin"
    fixture_dir.mkdir()
    project_resp = await api_client.post("/projects", json={"key": "bf", "name": "BF"})
    project_id = project_resp.json()["id"]
    origin_url = f"file://{(fixture_dir).resolve()}"
    reg = await api_client.post(
        f"/projects/{project_id}/repositories",
        json={
            "name": "ext",
            "provider": "LOCAL",
            "remote_url": origin_url,
            "credential_ref": "none:",
        },
    )
    assert reg.status_code == 201, reg.text
    repo_id = reg.json()["id"]
    assert reg.json()["status"] == "CLONING"
    cycle = await api_client.post(
        f"/projects/{project_id}/delivery-cycles",
        json={
            "type": "BROWNFIELD_ONBOARDING",
            "objective": "Onboard",
            "repository_id": repo_id,
        },
    )
    assert cycle.status_code == 201
    cycle_id = cycle.json()["id"]
    blocked = await api_client.post(
        f"/delivery-cycles/{cycle_id}/commands/start_code_index",
        json={"expected_state": "RECON"},
    )
    assert blocked.status_code == 422
    assert "REPOSITORY_NOT_READY" in blocked.text

    factory = async_sessionmaker(bind=async_engine, class_=AsyncSession, expire_on_commit=False)
    async with factory() as session, session.begin():
        actor = Actor(kind=ActorKind.SYSTEM, name="mat", roles=[ActorRole.SYSTEM.value])
        session.add(actor)
        await session.flush()
        ctx = CommandContext(actor=actor, correlation_id="mat")
        head = await materialize_existing_repository(session, uuid.UUID(repo_id), fixture_dir, ctx)

    ok = await api_client.post(
        f"/delivery-cycles/{cycle_id}/commands/start_code_index",
        json={"expected_state": "RECON"},
    )
    assert ok.status_code == 200, ok.text
    refreshed = await api_client.get(f"/delivery-cycles/{cycle_id}")
    assert refreshed.status_code == 200
    body = refreshed.json()
    assert body["state"] == "CODE_INDEX"
    assert body["base_sha"] == head
    repo = await api_client.get(f"/repositories/{repo_id}")
    assert repo.json()["canonical_commit"] == head


@pytest.mark.asyncio
async def test_repository_api_hides_paths_and_secrets(api_client, tmp_path) -> None:
    ws_root = str(tmp_path / "ws")
    project = await api_client.post("/projects", json={"key": "sec", "name": "Sec"})
    project_id = project.json()["id"]
    reg = await api_client.post(
        f"/projects/{project_id}/repositories",
        json={
            "name": "ext",
            "provider": "LOCAL",
            "remote_url": f"file://{(tmp_path / 'o').resolve()}",
            "credential_ref": "env:REPO_TOKEN",
        },
    )
    repo_id = reg.json()["id"]
    detail = await api_client.get(f"/repositories/{repo_id}")
    assert detail.status_code == 200
    blob = json.dumps(detail.json())
    assert ws_root not in blob
    assert "/Users/" not in blob
    assert "ghp_" not in blob
    assert detail.json()["credential_ref"] == "env:REPO_TOKEN"
    revs = await api_client.get(f"/repositories/{repo_id}/revisions")
    assert revs.status_code == 200
    assert ws_root not in json.dumps(revs.json())


@pytest.mark.asyncio
async def test_approval_decide_forbidden_and_allowed(api_client, viewer_client) -> None:
    project = await api_client.post("/projects", json={"key": "apr", "name": "Apr"})
    project_id = project.json()["id"]
    cycle = await api_client.post(
        f"/projects/{project_id}/delivery-cycles",
        json={"type": "GREENFIELD_BUILD", "objective": "a"},
    )
    cycle_id = cycle.json()["id"]
    subject_id = str(uuid.uuid4())
    req = await api_client.post(
        f"/delivery-cycles/{cycle_id}/approvals",
        json={
            "approval_type": ApprovalType.SCOPE.value,
            "subject_type": "task_contract",
            "subject_id": subject_id,
            "subject_version": 1,
            "subject_hash": "abc123",
        },
    )
    assert req.status_code == 201
    approval_id = req.json()["id"]

    denied = await viewer_client.post(
        f"/approvals/{approval_id}/decision",
        json={"decision": ApprovalStatus.APPROVED.value, "note": "nope"},
    )
    assert denied.status_code == 403
    audit = await api_client.get(
        "/audit",
        params={"target_type": "approval", "target_id": approval_id},
    )
    assert any(row["action"] == "approval.decision_denied" for row in audit.json())

    approved = await api_client.post(
        f"/approvals/{approval_id}/decision",
        json={"decision": ApprovalStatus.APPROVED.value, "note": "ok"},
    )
    assert approved.status_code == 200
    assert approved.json()["status"] == ApprovalStatus.APPROVED.value
    events = await api_client.get(f"/delivery-cycles/{cycle_id}/events")
    assert any(e["event_type"] == "approval.decided" for e in events.json())


@pytest.mark.asyncio
async def test_sse_delivers_events_and_resumes(api_client, control_app) -> None:
    from apps.control_api.sse import stream_delivery_cycle_events
    from starlette.requests import Request

    project = await api_client.post("/projects", json={"key": "sse", "name": "SSE"})
    cycle = await api_client.post(
        f"/projects/{project.json()['id']}/delivery-cycles",
        json={"type": "GREENFIELD_BUILD", "objective": "s"},
    )
    cycle_id = uuid.UUID(cycle.json()["id"])
    before = await api_client.get(f"/delivery-cycles/{cycle_id}/events")
    last_seq = max((e["sequence"] for e in before.json()), default=0)
    cancel = await api_client.post(
        f"/delivery-cycles/{cycle_id}/commands/cancel",
        json={"expected_state": "DISCOVERY"},
    )
    assert cancel.status_code == 200
    after = await api_client.get(
        f"/delivery-cycles/{cycle_id}/events",
        params={"after_sequence": last_seq},
    )
    assert any(e["event_type"] == "delivery_cycle.transitioned" for e in after.json())

    scope = {
        "type": "http",
        "headers": [(b"last-event-id", str(last_seq).encode())],
    }
    request = Request(scope)
    response = await stream_delivery_cycle_events(
        control_app.state.session_factory,
        cycle_id,
        request,
    )
    buf = b""
    async for chunk in response.body_iterator:
        buf += chunk if isinstance(chunk, bytes) else chunk.encode()
        if b"delivery_cycle.transitioned" in buf:
            break
    else:
        raise AssertionError("SSE stream did not deliver transition event")
    assert b"id:" in buf
