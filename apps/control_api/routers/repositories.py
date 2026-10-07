from __future__ import annotations

import uuid

from core.commands.bus import CommandBus
from core.commands.context import CommandContext
from core.domain.enums import RepositoryProvider, RepositorySourceType
from core.domain.repositories.materializations import RepositoryMaterialization
from core.domain.repositories.models import RepositoryRevision
from core.repositories.service import RepositoryService, RepositoryView
from fastapi import APIRouter, Depends
from pydantic import BaseModel, ConfigDict
from sqlalchemy.ext.asyncio import AsyncSession

from apps.control_api.command_dispatch import dispatch
from apps.control_api.deps import command_context, get_command_bus, get_db

router = APIRouter(tags=["repositories"])


class RegisterRepositoryRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str
    source_type: RepositorySourceType = RepositorySourceType.EXTERNAL_CLONE
    provider: RepositoryProvider
    remote_url: str
    default_branch: str | None = None
    credential_ref: str = "none:"


class WorkspaceResponse(BaseModel):
    id: uuid.UUID
    workspace_type: str
    storage_backend: str
    logical_location: str
    materialized_commit: str | None
    state: str


class RepositoryResponse(BaseModel):
    id: uuid.UUID
    project_id: uuid.UUID
    name: str
    source_type: str
    provider: str
    remote_url: str | None
    default_branch: str
    registered_sha: str | None
    canonical_commit: str | None
    released_commit: str | None
    status: str
    status_reason: str | None
    credential_ref: str
    credential_status: str
    workspace: WorkspaceResponse | None


class MaterializationAttemptResponse(BaseModel):
    id: uuid.UUID
    kind: str
    attempt: int
    status: str
    resulting_sha: str | None
    observed_default_branch: str | None
    error_class: str | None
    error_detail: str | None
    started_at: str
    finished_at: str | None


class RevisionResponse(BaseModel):
    sequence: int
    commit_sha: str
    cause: str
    integration_candidate_id: uuid.UUID | None = None
    release_id: uuid.UUID | None = None
    repository_event_id: uuid.UUID | None = None
    canonical_index_version_id: uuid.UUID | None = None
    created_at: str


def _to_response(view: RepositoryView) -> RepositoryResponse:
    ws = None
    if view.workspace:
        ws = WorkspaceResponse(
            id=view.workspace.id,
            workspace_type=view.workspace.workspace_type,
            storage_backend=view.workspace.storage_backend,
            logical_location=view.workspace.logical_location,
            materialized_commit=view.workspace.materialized_commit,
            state=view.workspace.state.value,
        )
    return RepositoryResponse(
        id=view.id,
        project_id=view.project_id,
        name=view.name,
        source_type=view.source_type.value,
        provider=view.provider.value,
        remote_url=view.remote_url,
        default_branch=view.default_branch,
        registered_sha=view.registered_sha,
        canonical_commit=view.canonical_commit,
        released_commit=view.released_commit,
        status=view.status.value,
        status_reason=view.status_reason,
        credential_ref=view.credential_ref,
        credential_status=view.credential_status,
        workspace=ws,
    )


@router.post(
    "/projects/{project_id}/repositories", response_model=RepositoryResponse, status_code=201
)
async def register_repository(
    project_id: uuid.UUID,
    body: RegisterRepositoryRequest,
    session: AsyncSession = Depends(get_db),
    ctx: CommandContext = Depends(command_context),
    bus: CommandBus = Depends(get_command_bus),
) -> RepositoryResponse:
    if body.source_type != RepositorySourceType.EXTERNAL_CLONE:
        from core.domain.exceptions import DomainError

        raise DomainError(
            code="INVALID_SOURCE_TYPE",
            message="GREENFIELD_MANAGED cannot be registered via API",
        )
    payload = body.model_dump(mode="json")
    payload["project_id"] = str(project_id)
    result = await dispatch(
        session,
        bus,
        name="register_repository",
        target_type="project",
        target_id=str(project_id),
        payload=payload,
        ctx=ctx,
    )
    view = await RepositoryService().get_view(session, uuid.UUID(result.data["repository_id"]))
    return _to_response(view)


@router.get("/projects/{project_id}/repositories", response_model=list[RepositoryResponse])
async def list_project_repositories(
    project_id: uuid.UUID,
    session: AsyncSession = Depends(get_db),
) -> list[RepositoryResponse]:
    from core.domain.repositories.models import Repository
    from sqlalchemy import select

    result = await session.execute(select(Repository).where(Repository.project_id == project_id))
    views = []
    svc = RepositoryService()
    for repo in result.scalars():
        views.append(_to_response(await svc.get_view(session, repo.id)))
    return views


@router.get("/repositories/{repository_id}", response_model=RepositoryResponse)
async def get_repository(
    repository_id: uuid.UUID,
    session: AsyncSession = Depends(get_db),
) -> RepositoryResponse:
    view = await RepositoryService().get_view(session, repository_id)
    return _to_response(view)


@router.get(
    "/repositories/{repository_id}/materializations",
    response_model=list[MaterializationAttemptResponse],
)
async def list_materializations(
    repository_id: uuid.UUID,
    session: AsyncSession = Depends(get_db),
) -> list[MaterializationAttemptResponse]:
    from sqlalchemy import select

    result = await session.execute(
        select(RepositoryMaterialization)
        .where(RepositoryMaterialization.repository_id == repository_id)
        .order_by(RepositoryMaterialization.attempt)
    )
    return [
        MaterializationAttemptResponse(
            id=m.id,
            kind=m.kind.value,
            attempt=m.attempt,
            status=m.status.value,
            resulting_sha=m.resulting_sha,
            observed_default_branch=m.observed_default_branch,
            error_class=m.error_class,
            error_detail=m.error_detail,
            started_at=m.started_at.isoformat(),
            finished_at=m.finished_at.isoformat() if m.finished_at else None,
        )
        for m in result.scalars()
    ]


