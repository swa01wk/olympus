"""Phase 19 — four-journey chained MVP on one Project (live, --live-required)."""

from __future__ import annotations

import json
import os
import subprocess
import sys
import uuid
from pathlib import Path

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker
from tests.journey.chained.assertions import assert_chained_acceptance_criteria
from tests.journey.chained.runner import ChainedRunContext, run_chained_mvp
from tests.live_credentials import any_live_provider_configured

pytestmark = [
    pytest.mark.journey,
    pytest.mark.asyncio,
    pytest.mark.skipif(
        os.environ.get("LLM_LIVE_TESTS") != "1",
        reason="Set LLM_LIVE_TESTS=1 for chained MVP journey",
    ),
]


@pytest.mark.asyncio
async def test_mvp_chained_supportdesk(
    control_app,
    operator_token,
    async_engine: AsyncEngine,
) -> None:
    if not any_live_provider_configured():
        pytest.skip("No live provider API key configured")
    if os.environ.get("OLYMPUS_ENV", "local") not in {"journey", "local", "test"}:
        pytest.skip("Set OLYMPUS_ENV=journey for chained MVP")

    os.environ.setdefault("MODEL_PRODUCT_DECOMPOSITION", os.environ.get("MODEL_DEFAULT", ""))
    os.environ.setdefault("MODEL_PLANNING", os.environ.get("MODEL_DEFAULT", ""))
    os.environ.setdefault("MODEL_IMPLEMENTATION", os.environ.get("MODEL_DEFAULT", ""))
    os.environ.setdefault("MODEL_VERIFICATION_PLANNING", os.environ.get("MODEL_DEFAULT", ""))
    os.environ.setdefault("MODEL_REVIEW", os.environ.get("MODEL_DEFAULT", ""))
    os.environ.setdefault("MODEL_REPOSITORY_REASONING", os.environ.get("MODEL_DEFAULT", ""))

    transport = ASGITransport(app=control_app)
    async with AsyncClient(
        transport=transport,
        base_url="http://test",
        headers={"Authorization": f"Bearer {operator_token}"},
    ) as client:
        ctx = ChainedRunContext(
            async_engine=async_engine,
            client=client,
            operator_token=operator_token,
            human_token=operator_token,
            chaos=os.environ.get("MVP_CHAOS") == "1",
        )
        await run_chained_mvp(ctx)

    assert ctx.project_id is not None
    factory = async_sessionmaker(bind=async_engine, class_=AsyncSession, expire_on_commit=False)
    async with factory() as session:
        await assert_chained_acceptance_criteria(
            session,
            ctx.project_id,
            fingerprints=ctx.fingerprints,
        )

    run_id = uuid.uuid4().hex
    reports = Path("var/olympus/reports")
    reports.mkdir(parents=True, exist_ok=True)
    fp_path = reports / f"fingerprints_{run_id}.json"
    fp_path.write_text(
        json.dumps({k: [v[0], v[1]] for k, v in ctx.fingerprints.items()}),
        encoding="utf-8",
    )
    os.environ["MVP_PROJECT_ID"] = str(ctx.project_id)
    os.environ["MVP_FINGERPRINTS_JSON"] = fp_path.read_text(encoding="utf-8")
    eval_env = {
        **os.environ,
        "OLYMPUS_VIEWER_TOKEN": operator_token,
        "LLM_TEST_BUDGET_USD": os.environ.get("LLM_TEST_BUDGET_USD", "999"),
    }
    proc = subprocess.run(
        [
            sys.executable,
            "scripts/acceptance/evaluate_mvp.py",
            "--project",
            str(ctx.project_id),
            "--run-id",
            run_id,
            "--out",
            str(reports),
            "--fingerprints",
            str(fp_path),
        ]
        + (["--chaos"] if os.environ.get("MVP_CHAOS") == "1" else []),
        check=False,
        env=eval_env,
    )
    assert proc.returncode == 0, "MVP evaluator must exit 0"
