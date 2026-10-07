"""Phase 16 live journey: Gitea issue → Feature Change → Release R2 + integrations."""

from __future__ import annotations

import os
import uuid
from pathlib import Path

import pytest
from core.commands.context import CommandContext
from core.domain.delivery_cycles.models import DeliveryCycle
from core.domain.enums import ProjectReadiness
from core.domain.projects.models import Project
from core.domain.repositories.models import Repository
from core.product_model.changes.models import ChangeRequest
from core.release.enums import ReleaseStatus
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker
from tests.fixtures.code_index_harness import SUPPORTDESK_R1
from tests.fixtures.planning_workflow_harness import ensure_system_actor
from tests.journey.feature_change_acceptance import assert_feature_change_phase14_acceptance
from tests.journey.feature_change_live_pipeline import run_feature_change_live_journey
from tests.journey.gitea_integration_helpers import (
    attach_repository_to_gitea,
    create_gitea_issue,
    create_gitea_repo,
    deliver_issue_webhook,
    ensure_integration_sources,
    ensure_journey_secret_key,
    gitea_api_token,
    gitea_owner_login,
    gitea_reachable,
    run_post_release_integrations,
)
from tests.journey.helpers import assert_live_llm_proof
from tests.journey.seed import TRUSTED_SEED, seed_trusted_project
from tests.live_credentials import any_live_provider_configured

CHANGE_TEXT = (
    Path(__file__).resolve().parents[1] / "fixtures" / "supportdesk" / "change_priority.md"
)

pytestmark = [
    pytest.mark.journey,
    pytest.mark.asyncio,
]


@pytest.mark.skipif(
    os.environ.get("LLM_LIVE_TESTS") != "1",
    reason="Set LLM_LIVE_TESTS=1 for live issue-tracker journey",
)
@pytest.mark.skipif(
    not os.environ.get("GITEA_API_TOKEN"),
    reason="Set GITEA_API_TOKEN (make integrations-up && make integrations-seed)",
)
async def test_feature_change_via_issue_tracker(
    async_engine: AsyncEngine,
) -> None:
    if not any_live_provider_configured():
        pytest.skip("No live provider API key configured")
    if not gitea_reachable():
        pytest.skip("Gitea not reachable (make integrations-up)")

    ensure_journey_secret_key()
    os.environ.setdefault("MODEL_PRODUCT_DECOMPOSITION", os.environ.get("MODEL_DEFAULT", ""))
    os.environ.setdefault("MODEL_PLANNING", os.environ.get("MODEL_DEFAULT", ""))
    os.environ.setdefault("MODEL_IMPLEMENTATION", os.environ.get("MODEL_DEFAULT", ""))
    from core.config.settings import clear_settings_cache
    from core.runtime.model_policy import clear_models_config_cache

    clear_settings_cache()
    clear_models_config_cache()

    token = gitea_api_token()
    owner = gitea_owner_login(token)
    repo_name = f"supportdesk-journey-{uuid.uuid4().hex[:8]}"
    create_gitea_repo(owner, repo_name, token)
    title = "Add ticket priority to SupportDesk"
    description = CHANGE_TEXT.read_text(encoding="utf-8")
    issue_number, external_ref = create_gitea_issue(
        owner, repo_name, token, title=title, body=description
    )
    webhook_secret = f"journey-wh-{uuid.uuid4().hex[:8]}"
    ci_secret = "ci-test-secret"

    factory = async_sessionmaker(bind=async_engine, class_=AsyncSession, expire_on_commit=False)
    project_id: uuid.UUID
    fc_cycle_id: uuid.UUID

    async with factory() as session, session.begin():
        actor = await ensure_system_actor(session)
        ctx = CommandContext(actor=actor, correlation_id="p16-journey-seed")
        trusted = await seed_trusted_project(session, SUPPORTDESK_R1, TRUSTED_SEED, ctx)
        project_id = trusted.project_id
        await ensure_integration_sources(
            session, project_id, webhook_secret=webhook_secret, ci_secret=ci_secret
        )
        inbound = await deliver_issue_webhook(
            session,
            ctx,
            project_id=project_id,
            owner=owner,
            repo_name=repo_name,
            issue_number=issue_number,
            title=title,
            body=description,
            webhook_secret=webhook_secret,
            event_id=f"gitea-issue-{issue_number}",
        )
        assert inbound["status"] == "ACCEPTED"
        cr = (
            await session.execute(
                select(ChangeRequest).where(ChangeRequest.project_id == project_id)
            )
        ).scalar_one()
        fc_cycle_id = cr.delivery_cycle_id
        assert cr.external_ref == external_ref

    ic, release = await run_feature_change_live_journey(
        factory,
        project_id=project_id,
        fc_cycle_id=fc_cycle_id,
        correlation_prefix="p16-fc",
    )

    remote_url = f"{os.environ.get('OLYMPUS_GITEA_URL', 'http://127.0.0.1:3000').rstrip('/')}/{owner}/{repo_name}.git"
    async with factory() as session, session.begin():
        actor = await ensure_system_actor(session)
        ctx = CommandContext(actor=actor, correlation_id="p16-post-release")
        cycle = await session.get(DeliveryCycle, fc_cycle_id)
        assert cycle is not None and cycle.repository_id is not None
        repo = await session.get(Repository, cycle.repository_id)
        assert repo is not None
        repo = await attach_repository_to_gitea(session, ctx, repo, remote_url)
        integration_out = await run_post_release_integrations(
            session,
            ctx,
            project_id=project_id,
            repository=repo,
            ic=ic,
            release=release,
            owner=owner,
            repo_name=repo_name,
            issue_number=issue_number,
            ci_secret=ci_secret,
        )

    async with factory() as session:
        cycle = await session.get(DeliveryCycle, fc_cycle_id)
        project = await session.get(Project, project_id)
        cr = (
            await session.execute(
                select(ChangeRequest).where(ChangeRequest.delivery_cycle_id == fc_cycle_id)
            )
        ).scalar_one()
        assert cycle is not None and cycle.state == "COMPLETE"
        assert project is not None
        assert project.readiness_state == ProjectReadiness.READY_FOR_CHANGE
        assert cr.status == "DONE"
        assert release.status == ReleaseStatus.RELEASED
        assert ic.integrated_sha is not None
        assert integration_out["deploy_status"]["status"] == "HEALTHY"
        assert integration_out["external_ci_recorded"] is True
        assert integration_out["external_link"] is True
        assert integration_out["comment_status"] == "SUCCEEDED"
        assert integration_out["close_status"] == "SUCCEEDED"

        await assert_live_llm_proof(
            session,
            fc_cycle_id,
            (
                "product_decomposition",
                "planning",
                "implementation",
            ),
        )
        await assert_feature_change_phase14_acceptance(
            session,
            project_id=project_id,
            cycle_id=fc_cycle_id,
            ic=ic,
            release=release,
        )
