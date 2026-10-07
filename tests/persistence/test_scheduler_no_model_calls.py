from __future__ import annotations

import pytest
from core.commands.context import CommandContext
from core.domain.model_calls.models import ModelCall
from core.execution.snapshots.base_commit import BaseCommitResolver
from core.scheduler.admission import AdmissionService
from core.scheduler.context_loader import load_eligibility_context, load_task_view
from core.scheduler.eligibility import evaluate
from core.scheduler.refs import build_default_registry
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from tests.fixtures.execution_harness import seed_ready_task

pytestmark = pytest.mark.persistence


async def _model_call_count(session: AsyncSession) -> int:
    return int((await session.execute(select(func.count()).select_from(ModelCall))).scalar_one())


@pytest.mark.asyncio
async def test_admission_does_not_create_model_calls(async_engine) -> None:
    factory = async_sessionmaker(bind=async_engine, class_=AsyncSession, expire_on_commit=False)
    async with factory() as session, session.begin():
        before = await _model_call_count(session)
        bundle = await seed_ready_task(session, key_prefix="no-llm-adm")
        ctx = CommandContext(actor=bundle.actor, correlation_id="no-llm")
        view = await load_task_view(session, bundle.task)
        elig_ctx = await load_eligibility_context(
            session,
            bundle.task,
            ref_registry=build_default_registry(),
            base_resolver=BaseCommitResolver(),
        )
        evaluate(view, elig_ctx)
        await AdmissionService().admit_task(session, bundle.task.id, ctx)
        await AdmissionService().admit_batch(session, 10, ctx)
        after = await _model_call_count(session)
        assert after == before
