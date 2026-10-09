"""A NEW_FEATURE interpretation never reuses an existing feature key."""

from __future__ import annotations

import uuid

import pytest
from core.commands.context import CommandContext
from core.product_model.changes.schemas import ChangeInterpretation
from core.product_model.changes.service import ChangeRequestService
from core.product_model.models import Feature
from core.product_model.schemas import FeatureSpecBody
from sqlalchemy import select
from tests.fixtures.code_index_harness import SUPPORTDESK_R1
from tests.journey.seed import TRUSTED_SEED, seed_trusted_project

pytestmark = [pytest.mark.integration, pytest.mark.asyncio]


async def test_new_feature_with_taken_key_gets_sequence_key(
    db_session, system_ctx: CommandContext
) -> None:
    trusted = await seed_trusted_project(db_session, SUPPORTDESK_R1, TRUSTED_SEED, system_ctx)
    svc = ChangeRequestService()
    cr = await svc.intake(
        db_session,
        project_id=trusted.project_id,
        title="Priority",
        description="Add ticket priority and page on HIGH.",
        source_type="change_request_api",
        external_ref="new-feature-key-1",
        inbound_event_id=None,
        ctx=system_ctx,
    )
    assert cr.delivery_cycle_id is not None
    existing = (
        (await db_session.execute(select(Feature).where(Feature.project_id == trusted.project_id)))
        .scalars()
        .first()
    )
    assert existing is not None

    await svc.persist_interpretation(
        db_session,
        cr.delivery_cycle_id,
        ChangeInterpretation(
            resolution="NEW_FEATURE_IN_CAPABILITY",
            feature_key=existing.key,
            proposed_feature_spec=FeatureSpecBody(
                behavior="Tickets carry a priority",
                summary="Ticket priority",
                inputs=[],
                outputs=[],
                rules=[],
            ),
            architecture_change_expected=False,
            architecture_rationale="none",
            candidate_ranking_rationale="test",
        ),
        uuid.uuid4(),
        system_ctx,
    )

    await db_session.refresh(cr)
    created = await db_session.get(Feature, cr.resolved_feature_id)
    assert created is not None and created.id != existing.id
    assert created.key.startswith("FEAT-") and created.key != existing.key
