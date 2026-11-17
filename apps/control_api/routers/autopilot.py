"""Autopilot API: start a journey in one call, watch it, turn it on/off, retry a stopped step."""

from __future__ import annotations

import hashlib
import re
import uuid
from dataclasses import replace
from datetime import datetime
from pathlib import Path
from typing import Any

from core.autopilot.service import AutopilotService, supports
from core.commands.bus import CommandBus
from core.commands.context import CommandContext
from core.domain.delivery_cycles.models import DeliveryCycle
from core.domain.enums import DeliveryCycleType
from core.domain.exceptions import DomainError
from core.integrations.inbound.service import InboundService
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.ext.asyncio import AsyncSession

from apps.control_api.command_dispatch import dispatch
from apps.control_api.deps import command_context, get_command_bus, get_db

router = APIRouter(tags=["autopilot"])


class AutopilotView(BaseModel):
    delivery_cycle_id: uuid.UUID
    supported: bool
    enabled: bool
    status: str
    step: str
    message: str
    detail: dict[str, Any]
    last_error: str | None
    updated_at: datetime | None
    code_path: str | None = None


class SetAutopilotBody(BaseModel):
    model_config = ConfigDict(extra="forbid")

    enabled: bool


class StartBody(BaseModel):
    model_config = ConfigDict(extra="forbid")

    journey: DeliveryCycleType = DeliveryCycleType.GREENFIELD_BUILD
    name: str = Field(min_length=1, max_length=200)
    prd_title: str = Field(default="PRD", max_length=500)
    # Required for a new app (GREENFIELD_BUILD); ignored when onboarding an existing repo.
    prd_text: str | None = None
    # Folder on this machine the project comes from (`olympus start`). Required for
    # BROWNFIELD_ONBOARDING; optional for a new app (releases are delivered into it).
    local_path: str | None = Field(default=None, max_length=1024)


class StartResponse(BaseModel):
    project_id: uuid.UUID
    delivery_cycle_id: uuid.UUID
    autopilot: AutopilotView


def _code_path(cycle: DeliveryCycle) -> str | None:
    """Where the project's code lives on this machine (the canonical working copy)."""
    from core.repositories.workspace_locator import WorkspaceLocator

    if cycle.repository_id is None:
        return None
    locator = WorkspaceLocator()
    try:
        path = locator.resolve("LOCAL_FILESYSTEM", locator.canonical_location(cycle.project_id))
    except ValueError:
        return None
    return str(path) if path.exists() else None


async def _view(session: AsyncSession, cycle: DeliveryCycle) -> AutopilotView:
    state = await AutopilotService().get(session, cycle.id)
    if state is None:
        return AutopilotView(
            delivery_cycle_id=cycle.id,
            supported=supports(cycle.type),
            enabled=False,
            status="OFF",
            step="off",
            message="Autopilot is off",
            detail={},
            last_error=None,
            updated_at=None,
            code_path=_code_path(cycle),
        )
    return AutopilotView(
        delivery_cycle_id=cycle.id,
        supported=supports(cycle.type),
        enabled=state.enabled,
        status=state.status if state.enabled else "OFF",
        step=state.step,
        message=state.message if state.enabled else "Autopilot is off",
        detail=state.detail or {},
        last_error=state.last_error,
        updated_at=state.updated_at,
        code_path=_code_path(cycle),
    )


async def _cycle(session: AsyncSession, cycle_id: uuid.UUID) -> DeliveryCycle:
    cycle = await session.get(DeliveryCycle, cycle_id)
    if cycle is None:
        raise HTTPException(status_code=404, detail="Delivery cycle not found")
    return cycle


@router.get("/delivery-cycles/{cycle_id}/autopilot", response_model=AutopilotView)
async def get_autopilot(
    cycle_id: uuid.UUID,
    session: AsyncSession = Depends(get_db),
) -> AutopilotView:
    return await _view(session, await _cycle(session, cycle_id))


@router.put("/delivery-cycles/{cycle_id}/autopilot", response_model=AutopilotView)
async def set_autopilot(
    cycle_id: uuid.UUID,
    body: SetAutopilotBody,
    session: AsyncSession = Depends(get_db),
    ctx: CommandContext = Depends(command_context),
) -> AutopilotView:
    cycle = await _cycle(session, cycle_id)
    await AutopilotService().set_enabled(session, cycle.id, body.enabled, ctx)
    return await _view(session, cycle)


@router.post("/delivery-cycles/{cycle_id}/autopilot/retry", response_model=AutopilotView)
async def retry_autopilot(
    cycle_id: uuid.UUID,
    session: AsyncSession = Depends(get_db),
    ctx: CommandContext = Depends(command_context),
) -> AutopilotView:
    cycle = await _cycle(session, cycle_id)
    await AutopilotService().request_retry(session, cycle.id, ctx)
    return await _view(session, cycle)


