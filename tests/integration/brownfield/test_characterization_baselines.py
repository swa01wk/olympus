"""Characterization context, authored-test baselines and execution ordering (FakeProvider)."""

from __future__ import annotations

import os

import pytest
from agents.sentinel.schemas import CharacterizationCheck, CharacterizationPlan
from core.assurance.enums import EvidenceResult
from core.assurance.models import Evidence
from core.commands.context import CommandContext
from core.domain.enums import TaskStatus
from core.domain.task_contracts.models import TaskContract
from core.domain.tasks.models import Task
from core.intelligence.baselines.authored import AUTHORED_TEST_DIR
from core.intelligence.baselines.enums import BaselineSource, BaselineStatus
from core.intelligence.baselines.models import BehavioralBaseline
from core.intelligence.baselines.readiness import (
    _metric_baseline_coverage,
    _metric_principal_coverage,
)
from core.intelligence.recovered_specs.promotion import PromotionService
from core.product_model.models import FeatureSpec
from core.runtime.providers.fake_provider import FakeProvider
from core.traceability.models import RepositoryIndexPointer
from sqlalchemy import select
from tests.fixtures.brownfield_phase12_harness import (
    _activate_eligible_baselines,
    ensure_human_approver,
    recovery_to_baseline,
    run_baseline_stage_workers,
)

pytestmark = [pytest.mark.integration, pytest.mark.asyncio]

_PASSING = """\
import app.models.ticket  # noqa: F401
from app.db import Base, engine

Base.metadata.create_all(bind=engine)

from app.main import app
from fastapi.testclient import TestClient


def test_create_returns_201() -> None:
    with TestClient(app) as client:
        response = client.post("/tickets", json={"title": "Characterized", "status": "OPEN"})
        assert response.status_code == 201
"""


def _fake_env() -> None:
    os.environ["MODEL_PROVIDER"] = "anthropic"
    os.environ["MODEL_DEFAULT"] = "claude-3-5-haiku-20241022"
    os.environ["MODEL_REPOSITORY_REASONING"] = "claude-3-5-haiku-20241022"
    from core.config.settings import clear_settings_cache
    from core.runtime.model_policy import clear_models_config_cache

    clear_settings_cache()
    clear_models_config_cache()


async def _baseline_tasks(db_session, cycle_id) -> list[Task]:
    return list(
        (
            await db_session.execute(
                select(Task).where(
                    Task.delivery_cycle_id == cycle_id,
                    Task.title.startswith("Characterize")
                    | Task.title.startswith("Execute baseline checks"),
                )
            )
        )
        .scalars()
        .all()
    )


async def test_authored_characterization_test_runs_at_onboarding_sha(
    db_session,
    system_ctx: CommandContext,
) -> None:
    _fake_env()
    fake = FakeProvider()
    cycle, sha = await recovery_to_baseline(db_session, system_ctx, fake=fake)

    tasks = await _baseline_tasks(db_session, cycle.id)
    assert [t.title.split()[0] for t in tasks] == ["Characterize"], (
        "execution waits for characterize"
    )
    contract = await db_session.get(TaskContract, tasks[0].current_contract_id)
    assert contract is not None
    snap = contract.body["_snapshot"]
    assert [ac["recovered_ac_key"] for ac in snap["acs"]] == ["AC-1"]
    assert snap["behaviors"], "observed behaviours reach the prompt"
    assert "TestClient" in snap["code_excerpt"], "an existing test shows conventions"
    assert "app/main.py" in snap["code_excerpt"]

    plan = CharacterizationPlan(
        checks=[
            CharacterizationCheck(
                recovered_ac_key="AC-1",
                given="the service at the onboarding SHA",
                when="POST /tickets with a valid body",
                then="the response status is 201",
                kind="AUTHORED_TEST",
                test_filename="test_create.py",
                test_code=_PASSING,
            ),
            CharacterizationCheck(
                recovered_ac_key="AC-404",
                given="g",
                when="w",
                then="t",
                kind="AUTHORED_TEST",
                test_code=_PASSING,
            ),
        ],
    )
    await run_baseline_stage_workers(db_session, system_ctx, cycle.id, fake=fake, plans=[plan])

    tasks = await _baseline_tasks(db_session, cycle.id)
    assert {t.title.split()[0] for t in tasks} == {"Characterize", "Execute"}
    assert all(t.status == TaskStatus.COMPLETED for t in tasks)

    authored = (
        (
            await db_session.execute(
                select(BehavioralBaseline).where(
                    BehavioralBaseline.project_id == cycle.project_id,
                    BehavioralBaseline.source == BaselineSource.BROWNFIELD_CHARACTERIZATION,
                )
            )
        )
        .scalars()
        .all()
    )
    assert len(authored) == 1, "unknown AC keys are not persisted"
    baseline = authored[0]
    assert baseline.check_ref.startswith(f"{AUTHORED_TEST_DIR}/test_create_")
    assert baseline.check_artifact_id is not None
    assert baseline.established_sha == sha
    assert baseline.status == BaselineStatus.PROPOSED
    evidence = await db_session.get(Evidence, baseline.established_evidence_id)
    assert evidence is not None
    assert evidence.result == EvidenceResult.PASS, evidence.details

    # Promotion moves baselines and links onto the canonical successor; coverage follows.
    _human, human_ctx = await ensure_human_approver(db_session)
    recovered = await db_session.get(FeatureSpec, baseline.feature_spec_id)
    assert recovered is not None
    await PromotionService().decide(
        db_session, cycle.id, "FEATURE_SPEC", recovered.id, "PROMOTE_AS_CANONICAL", None, human_ctx
    )
    await _activate_eligible_baselines(db_session, cycle.id, human_ctx)
    await db_session.refresh(baseline)
    assert baseline.status == BaselineStatus.ACTIVE
    assert baseline.feature_spec_id != recovered.id
    coverage = await _metric_baseline_coverage(db_session, cycle, 1.0)
    assert coverage["ok"], coverage
    pointer = await db_session.get(RepositoryIndexPointer, cycle.repository_id)
    assert pointer is not None and pointer.canonical_index_version_id is not None
    principal = await _metric_principal_coverage(
        db_session, cycle, pointer.canonical_index_version_id, 0.0
    )
    assert principal["value"] > 0, principal
