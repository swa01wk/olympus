from __future__ import annotations

import pytest
from core.commands.context import CommandContext
from core.domain.enums import RepositoryProvider, RepositoryStatus
from core.domain.exceptions import DomainError
from core.domain.executions.models import ExecutionSnapshot
from core.domain.task_contracts.schemas import TaskContractBody
from core.domain.task_contracts.service import ContractService
from core.execution.snapshots.base_commit import BaseCommitResolver
from core.execution.worker import ExecutionWorker
from core.repositories.service import RepositoryService
from core.scheduler.admission import AdmissionService
from core.scheduler.context_loader import load_eligibility_context, load_task_view
from core.scheduler.eligibility import evaluate
from core.scheduler.refs import build_default_registry
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from tests.fixtures.execution_harness import seed_ready_task
from tests.fixtures.repositories import materialize_existing_repository

pytestmark = [pytest.mark.workflow, pytest.mark.integration]


@pytest.mark.asyncio
async def test_repository_gates_eligibility_and_snapshot(async_engine, tmp_path) -> None:
    factory = async_sessionmaker(bind=async_engine, class_=AsyncSession, expire_on_commit=False)
    async with factory() as session, session.begin():
        bundle = await seed_ready_task(session, key_prefix="repo-elig")
        origin = tmp_path / "origin"
        origin.mkdir(parents=True, exist_ok=True)
        repo = await RepositoryService().register_external(
            session,
            bundle.project.id,
            "repo-gate",
            RepositoryProvider.LOCAL,
            f"file://{origin.resolve()}",
            "main",
            "none:",
            bundle.ctx,
        )
        bundle.cycle.repository_id = repo.id
        base_body = TaskContractBody.model_validate(bundle.contract.body)
        repo_body = base_body.model_copy(
            update={"repository_id": repo.id, "base_policy": "CYCLE_BASE"}
        )
        contracts = ContractService()
        draft = await contracts.create_draft(
            session, bundle.task.id, repo_body, "repo-test", bundle.ctx
        )
        issued = await contracts.issue(session, draft.id, bundle.ctx)
        bundle.task.current_contract_id = issued.id
        await session.flush()

        view = await load_task_view(session, bundle.task)
        elig_ctx = await load_eligibility_context(
            session,
            bundle.task,
            ref_registry=build_default_registry(),
            base_resolver=BaseCommitResolver(),
        )
        blocked = evaluate(view, elig_ctx)
        assert not blocked.eligible
        assert any(r.startswith("REPOSITORY_NOT_READY:") for r in blocked.reasons)

        head_sha = await materialize_existing_repository(session, repo.id, origin, bundle.ctx)
        bundle.cycle.base_sha = head_sha

        elig_ctx = await load_eligibility_context(
            session,
            bundle.task,
            ref_registry=build_default_registry(),
            base_resolver=BaseCommitResolver(),
        )
        assert evaluate(view, elig_ctx).eligible

        bundle.cycle.base_sha = "f" * 40
        elig_ctx = await load_eligibility_context(
            session,
            bundle.task,
            ref_registry=build_default_registry(),
            base_resolver=BaseCommitResolver(),
        )
        missing = evaluate(view, elig_ctx)
        assert not missing.eligible
        assert "BASE_COMMIT_UNAVAILABLE" in missing.reasons

        bundle.cycle.base_sha = head_sha
        ctx = CommandContext(actor=bundle.actor, correlation_id="repo-run")
        ex = await AdmissionService().admit_task(session, bundle.task.id, ctx)
        worker = ExecutionWorker(worker_id="repo-w")
        for _ in range(6):
            await worker.run_once(session, ctx)
            await session.refresh(ex)
            if ex.snapshot_id is not None:
                break
        assert ex.snapshot_id is not None
        snap_row = await session.get(ExecutionSnapshot, ex.snapshot_id)
        assert snap_row is not None
        assert snap_row.base_commit == head_sha
        assert snap_row.repository_id == repo.id
        repo_block = snap_row.content.get("repository")
        assert repo_block is not None
        assert repo_block.get("repository_id") == str(repo.id)
        assert repo_block.get("canonical_commit") == head_sha


@pytest.mark.asyncio
async def test_admission_rejects_repository_not_ready(async_engine, tmp_path) -> None:
    factory = async_sessionmaker(bind=async_engine, class_=AsyncSession, expire_on_commit=False)
    async with factory() as session, session.begin():
        bundle = await seed_ready_task(session, key_prefix="repo-adm")
        origin = tmp_path / "origin2"
        origin.mkdir(parents=True, exist_ok=True)
        repo = await RepositoryService().register_external(
            session,
            bundle.project.id,
            "repo-adm",
            RepositoryProvider.LOCAL,
            f"file://{origin.resolve()}",
            "main",
            "none:",
            bundle.ctx,
        )
        assert repo.status != RepositoryStatus.READY
        bundle.cycle.repository_id = repo.id
        body = TaskContractBody.model_validate(bundle.contract.body).model_copy(
            update={"repository_id": repo.id, "base_policy": "CYCLE_BASE"}
        )
        contracts = ContractService()
        draft = await contracts.create_draft(session, bundle.task.id, body, "t", bundle.ctx)
        issued = await contracts.issue(session, draft.id, bundle.ctx)
        bundle.task.current_contract_id = issued.id
        ctx = CommandContext(actor=bundle.actor, correlation_id="repo-block")
        with pytest.raises(DomainError) as exc:
            await AdmissionService().admit_task(session, bundle.task.id, ctx)
        assert exc.value.code == "NOT_ELIGIBLE"
