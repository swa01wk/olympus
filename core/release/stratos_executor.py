"""Deterministic stratos.release executor."""

from __future__ import annotations

import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from core.assurance.findings import FindingService
from core.commands.context import CommandContext
from core.domain.delivery_cycles.models import DeliveryCycle
from core.domain.repositories.models import Repository, RepositoryWorkspace
from core.execution.executors.base import ExecutionContext, ExecutorOutcome
from core.integration.enums import FindingSeverity, FindingSource
from core.integrations.connectors.base import ConnectorAction
from core.integrations.connectors.registry import get_connector_registry
from core.release.eligibility import ReleaseEligibilityService
from core.release.enums import ReleaseStatus
from core.release.models import Release
from core.repositories.revision import RepositoryRevisionService
from core.traceability.models import RepositoryIndexPointer


async def run_stratos_release(
    session: AsyncSession,
    ctx: ExecutionContext,
    command_ctx: CommandContext,
) -> ExecutorOutcome:
    release = await _load_release(session, ctx)
    if release is None:
        return ExecutorOutcome(
            status="FAILED", error_code="RELEASE_MISSING", error_message="release"
        )
    cycle = await session.get(DeliveryCycle, release.delivery_cycle_id)
    if cycle is None:
        return ExecutorOutcome(status="FAILED", error_code="CYCLE_MISSING", error_message="cycle")
    eligible, conditions = await ReleaseEligibilityService().evaluate(
        session, cycle, release=release
    )
    if not eligible:
        await _fail_release(
            session,
            release,
            cycle,
            command_ctx,
            "RELEASE_TOCTOU_INELIGIBLE",
            {"conditions": [c.name for c in conditions if not c.ok]},
            ctx.execution.id,
        )
        return ExecutorOutcome(
            status="FAILED",
            error_code="NOT_ELIGIBLE",
            error_message="Release no longer eligible",
        )
    repo = await session.get(Repository, cycle.repository_id)
    if repo is None or repo.workspace_id is None or repo.default_branch is None:
        return ExecutorOutcome(status="FAILED", error_code="REPO_MISSING", error_message="repo")
    ws = await session.get(RepositoryWorkspace, repo.workspace_id)
    if ws is None:
        return ExecutorOutcome(status="FAILED", error_code="WORKSPACE_MISSING", error_message="ws")
    integrated_sha = release.integrated_sha
    tag = f"olympus/release/{release.key}"
    ref = f"refs/heads/{repo.default_branch}"
    logical = ws.logical_location
    registry = get_connector_registry()
    ff = ConnectorAction(
        connector="git_local",
        action="fast_forward_ref",
        target_resource=str(repo.id),
        inputs={
            "logical_location": logical,
            "ref": ref,
            "target_sha": integrated_sha,
        },
        idempotency_key=f"release-ff:{release.id}:{integrated_sha}",
        correlation_id=command_ctx.correlation_id,
        expected_result_schema="FastForwardResult",
    )
    ff_result, _ = await registry.execute_with_persistence(
        session, ff, actor_id=command_ctx.actor.id
    )
    if ff_result.status != "SUCCEEDED":
        await _fail_release(
            session,
            release,
            cycle,
            command_ctx,
            "RELEASE_FF_DENIED",
            {"error": ff_result.error_class, "detail": ff_result.error_detail},
            ctx.execution.id,
        )
        return ExecutorOutcome(
            status="FAILED",
            error_code=ff_result.error_class or "FF_FAILED",
            error_message=ff_result.error_detail or "fast-forward failed",
        )
    tag_action = ConnectorAction(
        connector="git_local",
        action="create_tag",
        target_resource=str(repo.id),
        inputs={
            "logical_location": logical,
            "tag": tag,
            "target_sha": integrated_sha,
        },
        idempotency_key=f"release-tag:{release.id}:{tag}",
        correlation_id=command_ctx.correlation_id,
        expected_result_schema="CreateTagResult",
    )
    tag_result, _ = await registry.execute_with_persistence(
        session, tag_action, actor_id=command_ctx.actor.id
    )
    if tag_result.status != "SUCCEEDED":
        await _fail_release(
            session,
            release,
            cycle,
            command_ctx,
            "RELEASE_TAG_FAILED",
            {"error": tag_result.error_class},
            ctx.execution.id,
        )
        return ExecutorOutcome(
            status="FAILED",
            error_code=tag_result.error_class or "TAG_FAILED",
            error_message=tag_result.error_detail or "tag failed",
        )
    if repo.remote_url and repo.provider.value in {"GITHUB", "GITEA"}:
        from core.integrations.connectors.secrets import build_credential_resolver

        cred = await build_credential_resolver(session).resolve_async(repo.credential_ref)
        push = ConnectorAction(
            connector=f"git_provider_{repo.provider.value.lower()}",
            action="push_release",
            target_resource=str(repo.id),
            inputs={
                "logical_location": logical,
                "branch": repo.default_branch,
                "sha": integrated_sha,
                "tag": tag,
                "_credential": cred,
            },
            idempotency_key=f"release-remote:{release.id}",
            correlation_id=command_ctx.correlation_id,
            expected_result_schema="PushReleaseResult",
            policy_context={"release_executor": True},
        )
        push_result, _ = await registry.execute_with_persistence(
            session, push, actor_id=command_ctx.actor.id
        )
        if push_result.status != "SUCCEEDED":
            await _fail_release(
                session,
                release,
                cycle,
                command_ctx,
                "RELEASE_REMOTE_PUSH_FAILED",
                {"error": push_result.error_class},
                ctx.execution.id,
            )
            return ExecutorOutcome(
                status="FAILED",
                error_code=push_result.error_class or "REMOTE_PUSH",
                error_message=push_result.error_detail or "remote push failed",
            )
    try:
        await RepositoryRevisionService().mark_released(
            session, repo.id, integrated_sha, release.id, command_ctx
        )
        pointer = await session.get(RepositoryIndexPointer, repo.id)
        if pointer and pointer.canonical_index_version_id:
            pointer.released_index_version_id = pointer.canonical_index_version_id
        await session.flush()
    except Exception as exc:
        await _fail_release(
            session,
            release,
            cycle,
            command_ctx,
            "RELEASE_DB_FAILED",
            {"message": str(exc)},
            ctx.execution.id,
        )
        return ExecutorOutcome(status="FAILED", error_code="DB_FAILED", error_message=str(exc))
    return ExecutorOutcome(
        status="OUTPUT_PRODUCED",
        output={"status": "RELEASED", "tag": tag, "integrated_sha": integrated_sha},
    )


