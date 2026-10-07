from __future__ import annotations

import os
import uuid
from pathlib import Path

import pytest
from core.commands.context import CommandContext
from core.domain.artifacts.models import Artifact
from core.domain.enums import ExecutionStatus, TaskStatus
from core.domain.executions.models import Execution
from core.domain.model_calls.models import ModelCall
from core.domain.task_contracts.schemas import TaskContractBody
from core.domain.task_contracts.service import ContractService
from core.execution.worker import ExecutionWorker
from core.scheduler.admission import AdmissionService
from sqlalchemy import select
from tests.fixtures.execution_harness import (
    contract_with_inputs,
    seed_input_artifact,
    seed_ready_task,
)
from tests.live_credentials import any_live_provider_configured

pytestmark = [pytest.mark.live_llm, pytest.mark.integration]


@pytest.mark.asyncio
async def test_execution_spine_diagnostic_live(db_session, system_actor) -> None:
    if os.getenv("LLM_LIVE_TESTS") != "1":
        pytest.skip("LLM_LIVE_TESTS not enabled")
    if not any_live_provider_configured():
        pytest.skip("No live provider API key configured")

    text = Path("tests/fixtures/diagnostic/paragraph.txt").read_text(encoding="utf-8")
    ctx = CommandContext(actor=system_actor, correlation_id="live-spine")
    bundle = await seed_ready_task(db_session, key_prefix="live", actor=system_actor)
    artifact_id = await seed_input_artifact(db_session, bundle, text=text)
    base = TaskContractBody.model_validate(bundle.contract.body)
    agent_body = contract_with_inputs(
        base,
        artifact_id,
        agent_profile="diagnostic.structured_echo",
        required_outputs=["artifact:DIAGNOSTIC_SUMMARY"],
    )
    contracts = ContractService()
    draft = await contracts.create_draft(db_session, bundle.task.id, agent_body, "live-test", ctx)
    issued = await contracts.issue(db_session, draft.id, ctx)
    bundle.task.current_contract_id = issued.id
    await db_session.flush()

    execution = await AdmissionService().admit_task(db_session, bundle.task.id, ctx)
    execution_id = execution.id
    worker = ExecutionWorker(worker_id=f"live-{uuid.uuid4().hex[:6]}")
    for _ in range(8):
        await worker.run_once(db_session, ctx)
        execution = await db_session.get(Execution, execution_id)
        assert execution is not None
        if execution.status == ExecutionStatus.COMPLETED:
            break

    assert execution.status == ExecutionStatus.COMPLETED
    await db_session.refresh(bundle.task)
    assert bundle.task.status == TaskStatus.COMPLETED

    arts = await db_session.execute(
        select(Artifact).where(
            Artifact.execution_id == execution.id,
            Artifact.kind == "DIAGNOSTIC_SUMMARY",
        )
    )
    assert arts.scalar_one_or_none() is not None

    calls = await db_session.execute(
        select(ModelCall).where(ModelCall.execution_id == execution.id)
    )
    call = calls.scalar_one_or_none()
    assert call is not None
    assert call.provider_request_id
