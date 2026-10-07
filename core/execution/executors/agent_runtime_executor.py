from __future__ import annotations

import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from core.execution.executors.base import ExecutionContext, ExecutorOutcome
from core.runtime.contracts import AgentRunRequest, ContextItem
from core.runtime.langgraph_runtime import LangGraphRuntime


class AgentRuntimeExecutor:
    def __init__(self, session: AsyncSession | None = None) -> None:
        self._session = session

    async def execute(self, ctx: ExecutionContext) -> ExecutorOutcome:
        if self._session is None:
            return ExecutorOutcome(
                status="FAILED",
                error_code="NO_SESSION",
                error_message="AgentRuntimeExecutor requires database session",
            )
        from sqlalchemy import select

        from core.domain.actors.models import Actor
        from core.domain.artifacts.models import Artifact
        from core.domain.enums import ActorKind
        from core.execution.artifacts import ArtifactStore
        from core.runtime.model_router import ModelRouter, build_providers

        actor_result = await self._session.execute(
            select(Actor).where(Actor.kind == ActorKind.SYSTEM).limit(1)
        )
        actor = actor_result.scalar_one()
        router = ModelRouter(
            self._session,
            actor_id=actor.id,
            providers=build_providers(),
        )
        from core.bootstrap.connectors import ensure_connectors_registered
        from core.domain.delivery_cycles.models import DeliveryCycle
        from core.domain.enums import WorkType
        from core.domain.projects.models import Project
        from core.execution.worktrees.manager import WorktreeManager
        from core.runtime.tool_client import DenyAllToolGateway
        from core.tools.client import GatewayToolClient
        from core.tools.tokens import default_token_expiry, issue_token, persist_token

        ensure_connectors_registered()
        tool_gateway: GatewayToolClient | DenyAllToolGateway = DenyAllToolGateway()
        if ctx.lease_id and ctx.contract.repository_id and ctx.snapshot.base_commit:
            from core.domain.repositories.models import Repository

            project_id: uuid.UUID | None = None
            cycle = await self._session.get(DeliveryCycle, ctx.execution.delivery_cycle_id)
            if cycle is not None:
                project_id = cycle.project_id
            else:
                repo_row = await self._session.get(Repository, ctx.contract.repository_id)
                if repo_row is not None:
                    project_id = repo_row.project_id
            project = await self._session.get(Project, project_id) if project_id else None
            if project is not None:
                wt_mgr = WorktreeManager()
                if ctx.contract.work_type == WorkType.CODE_CHANGE:
                    await wt_mgr.create(
                        self._session,
                        ctx.execution,
                        ctx.contract.repository_id,
                        ctx.snapshot.base_commit,
                        actor_id=actor.id,
                        correlation_id=str(ctx.execution.id),
                        project_id=project.id,
                    )
                elif ctx.contract.work_type in {WorkType.ANALYSIS, WorkType.VERIFICATION}:
                    await wt_mgr.create_readonly(
                        self._session,
                        ctx.execution,
                        ctx.contract.repository_id,
                        ctx.snapshot.base_commit,
                        actor_id=actor.id,
                        correlation_id=str(ctx.execution.id),
                        project_id=project.id,
                    )
                from core.domain.executions.models import ExecutionLease

                lease = await self._session.get(ExecutionLease, ctx.lease_id)
                if lease is not None:
                    expiry = default_token_expiry(lease)
                    raw, token_hash = issue_token(ctx.execution.id, lease.id, expiry)
                    import os

                    worker_id = os.environ.get("OLYMPUS_WORKER_ID")
                    await persist_token(
                        self._session,
                        ctx.execution.id,
                        lease.id,
                        token_hash,
                        default_token_expiry(lease),
                        worker_id=worker_id,
                    )
                    tool_gateway = GatewayToolClient(self._session, raw)
        runtime = LangGraphRuntime(self._session, router, tool_gateway=tool_gateway)
        from core.runtime.profiles.atlas import register_atlas_profile
        from core.runtime.profiles.forge import register_forge_profile
        from core.runtime.profiles.kira import register_kira_profile

        register_forge_profile()
        register_kira_profile()
        register_atlas_profile()
        from core.runtime.profiles.sentinel import register_sentinel_profiles
        from core.runtime.profiles.warden import register_warden_profile

        register_warden_profile()
        register_sentinel_profiles()
        from core.runtime.profiles.scout import register_scout_profile

        register_scout_profile()
        from core.runtime.profiles.orchestrator import register_orchestrator_profile

        register_orchestrator_profile()
        source_text = ""
        store = ArtifactStore()
        for item in ctx.contract.inputs:
            if item.ref_type == "ARTIFACT":
                artifact = await self._session.get(Artifact, item.ref_id)
                if artifact is not None:
                    if artifact.inline is not None:
                        source_text = str(artifact.inline)
                    else:
                        source_text = store.read_bytes(artifact).decode("utf-8", errors="replace")
        request = AgentRunRequest(
            run_id=ctx.execution.id,
            agent_profile=ctx.contract.agent_profile or "diagnostic.structured_echo",
            contract=ctx.contract,
            snapshot=ctx.snapshot.content,
            context=[
                ContextItem(kind="TEXT", content=source_text, provenance="DETERMINISTIC"),
            ],
            continuation=ctx.continuation,
        )
        if ctx.continuation:
            from core.runtime.contracts import AgentResumeRequest

            result = await runtime.resume(
                AgentResumeRequest(
                    run_id=ctx.execution.id,
                    agent_profile=request.agent_profile,
                    continuation=ctx.continuation,
                    contract=ctx.contract,
                    snapshot=ctx.snapshot.content,
                    context=request.context,
                )
            )
        else:
            result = await runtime.run(request)

        if result.status == "CHECKPOINT_REQUESTED":
            return ExecutorOutcome(
                status="CHECKPOINT_REQUESTED",
                checkpoint=result.checkpoint_request.model_dump(mode="json")
                if result.checkpoint_request
                else {},
                runtime_metadata=result.runtime_metadata,
                model_call_ids=list(result.model_call_ids),
            )
        if result.status == "FAILED":
            return ExecutorOutcome(
                status="FAILED",
                error_code=result.error.code if result.error else "RUNTIME_ERROR",
                error_message=result.error.message if result.error else "runtime failed",
                runtime_metadata=result.runtime_metadata,
                model_call_ids=list(result.model_call_ids),
            )
        if result.status == "CANCELLED":
            return ExecutorOutcome(status="CANCELLED", runtime_metadata=result.runtime_metadata)
        return ExecutorOutcome(
            status="OUTPUT_PRODUCED",
            output=result.output,
            runtime_metadata=result.runtime_metadata,
            model_call_ids=list(result.model_call_ids),
            artifacts=[a.model_dump(mode="json") for a in result.artifacts],
        )
