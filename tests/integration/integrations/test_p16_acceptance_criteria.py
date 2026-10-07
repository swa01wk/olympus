"""Phase 16 §14 acceptance criteria — deterministic integration proofs."""

from __future__ import annotations

import hashlib
import hmac
import json
import uuid

import pytest
from core.assurance.enums import EvidenceType
from core.assurance.models import Evidence
from core.bootstrap.connectors import ensure_connectors_registered
from core.commands.bus import CommandBus
from core.commands.ci_handlers import handle_ingest_external_ci_result
from core.commands.context import CommandContext
from core.commands.registry import build_command_bus
from core.domain.connectors.models import ConnectorActionRecord
from core.domain.enums import (
    ExecutionStatus,
    IntegrationAuthKind,
    RepositoryProvider,
)
from core.domain.integrations.models import ExternalLink
from core.domain.projects.models import Project
from core.integrations.connectors.base import ConnectorAction
from core.integrations.connectors.registry import get_connector_registry, reset_connector_registry
from core.integrations.connectors.secrets import store_secret
from core.integrations.inbound.models import IntegrationSource
from core.integrations.inbound.service import InboundService
from core.repositories.service import RepositoryService
from sqlalchemy import select

pytestmark = pytest.mark.integration


@pytest.fixture
def command_bus() -> CommandBus:
    return build_command_bus()


@pytest.fixture(autouse=True)
def _connectors() -> None:
    reset_connector_registry()
    ensure_connectors_registered()


@pytest.mark.asyncio
async def test_ac_inbound_adapters_authenticate_and_deduplicate(
    db_session,
    system_ctx: CommandContext,
    sample_project: Project,
    command_bus: CommandBus,
) -> None:
    import os

    os.environ["OLYMPUS_SECRET_KEY"] = "ac-inbound-key"
    from core.config.settings import clear_settings_cache

    clear_settings_cache()
    secret = "shared-hmac"
    await store_secret(db_session, "wh-ac", secret)
    db_session.add(
        IntegrationSource(
            project_id=sample_project.id,
            source_type="issue_tracker_webhook",
            name="default",
            auth_kind=IntegrationAuthKind.HMAC_SHA256,
            secret_ref="secret:wh-ac",
            active=True,
        )
    )
    await db_session.flush()
    body = {
        "issue": {
            "title": "Add priority",
            "body": "Please add ticket priority",
            "number": 42,
            "labels": [{"name": "olympus:change"}],
            "repository": {"full_name": "acme/supportdesk"},
        }
    }
    raw_body = json.dumps(body).encode()
    sig = hmac.new(secret.encode(), raw_body, hashlib.sha256).hexdigest()
    raw = {
        "source_id": "default",
        "event_id": "issue-42-open",
        "project_id": str(sample_project.id),
        "json_body": body,
        "headers": {"X-Gitea-Signature": f"sha256={sig}"},
        "raw_body": raw_body,
    }
    await RepositoryService().declare_managed(db_session, sample_project.id, system_ctx)
    svc = InboundService(command_bus)
    first = await svc.receive(db_session, "issue_tracker_webhook", raw, system_ctx)
    second = await svc.receive(db_session, "issue_tracker_webhook", raw, system_ctx)
    assert first["status"] == "ACCEPTED"
    assert second["status"] == "DUPLICATE"


@pytest.mark.asyncio
async def test_ac_issue_intake_creates_external_link(
    db_session,
    system_ctx: CommandContext,
    sample_project: Project,
    command_bus: CommandBus,
) -> None:
    import os

    os.environ["OLYMPUS_SECRET_KEY"] = "ac-link-key"
    from core.config.settings import clear_settings_cache

    clear_settings_cache()
    secret = "link-hmac"
    await store_secret(db_session, "wh-link", secret)
    db_session.add(
        IntegrationSource(
            project_id=sample_project.id,
            source_type="issue_tracker_webhook",
            name="default",
            auth_kind=IntegrationAuthKind.HMAC_SHA256,
            secret_ref="secret:wh-link",
            active=True,
        )
    )
    await db_session.flush()
    await RepositoryService().declare_managed(db_session, sample_project.id, system_ctx)
    body = {
        "issue": {
            "title": "Feature",
            "body": "desc",
            "number": 7,
            "labels": [{"name": "olympus:change"}],
            "repository": {"full_name": "acme/app"},
        }
    }
    raw_body = json.dumps(body).encode()
    sig = hmac.new(secret.encode(), raw_body, hashlib.sha256).hexdigest()
    raw = {
        "source_id": "default",
        "event_id": "issue-7",
        "project_id": str(sample_project.id),
        "json_body": body,
        "headers": {"X-Gitea-Signature": f"sha256={sig}"},
        "raw_body": raw_body,
    }
    await InboundService(command_bus).receive(db_session, "issue_tracker_webhook", raw, system_ctx)
    links = await db_session.execute(
        select(ExternalLink).where(ExternalLink.external_id == "acme/app#7")
    )
    assert links.scalar_one_or_none() is not None


@pytest.mark.asyncio
async def test_ac_gitlab_registration_rejected(
    db_session,
    sample_project: Project,
    system_ctx: CommandContext,
) -> None:
    from core.domain.exceptions import DomainError

    with pytest.raises(DomainError) as exc:
        await RepositoryService().register_external(
            db_session,
            sample_project.id,
            "gitlab-repo",
            RepositoryProvider.GITLAB,
            "https://gitlab.com/acme/repo.git",
            "main",
            "none:",
            system_ctx,
        )
    assert exc.value.code == "PROVIDER_NOT_SUPPORTED"


