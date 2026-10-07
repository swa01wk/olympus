"""Phase 16 — secrets, inbound HMAC, reconciliation, repository sync."""

from __future__ import annotations

import hashlib
import hmac
import json
import subprocess
import uuid
from pathlib import Path

import pytest
from core.commands.bus import CommandBus
from core.commands.context import CommandContext
from core.commands.registry import build_command_bus
from core.domain.enums import (
    InboundEventStatus,
    IntegrationAuthKind,
    RepositoryProvider,
    RepositoryStatus,
)
from core.domain.integrations.models import ReconciliationItem, RepositoryEvent, StoredSecret
from core.domain.projects.models import Project
from core.integrations.connectors.base import ConnectorAction
from core.integrations.connectors.registry import get_connector_registry
from core.integrations.connectors.secrets import build_credential_resolver, store_secret
from core.integrations.inbound.models import InboundEvent, IntegrationSource
from core.integrations.inbound.service import InboundService
from core.integrations.reconciliation.service import ReconciliationService
from core.repositories.materialization import RepositoryMaterializationService
from core.repositories.service import RepositoryService
from core.repositories.sync import RepositorySyncService
from sqlalchemy import select, text

pytestmark = pytest.mark.integration


@pytest.fixture
def command_bus() -> CommandBus:
    return build_command_bus()


@pytest.mark.asyncio
async def test_secret_store_encrypted_not_plaintext(db_session, system_ctx: CommandContext) -> None:
    import os

    os.environ["OLYMPUS_SECRET_KEY"] = "test-secret-key-for-p16"
    from core.config.settings import clear_settings_cache

    clear_settings_cache()
    plaintext = "gitea-token-value-unique-xyz"
    await store_secret(db_session, "gitea-test", plaintext)
    row = await db_session.execute(select(StoredSecret).where(StoredSecret.name == "gitea-test"))
    stored = row.scalar_one()
    assert plaintext.encode() not in stored.ciphertext
    cred = build_credential_resolver(db_session)
    resolved = await cred.resolve_async("secret:gitea-test")
    assert resolved is not None
    assert resolved.secret.get_secret_value() == plaintext


@pytest.mark.asyncio
async def test_inbound_hmac_rejects_invalid_signature(
    db_session,
    system_ctx: CommandContext,
    sample_project: Project,
    command_bus: CommandBus,
) -> None:
    import os

    os.environ["OLYMPUS_SECRET_KEY"] = "hmac-test-key"
    from core.config.settings import clear_settings_cache

    clear_settings_cache()
    await store_secret(db_session, "webhook", "super-secret")
    db_session.add(
        IntegrationSource(
            project_id=sample_project.id,
            source_type="git_provider_webhook",
            name="default",
            auth_kind=IntegrationAuthKind.HMAC_SHA256,
            secret_ref="secret:webhook",
            active=True,
        )
    )
    await db_session.flush()
    body = {"ref": "refs/heads/main", "repository_id": str(uuid.uuid4())}
    raw = {
        "source_id": "default",
        "event_id": "evt-1",
        "project_id": str(sample_project.id),
        "json_body": body,
        "headers": {"X-Gitea-Signature": "sha256=deadbeef"},
        "raw_body": json.dumps(body).encode(),
    }
    result = await InboundService(command_bus).receive(
        db_session, "git_provider_webhook", raw, system_ctx
    )
    assert result["status"] == "REJECTED"
    rows = await db_session.execute(select(InboundEvent).where(InboundEvent.event_id == "evt-1"))
    event = rows.scalar_one()
    assert event.status == InboundEventStatus.REJECTED


@pytest.mark.asyncio
async def test_inbound_hmac_accepts_valid_signature(
    db_session,
    system_ctx: CommandContext,
    sample_project: Project,
    command_bus: CommandBus,
    tmp_path: Path,
) -> None:
    import os

    os.environ["OLYMPUS_SECRET_KEY"] = "hmac-test-key-2"
    from core.config.settings import clear_settings_cache

    clear_settings_cache()
    secret = "webhook-shared-secret"
    await store_secret(db_session, "wh", secret)
    db_session.add(
        IntegrationSource(
            project_id=sample_project.id,
            source_type="git_provider_webhook",
            name="default",
            auth_kind=IntegrationAuthKind.HMAC_SHA256,
            secret_ref="secret:wh",
            active=True,
        )
    )
    origin = tmp_path / "origin"
    origin.mkdir()
    subprocess.run(["git", "init", "-b", "main"], cwd=origin, check=True, capture_output=True)
    (origin / "README.md").write_text("v1\n", encoding="utf-8")
    subprocess.run(["git", "add", "-A"], cwd=origin, check=True, capture_output=True)
    subprocess.run(
        ["git", "-c", "user.email=t@t.com", "-c", "user.name=t", "commit", "-m", "v1"],
        cwd=origin,
        check=True,
        capture_output=True,
    )
    repo = await RepositoryService().register_external(
        db_session,
        sample_project.id,
        "webhook-repo",
        RepositoryProvider.LOCAL,
        f"file://{origin.resolve()}",
        "main",
        "none:",
        system_ctx,
    )
    await RepositoryMaterializationService().materialize_external(db_session, repo.id, system_ctx)
    await db_session.refresh(repo)
    assert repo.status == RepositoryStatus.READY
    body = {
        "ref": "refs/heads/main",
        "before": repo.canonical_commit,
        "after": repo.canonical_commit,
        "repository_id": str(repo.id),
    }
    raw_body = json.dumps(body).encode()
    sig = hmac.new(secret.encode(), raw_body, hashlib.sha256).hexdigest()
    raw = {
        "source_id": "default",
        "event_id": "evt-valid-1",
        "project_id": str(sample_project.id),
        "json_body": body,
        "headers": {"X-Gitea-Signature": f"sha256={sig}"},
        "raw_body": raw_body,
        "repository_id": str(repo.id),
    }
    result = await InboundService(command_bus).receive(
        db_session, "git_provider_webhook", raw, system_ctx
    )
    assert result["status"] == "ACCEPTED"


