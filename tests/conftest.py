from __future__ import annotations

import logging
import os

# Ryuk often breaks port mapping on Docker Desktop (testcontainers#433).
os.environ.setdefault("TESTCONTAINERS_RYUK_DISABLED", "true")
from collections.abc import AsyncIterator, Iterator
from contextlib import contextmanager
from pathlib import Path

import pytest
from alembic import command

collect_ignore = ["fixtures/repos"]

_SESSION_OLYMPUS_WORKSPACE: str | None = None
_SESSION_OLYMPUS_STORAGE: str | None = None

from alembic.config import Config
from core.config.settings import clear_settings_cache
from core.db.engine import dispose_engine
from core.db.session import reset_session_factory
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from testcontainers.community.postgres import PostgresContainer


@pytest.fixture(scope="session")
def postgres_url() -> Iterator[str]:
    with PostgresContainer("pgvector/pgvector:pg16") as postgres:
        url = postgres.get_connection_url()
        if url.startswith("postgresql+psycopg2://"):
            async_url = url.replace("postgresql+psycopg2://", "postgresql+psycopg://", 1)
        elif url.startswith("postgresql://"):
            async_url = url.replace("postgresql://", "postgresql+psycopg://", 1)
        else:
            async_url = url
        yield async_url


@pytest.fixture(scope="session", autouse=True)
def _test_env(postgres_url: str, tmp_path_factory: pytest.TempPathFactory) -> Iterator[None]:
    global _SESSION_OLYMPUS_WORKSPACE, _SESSION_OLYMPUS_STORAGE
    # Ryuk often breaks port mapping on Docker Desktop for macOS (testcontainers#433).
    os.environ.setdefault("TESTCONTAINERS_RYUK_DISABLED", "true")
    workspace = tmp_path_factory.mktemp("workspace")
    storage = tmp_path_factory.mktemp("storage")
    os.environ["DATABASE_URL"] = postgres_url
    os.environ["OLYMPUS_ENV"] = "test"
    os.environ["OLYMPUS_WORKSPACE_ROOT"] = str(workspace)
    os.environ["OLYMPUS_STORAGE_ROOT"] = str(storage)
    _SESSION_OLYMPUS_WORKSPACE = str(workspace)
    _SESSION_OLYMPUS_STORAGE = str(storage)
    if os.environ.get("LLM_LIVE_TESTS") != "1":
        os.environ["LLM_LIVE_TESTS"] = "0"
    clear_settings_cache()
    from core.bootstrap.connectors import ensure_connectors_registered

    ensure_connectors_registered()
    yield
    clear_settings_cache()


@pytest.fixture(scope="session")
def alembic_config() -> Config:
    root = Path(__file__).resolve().parents[1]
    return Config(str(root / "alembic.ini"))


@contextmanager
def _quiet_alembic_migration_logs() -> Iterator[None]:
    """Alembic logs every revision at INFO; keep pytest failure output readable."""
    logger = logging.getLogger("alembic.runtime.migration")
    prev = logger.level
    logger.setLevel(logging.WARNING)
    try:
        yield
    finally:
        logger.setLevel(prev)


@pytest.fixture(scope="session")
def migrated_db(postgres_url: str, alembic_config: Config, _test_env: None) -> Iterator[str]:
    # Round-trip downgrade/upgrade is covered by tests/integration/test_db_and_migrations.py.
    # Session Postgres is discarded when the container stops; no teardown migrate needed.
    with _quiet_alembic_migration_logs():
        command.upgrade(alembic_config, "head")
    yield postgres_url


@pytest.fixture(scope="session")
async def async_engine(migrated_db: str) -> AsyncIterator[AsyncEngine]:
    engine = create_async_engine(migrated_db, pool_pre_ping=True)
    yield engine
    await engine.dispose()


@pytest.fixture
async def db_session(async_engine: AsyncEngine) -> AsyncIterator[AsyncSession]:
    connection = await async_engine.connect()
    transaction = await connection.begin()
    session_factory = async_sessionmaker(
        bind=connection,
        class_=AsyncSession,
        expire_on_commit=False,
    )
    session = session_factory()
    try:
        yield session
    finally:
        await session.close()
        await transaction.rollback()
        await connection.close()


@pytest.fixture(autouse=True)
def _restore_olympus_filesystem_roots() -> Iterator[None]:
    """Tests that relocate OLYMPUS_* roots must not leak paths into later git/index tests."""
    yield
    if _SESSION_OLYMPUS_WORKSPACE is not None:
        os.environ["OLYMPUS_WORKSPACE_ROOT"] = _SESSION_OLYMPUS_WORKSPACE
    if _SESSION_OLYMPUS_STORAGE is not None:
        os.environ["OLYMPUS_STORAGE_ROOT"] = _SESSION_OLYMPUS_STORAGE
    clear_settings_cache()


@pytest.fixture(autouse=True)
def _reset_engine_singletons() -> Iterator[None]:
    yield
    reset_session_factory()


@pytest.fixture(autouse=True)
async def _dispose_engine_after_test() -> AsyncIterator[None]:
    yield
    await dispose_engine()
    reset_session_factory()


pytest_plugins = ["tests.plugins.live_guard"]
