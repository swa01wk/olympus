from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager, suppress

from core.commands.registry import build_command_bus
from core.config.settings import OlympusSettings, get_settings
from core.db.engine import create_async_engine_from_settings, dispose_engine
from core.db.session import create_session_factory, reset_session_factory
from core.domain.exceptions import DomainError
from core.observability.logging import configure_logging
from core.observability.otel import configure_otel
from core.observability.outbox import outbox_loop
from core.ops.startup_reconcilers import run_startup_reconcilers
from core.policy.policy_service import ensure_policy_version
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from starlette.responses import JSONResponse

from apps.control_api.errors import domain_error_handler
from apps.control_api.middleware import CorrelationIdMiddleware
from apps.control_api.middleware_security import RateLimitMiddleware, SecurityHeadersMiddleware
from apps.control_api.routers import (
    actions,
    actors,
    approvals,
    artifacts,
    assurance,
    audit,
    auth_tokens,
    baselines,
    brownfield,
    candidate_commits,
    changes,
    clarifications,
    code_intelligence,
    commands,
    connector_configs,
    connectors,
    contracts,
    defects,
    delivery_cycles,
    events,
    execution_workspaces,
    executions,
    external_links,
    findings,
    health,
    impact,
    inbound,
    integration,
    integration_candidates,
    integration_sources,
    lineage,
    metrics,
    ops,
    orchestrator,
    planning,
    policy,
    product_model,
    projects,
    promotion,
    readiness,
    reconciliation,
    releases,
    repositories,
    secrets,
    sources,
    spec_deltas,
    specs,
    tasks,
    views,
)


def _resolve_settings(app: FastAPI) -> OlympusSettings:
    override: OlympusSettings | None = getattr(app.state, "settings_override", None)
    if override is not None:
        return override
    return get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    settings = _resolve_settings(app)
    configure_logging(settings)
    configure_otel(settings)
    engine = create_async_engine_from_settings(settings)
    session_factory = create_session_factory()
    app.state.settings = settings
    app.state.engine = engine
    app.state.session_factory = session_factory
    app.state.command_bus = build_command_bus()
    with suppress(Exception):
        async with session_factory() as session, session.begin():
            await ensure_policy_version(session)
            await run_startup_reconcilers(session)
    outbox_task: asyncio.Task[None] | None = None
    if settings.olympus_env != "test":
        outbox_task = asyncio.create_task(outbox_loop(session_factory))
    yield
    if outbox_task is not None:
        outbox_task.cancel()
        with suppress(asyncio.CancelledError):
            await outbox_task
    await dispose_engine()
    reset_session_factory()


async def _handle_domain_error(request: Request, exc: Exception) -> JSONResponse:
    if not isinstance(exc, DomainError):
        raise exc
    return await domain_error_handler(request, exc)


def _dashboard_cors_origins(env: str) -> list[str]:
    if env not in {"local", "journey", "integration"}:
        return []
    ports = ("3000", "3001", "3010")
    hosts = ("localhost", "127.0.0.1")
    return [f"http://{host}:{port}" for host in hosts for port in ports]


def create_app(settings: OlympusSettings | None = None) -> FastAPI:
    app = FastAPI(title="Olympus Control API", lifespan=lifespan)
    app.state.settings_override = settings
    app.state.command_bus = build_command_bus()
    app.add_exception_handler(DomainError, _handle_domain_error)
    app.add_middleware(RateLimitMiddleware)
    app.add_middleware(SecurityHeadersMiddleware)
    app.add_middleware(CorrelationIdMiddleware)
    resolved = settings if settings is not None else get_settings()
    cors_origins = _dashboard_cors_origins(resolved.olympus_env)
    if cors_origins:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=cors_origins,
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )
    app.include_router(health.router)
    app.include_router(metrics.router)
    app.include_router(auth_tokens.router)
    app.include_router(actors.router)
    app.include_router(commands.router)
    app.include_router(views.router)
    app.include_router(orchestrator.router)
    app.include_router(projects.router)
    app.include_router(repositories.router)
    app.include_router(code_intelligence.router)
    app.include_router(delivery_cycles.router)
    app.include_router(tasks.router)
    app.include_router(executions.router)
    app.include_router(actions.router)
    app.include_router(connector_configs.router)
    app.include_router(connectors.router)
    app.include_router(candidate_commits.router)
    app.include_router(execution_workspaces.router)
    app.include_router(clarifications.router)
    app.include_router(artifacts.router)
    app.include_router(contracts.router)
    app.include_router(approvals.router)
    app.include_router(events.router)
    app.include_router(external_links.router)
    app.include_router(audit.router)
    app.include_router(ops.router)
    app.include_router(policy.router)
    app.include_router(sources.router)
    app.include_router(changes.router)
    app.include_router(defects.router)
    app.include_router(product_model.router)
    app.include_router(brownfield.router)
    app.include_router(baselines.router)
    app.include_router(promotion.router)
    app.include_router(readiness.router)
    app.include_router(specs.router)
    app.include_router(spec_deltas.router)
    app.include_router(impact.router)
    app.include_router(planning.router)
    app.include_router(inbound.router)
    app.include_router(integration.router)
    app.include_router(integration_sources.router)
    app.include_router(integration_candidates.router)
    app.include_router(findings.router)
    app.include_router(assurance.router)
    app.include_router(lineage.router)
    app.include_router(releases.router)
    app.include_router(reconciliation.router)
    app.include_router(secrets.router)
    return app


app = create_app()