def _project_key(name: str, idempotency_key: str | None) -> str:
    """Readable unique key; stable for a retried request so the replay matches."""
    slug = re.sub(r"[^A-Z0-9]+", "-", name.upper()).strip("-")[:40] or "PROJECT"
    if idempotency_key:
        suffix = hashlib.sha256(idempotency_key.encode()).hexdigest()[:4]
    else:
        suffix = uuid.uuid4().hex[:4]
    return f"{slug}-{suffix.upper()}"


def _local_folder(raw: str | None, *, must_be_git: bool) -> Path | None:
    if raw is None:
        return None
    path = Path(raw).expanduser()
    if not path.is_absolute():
        raise DomainError(code="INVALID_LOCAL_PATH", message="local_path must be absolute")
    path = path.resolve()
    if not path.is_dir():
        raise DomainError(code="INVALID_LOCAL_PATH", message=f"{path} is not a folder")
    if must_be_git and not (path / ".git").exists():
        raise DomainError(code="NOT_A_GIT_REPO", message=f"{path} is not a git repository")
    return path


@router.post("/start", response_model=StartResponse, status_code=201)
async def start_journey(
    body: StartBody,
    session: AsyncSession = Depends(get_db),
    ctx: CommandContext = Depends(command_context),
    bus: CommandBus = Depends(get_command_bus),
) -> StartResponse:
    """Start a journey with Autopilot on, in one call.

    - GREENFIELD_BUILD: new project from a PRD (the "Build a new app" screen, or
      `olympus start` in an empty folder).
    - BROWNFIELD_ONBOARDING: learn an existing git repository on this machine
      (`olympus start` in a project folder). Olympus clones it; it never edits the folder.
    """
    from core.domain.projects.models import Project
    from sqlalchemy import select

    greenfield = body.journey == DeliveryCycleType.GREENFIELD_BUILD
    if body.journey not in (
        DeliveryCycleType.GREENFIELD_BUILD,
        DeliveryCycleType.BROWNFIELD_ONBOARDING,
    ):
        raise DomainError(
            code="AUTOPILOT_UNSUPPORTED",
            message="Only new apps and existing repos can be started this way for now",
        )
    if greenfield and not (body.prd_text or "").strip():
        raise DomainError(code="PRD_REQUIRED", message="A new app needs a PRD (prd_text)")
    if not greenfield and body.local_path is None:
        raise DomainError(
            code="LOCAL_PATH_REQUIRED", message="Onboarding needs the repository folder"
        )
    folder = _local_folder(body.local_path, must_be_git=not greenfield)
    if folder is not None:
        taken = (
            await session.execute(select(Project).where(Project.local_path == str(folder)))
        ).scalar_one_or_none()
        if taken is not None:
            raise DomainError(
                code="FOLDER_ALREADY_A_PROJECT",
                message=f"{folder} is already the project “{taken.name}”",
            )
    name = body.name.strip()

    def step(suffix: str) -> CommandContext:
        # One request runs several commands; each needs its own idempotency key, or the
        # second would be rejected as a replay of the first with a different body.
        key = f"{ctx.idempotency_key}/{suffix}" if ctx.idempotency_key else None
        return replace(ctx, idempotency_key=key)

    project = await dispatch(
        session,
        bus,
        name="create_project",
        target_type="project",
        target_id=name,
        payload={"key": _project_key(name, ctx.idempotency_key), "name": name},
        ctx=step("project"),
    )
    project_id = uuid.UUID(project.data["project_id"])
    project_row = await session.get(Project, project_id)
    assert project_row is not None
    if folder is not None:
        project_row.local_path = str(folder)

    repository_id: str | None = None
    if not greenfield:
        assert folder is not None
        registered = await dispatch(
            session,
            bus,
            name="register_repository",
            target_type="project",
            target_id=str(project_id),
            payload={
                "project_id": str(project_id),
                "name": folder.name or name,
                "provider": "LOCAL",
                "remote_url": folder.as_uri(),
                "source_type": "EXTERNAL_CLONE",
                "default_branch": None,
                "credential_ref": "none:",
            },
            ctx=step("repository"),
        )
        repository_id = str(registered.data["repository_id"])

    created = await dispatch(
        session,
        bus,
        name="create_delivery_cycle",
        target_type="project",
        target_id=str(project_id),
        payload={
            "project_id": str(project_id),
            "type": body.journey.value,
            "objective": (f"Build {name}" if greenfield else f"Learn {name}")[:4096],
            "repository_id": repository_id,
        },
        ctx=step("cycle"),
    )
    cycle_id = uuid.UUID(created.data["cycle_id"])
    if greenfield:
        await InboundService(bus).receive(
            session,
            "document_upload",
            {
                "project_id": str(project_id),
                "source_id": str(project_id),
                "event_id": f"start-{cycle_id}",
                "delivery_cycle_id": str(cycle_id),
                "json_body": {
                    "title": body.prd_title.strip() or "PRD",
                    "text": body.prd_text,
                    "lineage_key": "default",
                    "source_type": "PRD",
                },
                "lineage_key": "default",
                "source_type_label": "PRD",
            },
            step("prd"),
        )
    await AutopilotService().set_enabled(session, cycle_id, True, ctx)
    cycle = await _cycle(session, cycle_id)
    return StartResponse(
        project_id=project_id,
        delivery_cycle_id=cycle_id,
        autopilot=await _view(session, cycle),
    )


