from __future__ import annotations

from unittest.mock import patch

import pytest
from core.commands.context import CommandContext
from core.domain.actors.models import Actor
from core.domain.enums import ActorKind, ActorRole, ApprovalType
from core.policy.action_policy import PolicyDecision
from core.tools.gateway import ToolGateway
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from tests.fixtures.phase04_harness import (
    seed_code_change_task,
    seed_execution_with_worktree,
    seed_greenfield_repository,
)

pytestmark = [pytest.mark.integration]


@pytest.mark.asyncio
async def test_action_approval_created_and_decidable_via_api(
    api_client,
    async_engine,
) -> None:
    factory = async_sessionmaker(bind=async_engine, class_=AsyncSession, expire_on_commit=False)
    exec_token: str
    async with factory() as session, session.begin():
        actor = Actor(kind=ActorKind.SYSTEM, name="apr4-sys", roles=[ActorRole.SYSTEM.value])
        session.add(actor)
        await session.flush()
        ctx = CommandContext(actor=actor, correlation_id="apr4")
        project, repo, sha = await seed_greenfield_repository(session, ctx, project_key="apr4")
        fixture = await seed_code_change_task(session, ctx, project, repo, sha)
        bundle = await seed_execution_with_worktree(session, ctx, fixture, key_prefix="apr")
        exec_token = bundle.token
        gateway = ToolGateway(session)
        approval_decision = PolicyDecision(
            decision="REQUIRE_APPROVAL",
            rule_ids=["test.approval"],
            reasons=["test requires approval"],
            policy_version_id=None,
            requires_approval=True,
        )
        with patch("core.tools.gateway.evaluate_action_policy", return_value=approval_decision):
            pending = await gateway.handle(
                bundle.token,
                "git.status",
                {},
            )
        assert pending.status == "PENDING_APPROVAL", pending.denial_reasons

    pending_list = await api_client.get("/approvals/pending")
    assert pending_list.status_code == 200
    matches = [
        a
        for a in pending_list.json()
        if a["approval_type"] == ApprovalType.ACTION.value and a["subject_type"] == "action_request"
    ]
    assert len(matches) >= 1
    approval_id = matches[0]["id"]

    decided = await api_client.post(
        f"/approvals/{approval_id}/decision",
        json={"decision": "APPROVED", "note": "ok for test"},
    )
    assert decided.status_code == 200
    body = decided.json()
    assert body["status"] == "APPROVED"
    assert body["decision_note"] == "ok for test"
    assert body["decided_by_actor_id"]
    assert body["decided_at"]
    fetched = await api_client.get(f"/approvals/{approval_id}")
    assert fetched.json()["decision_note"] == "ok for test"
    assert exec_token  # used by gateway path above