@router.post("/repositories/{repository_id}/commands/retry_materialization")
async def retry_materialization(
    repository_id: uuid.UUID,
    session: AsyncSession = Depends(get_db),
    ctx: CommandContext = Depends(command_context),
    bus: CommandBus = Depends(get_command_bus),
) -> RepositoryResponse:
    await dispatch(
        session,
        bus,
        name="retry_materialization",
        target_type="repository",
        target_id=str(repository_id),
        payload={"repository_id": str(repository_id)},
        ctx=ctx,
    )
    view = await RepositoryService().get_view(session, repository_id)
    return _to_response(view)


@router.get("/repositories/{repository_id}/code-index/canonical")
async def get_canonical_code_index(
    repository_id: uuid.UUID,
    session: AsyncSession = Depends(get_db),
) -> dict[str, object]:
    from core.domain.repositories.models import Repository
    from core.intelligence.code_index.models import CodeIndexVersion
    from core.traceability.models import RepositoryIndexPointer

    repo = await session.get(Repository, repository_id)
    if repo is None:
        from fastapi import HTTPException

        raise HTTPException(status_code=404, detail="Repository not found")
    pointer = await session.get(RepositoryIndexPointer, repository_id)
    version = None
    if pointer and pointer.canonical_index_version_id:
        version = await session.get(CodeIndexVersion, pointer.canonical_index_version_id)
    return {
        "repository_id": str(repository_id),
        "canonical_commit": repo.canonical_commit,
        "canonical_index_version_id": (
            str(pointer.canonical_index_version_id)
            if pointer and pointer.canonical_index_version_id
            else None
        ),
        "commit_sha": version.commit_sha if version else None,
        "index_version_status": version.status.value if version else None,
    }


class AttachRemoteRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    provider: RepositoryProvider
    remote_url: str
    credential_ref: str = "none:"


@router.post("/repositories/{repository_id}/sync")
async def sync_repository(
    repository_id: uuid.UUID,
    session: AsyncSession = Depends(get_db),
    ctx: CommandContext = Depends(command_context),
) -> dict[str, object]:
    from core.repositories.sync import RepositorySyncService

    event = await RepositorySyncService().sync(session, repository_id, ctx)
    await session.commit()
    return {
        "repository_event_id": str(event.id) if event else None,
        "classification": event.classification if event else None,
    }


@router.post("/repositories/{repository_id}/commands/attach_remote")
async def attach_remote(
    repository_id: uuid.UUID,
    body: AttachRemoteRequest,
    session: AsyncSession = Depends(get_db),
    ctx: CommandContext = Depends(command_context),
    bus: CommandBus = Depends(get_command_bus),
) -> RepositoryResponse:
    result = await dispatch(
        session,
        bus,
        name="attach_remote",
        target_type="repository",
        target_id=str(repository_id),
        payload={
            "repository_id": str(repository_id),
            **body.model_dump(mode="json"),
        },
        ctx=ctx,
    )
    view = await RepositoryService().get_view(session, uuid.UUID(result.data["repository_id"]))
    return _to_response(view)


@router.post("/repositories/{repository_id}/commands/acknowledge_rewrite")
async def acknowledge_rewrite(
    repository_id: uuid.UUID,
    session: AsyncSession = Depends(get_db),
    ctx: CommandContext = Depends(command_context),
) -> dict[str, object]:
    from core.repositories.sync import RepositorySyncService

    revision = await RepositorySyncService().acknowledge_rewrite(session, repository_id, ctx)
    await session.commit()
    return {"revision_sequence": revision.sequence, "commit_sha": revision.commit_sha}


@router.get("/repositories/{repository_id}/events")
async def list_repository_events(
    repository_id: uuid.UUID,
    session: AsyncSession = Depends(get_db),
) -> list[dict[str, object]]:
    from core.domain.integrations.models import RepositoryEvent
    from sqlalchemy import select

    rows = await session.execute(
        select(RepositoryEvent)
        .where(RepositoryEvent.repository_id == repository_id)
        .order_by(RepositoryEvent.created_at.desc())
    )
    return [
        {
            "id": str(e.id),
            "ref": e.ref,
            "before_sha": e.before_sha,
            "after_sha": e.after_sha,
            "classification": e.classification,
            "processed_at": e.processed_at.isoformat() if e.processed_at else None,
        }
        for e in rows.scalars()
    ]


@router.get("/repositories/{repository_id}/revisions", response_model=list[RevisionResponse])
async def list_revisions(
    repository_id: uuid.UUID,
    session: AsyncSession = Depends(get_db),
) -> list[RevisionResponse]:
    from sqlalchemy import select

    result = await session.execute(
        select(RepositoryRevision)
        .where(RepositoryRevision.repository_id == repository_id)
        .order_by(RepositoryRevision.sequence)
    )
    return [
        RevisionResponse(
            sequence=r.sequence,
            commit_sha=r.commit_sha,
            cause=r.cause.value,
            integration_candidate_id=r.integration_candidate_id,
            release_id=r.release_id,
            repository_event_id=r.repository_event_id,
            canonical_index_version_id=r.canonical_index_version_id,
            created_at=r.created_at.isoformat(),
        )
        for r in result.scalars()
    ]