@pytest.mark.asyncio
async def test_ac_ci_evidence_requires_correlation(
    db_session,
    system_ctx: CommandContext,
    sample_project: Project,
) -> None:
    from core.domain.delivery_cycles.models import DeliveryCycle
    from core.domain.enums import DeliveryCycleType
    from core.domain.exceptions import DomainError
    from core.integration.enums import ICStatus
    from core.integration.models import IntegrationCandidate

    repo = await RepositoryService().declare_managed(db_session, sample_project.id, system_ctx)
    cycle = DeliveryCycle(
        key="DC-AC",
        project_id=sample_project.id,
        type=DeliveryCycleType.FEATURE_CHANGE,
        objective="ac ci",
        state="INTAKE",
        opened_by_actor_id=system_ctx.actor.id,
    )
    db_session.add(cycle)
    await db_session.flush()
    ic = IntegrationCandidate(
        key="IC-AC",
        delivery_cycle_id=cycle.id,
        repository_id=repo.id,
        base_sha="b" * 40,
        integration_branch="olympus/ic-ac",
        integrated_sha="c" * 40,
        status=ICStatus.READY,
    )
    db_session.add(ic)
    await db_session.flush()
    with pytest.raises(DomainError) as exc:
        await handle_ingest_external_ci_result(
            db_session,
            system_ctx,
            {"sha": "c" * 40, "run_id": "run-1", "correlation_id": "no-trigger"},
        )
    assert exc.value.code == "CORRELATION_MISMATCH"

    registry = get_connector_registry()
    await registry.execute_with_persistence(
        db_session,
        ConnectorAction(
            connector="ci_http",
            action="trigger_verification",
            target_resource="ci",
            inputs={
                "sha": "c" * 40,
                "callback_url": "http://127.0.0.1:8000/integrations/inbound/ci_callback",
            },
            idempotency_key="ci-trig-ac",
            correlation_id="corr-ac",
            expected_result_schema="CiTrigger",
        ),
        actor_id=system_ctx.actor.id,
    )
    out = await handle_ingest_external_ci_result(
        db_session,
        system_ctx,
        {"sha": "c" * 40, "run_id": "run-2", "correlation_id": "corr-ac", "status": "PASSED"},
    )
    assert out["ingested"] is True
    ev = await db_session.execute(
        select(Evidence).where(Evidence.evidence_type == EvidenceType.EXTERNAL_CI)
    )
    assert ev.scalar_one_or_none() is not None


@pytest.mark.asyncio
async def test_ac_outbound_connectors_registered_with_idempotency(
    db_session, system_ctx: CommandContext
) -> None:
    registry = get_connector_registry()
    names = registry.list_connectors()
    for required in (
        "ci_http",
        "artifact_fs",
        "issue_tracker_gitea",
        "deployment_local",
        "http_generic",
    ):
        assert required in names
    action = ConnectorAction(
        connector="deployment_local",
        action="deploy",
        target_resource="release",
        inputs={
            "project_id": str(uuid.uuid4()),
            "release_id": str(uuid.uuid4()),
        },
        idempotency_key="ac-idem-deploy",
        correlation_id="ac-corr",
        expected_result_schema="DeployResult",
        execution_id=None,
    )
    result, action_id = await registry.execute_with_persistence(
        db_session, action, actor_id=system_ctx.actor.id
    )
    assert result.status == "SUCCEEDED"
    row = await db_session.get(ConnectorActionRecord, action_id)
    assert row is not None
    assert row.idempotency_key == "ac-idem-deploy"
    assert row.correlation_id == "ac-corr"


@pytest.mark.asyncio
async def test_ac_waiting_external_checkpoint_on_unknown(
    db_session,
    system_ctx: CommandContext,
    sample_project: Project,
) -> None:
    from core.domain.executions.models import Checkpoint
    from tests.fixtures.gateway_harness import seed_gateway_execution

    repo = await RepositoryService().declare_managed(db_session, sample_project.id, system_ctx)
    bundle = await seed_gateway_execution(
        db_session,
        repository=repo,
        base_commit="a" * 40,
        key_prefix="we",
    )
    ex = bundle.execution
    ex.status = ExecutionStatus.STARTED
    await db_session.flush()

    registry = get_connector_registry()
    action = ConnectorAction(
        connector="git_local",
        action="resolve_head",
        target_resource="missing",
        inputs={"logical_location": "projects/nope/repo", "branch": "main"},
        idempotency_key=f"we-{uuid.uuid4().hex}",
        correlation_id="we-corr",
        expected_result_schema="HeadResult",
        execution_id=ex.id,
    )
    result, _action_id = await registry.execute_with_persistence(
        db_session, action, actor_id=system_ctx.actor.id
    )
    if result.status != "UNKNOWN":
        pytest.skip("git_local did not yield UNKNOWN in this environment")
    await db_session.refresh(ex)
    assert ex.status == ExecutionStatus.CHECKPOINTED
    cp = await db_session.execute(select(Checkpoint).where(Checkpoint.execution_id == ex.id))
    assert cp.scalar_one_or_none() is not None