async def _load_release(session: AsyncSession, ctx: ExecutionContext) -> Release | None:
    for ref in ctx.contract.inputs:
        if ref.ref_type == "RELEASE":
            return await session.get(Release, ref.ref_id)
    return None


async def _fail_release(
    session: AsyncSession,
    release: Release,
    cycle: DeliveryCycle,
    command_ctx: CommandContext,
    category: str,
    detail: dict[str, object],
    execution_id: uuid.UUID,
) -> None:
    release.status = ReleaseStatus.FAILED
    await session.flush()
    await FindingService().create(
        session,
        project_id=cycle.project_id,
        delivery_cycle_id=cycle.id,
        source=FindingSource.INTEGRATION,
        category=category,
        severity=FindingSeverity.BLOCKER,
        title=f"Release {release.key} failed",
        detail=detail,
        ctx=command_ctx,
        integration_candidate_id=release.integration_candidate_id,
    )
    await _append_domain_event_release_failed(session, release, command_ctx, execution_id)


async def _append_domain_event_release_failed(
    session: AsyncSession,
    release: Release,
    command_ctx: CommandContext,
    execution_id: uuid.UUID,
) -> None:
    from core.domain.events.append import append_domain_event

    await append_domain_event(
        session,
        aggregate_type="release",
        aggregate_id=release.id,
        event_type="release.failed",
        payload={"execution_id": str(execution_id)},
        actor_id=command_ctx.actor.id,
        correlation_id=command_ctx.correlation_id,
        project_id=release.project_id,
        delivery_cycle_id=release.delivery_cycle_id,
    )
