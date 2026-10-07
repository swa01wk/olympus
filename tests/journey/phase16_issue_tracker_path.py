"""Deterministic Phase 16 issue-tracker → connectors path (no live LLM)."""

from __future__ import annotations

import hashlib
import hmac
import json
import uuid

from core.bootstrap.connectors import ensure_connectors_registered
from core.commands.context import CommandContext
from core.commands.registry import build_command_bus
from core.domain.enums import IntegrationAuthKind
from core.domain.integrations.models import ExternalLink
from core.integrations.connectors.base import ConnectorAction
from core.integrations.connectors.registry import get_connector_registry
from core.integrations.connectors.secrets import store_secret
from core.integrations.inbound.models import IntegrationSource
from core.integrations.inbound.service import InboundService
from core.repositories.service import RepositoryService
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession


async def run_phase16_issue_tracker_acceptance(
    session: AsyncSession,
    ctx: CommandContext,
    *,
    project_id: uuid.UUID,
) -> dict[str, object]:
    """Issue webhook → CR + external_link; deploy_local HEALTHY; outbound connectors traced."""
    ensure_connectors_registered()

    from tests.journey.gitea_integration_helpers import ensure_journey_secret_key

    ensure_journey_secret_key()
    secret = "journey-webhook-secret"
    await store_secret(session, "journey-wh", secret)
    session.add(
        IntegrationSource(
            project_id=project_id,
            source_type="issue_tracker_webhook",
            name="default",
            auth_kind=IntegrationAuthKind.HMAC_SHA256,
            secret_ref="secret:journey-wh",
            active=True,
        )
    )
    await session.flush()
    await RepositoryService().declare_managed(session, project_id, ctx)
    body = {
        "issue": {
            "title": "Add ticket priority to SupportDesk",
            "body": "Operators need priority on tickets.",
            "number": 42,
            "labels": [{"name": "olympus:change"}],
            "repository": {"full_name": "acme/supportdesk"},
        }
    }
    raw_body = json.dumps(body).encode()
    sig = hmac.new(secret.encode(), raw_body, hashlib.sha256).hexdigest()
    raw = {
        "source_id": "default",
        "event_id": "journey-issue-42",
        "project_id": str(project_id),
        "json_body": body,
        "headers": {"X-Gitea-Signature": f"sha256={sig}"},
        "raw_body": raw_body,
    }
    bus = build_command_bus()
    inbound = await InboundService(bus).receive(session, "issue_tracker_webhook", raw, ctx)
    link = await session.execute(
        select(ExternalLink).where(ExternalLink.external_id == "acme/supportdesk#42")
    )
    assert link.scalar_one_or_none() is not None

    registry = get_connector_registry()
    release_id = str(uuid.uuid4())
    deploy = await registry.execute_with_persistence(
        session,
        ConnectorAction(
            connector="deployment_local",
            action="deploy",
            target_resource=f"release:{release_id}",
            inputs={"project_id": str(project_id), "release_id": release_id, "tag": "R2"},
            idempotency_key=f"journey-deploy:{release_id}",
            correlation_id=ctx.correlation_id,
            expected_result_schema="DeployResult",
        ),
        actor_id=ctx.actor.id,
    )
    assert deploy[0].status == "SUCCEEDED"
    return {
        "inbound_status": inbound["status"],
        "deploy_status": deploy[0].normalized_result,
        "release_id": release_id,
    }
