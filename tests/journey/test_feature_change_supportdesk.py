"""Journey 3 — Feature Change: ticket priority on SupportDesk R1 → Release R2."""

from __future__ import annotations

import os
import uuid
from pathlib import Path
from unittest.mock import patch

import pytest
from core.commands.context import CommandContext
from core.domain.delivery_cycles.models import DeliveryCycle
from core.domain.enums import (
    ProjectReadiness,
    SpecStatus,
)
from core.domain.projects.models import Project
from core.domain.repositories.models import Repository
from core.planning.models import ImplementationSpec
from core.product_model.changes.models import ChangeRequest
from core.product_model.models import AcceptanceCriterion
from core.release.enums import ReleaseStatus
from core.runtime.model_router import build_providers
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker
from tests.fixtures.code_index_harness import SUPPORTDESK_R1
from tests.fixtures.planning_workflow_harness import ensure_system_actor
from tests.journey.feature_change_acceptance import assert_feature_change_phase14_acceptance
from tests.journey.feature_change_helpers import assert_impact_includes_ticket_surface
from tests.journey.feature_change_live_pipeline import run_feature_change_live_journey
from tests.journey.helpers import assert_live_llm_proof
from tests.journey.seed import TRUSTED_SEED, seed_trusted_project
from tests.live_credentials import any_live_provider_configured

CHANGE_TEXT = (
    Path(__file__).resolve().parents[1] / "fixtures" / "supportdesk" / "change_priority.md"
)

pytestmark = [
    pytest.mark.journey,
    pytest.mark.asyncio,
    pytest.mark.skipif(
        os.environ.get("LLM_LIVE_TESTS") != "1",
        reason="Set LLM_LIVE_TESTS=1 for Feature Change journey",
    ),
]


@pytest.mark.asyncio
async def test_feature_change_supportdesk_end_to_end(
    control_app,
    operator_token,
    async_engine: AsyncEngine,
) -> None:
    if not any_live_provider_configured():
        pytest.skip("No live provider API key configured")

    os.environ.setdefault("MODEL_PRODUCT_DECOMPOSITION", os.environ.get("MODEL_DEFAULT", ""))
    os.environ.setdefault("MODEL_PLANNING", os.environ.get("MODEL_DEFAULT", ""))
    os.environ.setdefault("MODEL_IMPLEMENTATION", os.environ.get("MODEL_DEFAULT", ""))
    from core.config.settings import clear_settings_cache
    from core.runtime.model_policy import clear_models_config_cache

    clear_settings_cache()
    clear_models_config_cache()

    factory = async_sessionmaker(bind=async_engine, class_=AsyncSession, expire_on_commit=False)
    project_id: uuid.UUID
    fc_cycle_id: uuid.UUID

    async with factory() as session, session.begin():
        actor = await ensure_system_actor(session)
        ctx = CommandContext(actor=actor, correlation_id="fc-seed")
        trusted = await seed_trusted_project(session, SUPPORTDESK_R1, TRUSTED_SEED, ctx)
        project_id = trusted.project_id

    transport = ASGITransport(app=control_app)
    async with AsyncClient(
        transport=transport,
        base_url="http://test",
        headers={"Authorization": f"Bearer {operator_token}"},
    ) as client:
        cr_resp = await client.post(
            f"/projects/{project_id}/change-requests",
            json={
                "title": "Ticket priority",
                "description": CHANGE_TEXT.read_text(encoding="utf-8"),
                "external_ref": f"FC-{uuid.uuid4().hex[:8]}",
            },
            headers={"Idempotency-Key": f"fc-{uuid.uuid4().hex}"},
        )
        assert cr_resp.status_code == 200, cr_resp.text
        body = cr_resp.json()
        result = body.get("result") if isinstance(body.get("result"), dict) else body
        fc_cycle_id = uuid.UUID(str(result["delivery_cycle_id"]))

    with patch("core.runtime.model_router.build_providers", side_effect=build_providers):
        ic, release = await run_feature_change_live_journey(
            factory,
            project_id=project_id,
            fc_cycle_id=fc_cycle_id,
            correlation_prefix="fc",
        )
        async with factory() as session:
            await assert_impact_includes_ticket_surface(session, fc_cycle_id)
        async with factory() as session:
            delta_impl = (
                await session.execute(
                    select(ImplementationSpec).where(
                        ImplementationSpec.project_id == project_id,
                        ImplementationSpec.kind == "DELTA",
                    )
                )
            ).scalars()
            assert any(
                i.status in (SpecStatus.PROPOSED, SpecStatus.APPROVED) for i in delta_impl
            ), "expected ImplementationSpec DELTA after live planning"

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

        priority_ac = (
            await session.execute(
                select(AcceptanceCriterion).where(
                    AcceptanceCriterion.lineage_key.ilike("%PRIORITY%"),
                )
            )
        ).scalars()
        assert list(priority_ac), "expected priority-related AC after change"

        repo = await session.get(Repository, cycle.repository_id) if cycle.repository_id else None
        if repo and repo.canonical_commit:
            assert repo.canonical_commit == ic.integrated_sha

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