class LocalProject(BaseModel):
    project_id: uuid.UUID
    name: str
    local_path: str
    latest_run: HomeRun | None


@router.get("/local-projects", response_model=LocalProject)
async def find_local_project(
    path: str,
    session: AsyncSession = Depends(get_db),
) -> LocalProject:
    """The project started from this folder (used by `olympus start` / `olympus status`)."""
    from core.domain.projects.models import Project
    from sqlalchemy import select

    folder = str(Path(path).expanduser().resolve())
    project = (
        await session.execute(select(Project).where(Project.local_path == folder))
    ).scalar_one_or_none()
    if project is None:
        raise HTTPException(status_code=404, detail=f"No project for {folder}")
    latest = (
        await session.execute(
            select(DeliveryCycle)
            .where(DeliveryCycle.project_id == project.id)
            .order_by(DeliveryCycle.created_at.desc())
            .limit(1)
        )
    ).scalar_one_or_none()
    return LocalProject(
        project_id=project.id,
        name=project.name,
        local_path=folder,
        latest_run=await _home_run(session, latest) if latest else None,
    )


class ReviewItemView(BaseModel):
    subject_type: str
    subject_id: str
    group: str
    title: str
    detail: str | None
    suggestion: str
    why: str | None
    keep_label: str
    drop_label: str


class ReviewChoice(BaseModel):
    model_config = ConfigDict(extra="forbid")

    subject_type: str
    subject_id: str
    choice: str = Field(pattern="^(keep|drop)$")


class ReviewBody(BaseModel):
    model_config = ConfigDict(extra="forbid")

    # Items left out take Olympus's suggestion.
    choices: list[ReviewChoice] = Field(default_factory=list)


@router.get("/delivery-cycles/{cycle_id}/autopilot/review", response_model=list[ReviewItemView])
async def get_review(
    cycle_id: uuid.UUID,
    session: AsyncSession = Depends(get_db),
) -> list[ReviewItemView]:
    """What onboarding learned and still needs the person's confirmation."""
    from core.autopilot.review import pending_items

    await _cycle(session, cycle_id)
    return [ReviewItemView(**item.as_dict()) for item in await pending_items(session, cycle_id)]


@router.post("/delivery-cycles/{cycle_id}/autopilot/review", response_model=AutopilotView)
async def submit_review(
    cycle_id: uuid.UUID,
    body: ReviewBody,
    session: AsyncSession = Depends(get_db),
    ctx: CommandContext = Depends(command_context),
) -> AutopilotView:
    """Record the person's decisions (their own action), then let Autopilot continue."""
    from core.autopilot.review import apply_choices

    cycle = await _cycle(session, cycle_id)
    choices = {(c.subject_type, c.subject_id): c.choice for c in body.choices}
    await apply_choices(session, cycle.id, choices, ctx)
    if await AutopilotService().get(session, cycle.id) is not None:
        await AutopilotService().advance_as_system(session, cycle.id, ctx.correlation_id)
    return await _view(session, cycle)


class HomeRun(BaseModel):
    delivery_cycle_id: uuid.UUID
    type: str
    state: str
    objective: str
    created_at: datetime
    autopilot: AutopilotView


async def _home_run(session: AsyncSession, cycle: DeliveryCycle) -> HomeRun:
    return HomeRun(
        delivery_cycle_id=cycle.id,
        type=cycle.type.value,
        state=cycle.state,
        objective=cycle.objective,
        created_at=cycle.created_at,
        autopilot=await _view(session, cycle),
    )


class HomeProject(BaseModel):
    id: uuid.UUID
    key: str
    name: str
    local_path: str | None = None
    latest_run: HomeRun | None


@router.get("/home", response_model=list[HomeProject])
async def home(session: AsyncSession = Depends(get_db)) -> list[HomeProject]:
    """Every project with its most recent run, newest activity first (the Home screen)."""
    from core.domain.projects.models import Project
    from sqlalchemy import select

    projects = list((await session.execute(select(Project))).scalars())
    cycles = list(
        (
            await session.execute(select(DeliveryCycle).order_by(DeliveryCycle.created_at.desc()))
        ).scalars()
    )
    latest: dict[uuid.UUID, DeliveryCycle] = {}
    for row in cycles:
        latest.setdefault(row.project_id, row)
    out: list[HomeProject] = []
    for project in projects:
        last = latest.get(project.id)
        run = await _home_run(session, last) if last is not None else None
        out.append(
            HomeProject(
                id=project.id,
                key=project.key,
                name=project.name,
                local_path=project.local_path,
                latest_run=run,
            )
        )
    out.sort(
        key=lambda p: p.latest_run.created_at if p.latest_run else datetime.min,
        reverse=True,
    )
    return out


LocalProject.model_rebuild()