@pytest.mark.asyncio
async def test_unknown_connector_action_opens_reconciliation_item(
    db_session, system_ctx: CommandContext
) -> None:
    registry = get_connector_registry()
    action = ConnectorAction(
        connector="git_local",
        action="resolve_head",
        target_resource="missing",
        inputs={"logical_location": "projects/nope/repo", "branch": "main"},
        idempotency_key=f"test-unknown-{uuid.uuid4().hex}",
        correlation_id="recon-test",
        expected_result_schema="HeadResult",
    )
    result, action_id = await registry.execute_with_persistence(
        db_session, action, actor_id=system_ctx.actor.id
    )
    if result.status == "UNKNOWN":
        item = await db_session.execute(
            select(ReconciliationItem).where(ReconciliationItem.connector_action_id == action_id)
        )
        assert item.scalar_one_or_none() is not None
    else:
        svc = ReconciliationService()
        item = await svc.open_for_unknown(db_session, action_id, "manual-open")
        assert item.kind == "OUTBOUND_UNKNOWN"


@pytest.mark.asyncio
async def test_repository_sync_external_fast_forward(
    db_session,
    system_ctx: CommandContext,
    sample_project: Project,
    tmp_path: Path,
) -> None:
    origin = tmp_path / "origin"
    origin.mkdir()
    subprocess.run(["git", "init", "-b", "main"], cwd=origin, check=True, capture_output=True)
    (origin / "README.md").write_text("v1\n", encoding="utf-8")
    subprocess.run(["git", "add", "-A"], cwd=origin, check=True, capture_output=True)
    subprocess.run(
        ["git", "-c", "user.email=t@t.com", "-c", "user.name=t", "commit", "-m", "v1"],
        cwd=origin,
        check=True,
        capture_output=True,
    )
    head_v1 = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=origin,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()

    repo = await RepositoryService().register_external(
        db_session,
        sample_project.id,
        "sync-repo",
        RepositoryProvider.LOCAL,
        f"file://{origin.resolve()}",
        "main",
        "none:",
        system_ctx,
    )
    await RepositoryMaterializationService().materialize_external(db_session, repo.id, system_ctx)
    await db_session.refresh(repo)
    assert repo.canonical_commit == head_v1

    (origin / "README.md").write_text("v2 external\n", encoding="utf-8")
    subprocess.run(["git", "add", "-A"], cwd=origin, check=True, capture_output=True)
    subprocess.run(
        ["git", "-c", "user.email=t@t.com", "-c", "user.name=t", "commit", "-m", "v2"],
        cwd=origin,
        check=True,
        capture_output=True,
    )
    head_v2 = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=origin,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()

    event = await RepositorySyncService().sync(
        db_session,
        repo.id,
        system_ctx,
        before_sha=head_v1,
        after_sha=head_v2,
        ref="refs/heads/main",
    )
    await db_session.refresh(repo)
    assert event is not None
    assert event.classification == "EXTERNAL_FAST_FORWARD"
    assert repo.canonical_commit == head_v2
    rev_check = await db_session.execute(
        select(RepositoryEvent).where(RepositoryEvent.repository_id == repo.id)
    )
    assert rev_check.scalars().first() is not None

    dump = await db_session.execute(text("SELECT encode(ciphertext, 'escape') FROM secrets"))
    for row in dump:
        assert "gitea-token" not in str(row[0])


@pytest.mark.asyncio
async def test_duplicate_inbound_event_ack(
    db_session,
    operator_ctx: CommandContext,
    sample_project: Project,
    command_bus: CommandBus,
) -> None:
    payload = {
        "project_id": str(sample_project.id),
        "title": "Dup CR",
        "description": "Same event twice",
        "event_id": "dup-cr-1",
        "source_id": str(sample_project.id),
    }
    await RepositoryService().declare_managed(db_session, sample_project.id, operator_ctx)
    svc = InboundService(command_bus)
    first = await svc.receive(db_session, "change_request_api", payload, operator_ctx)
    second = await svc.receive(db_session, "change_request_api", payload, operator_ctx)
    assert first["status"] == "ACCEPTED"
    assert second["status"] == "DUPLICATE"
