from __future__ import annotations

import os
from collections.abc import AsyncIterator, Iterator
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from core.config.settings import clear_settings_cache
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
    workspace = tmp_path_factory.mktemp("workspace")
    storage = tmp_path_factory.mktemp("storage")
    os.environ["DATABASE_URL"] = postgres_url
    os.environ["OLYMPUS_ENV"] = "test"
    os.environ["OLYMPUS_WORKSPACE_ROOT"] = str(workspace)
    os.environ["OLYMPUS_STORAGE_ROOT"] = str(storage)
    os.environ["LLM_LIVE_TESTS"] = "0"
    clear_settings_cache()
    yield
    clear_settings_cache()


@pytest.fixture(scope="session")
def alembic_config() -> Config:
    root = Path(__file__).resolve().parents[1]
    return Config(str(root / "alembic.ini"))


@pytest.fixture(scope="session")
def migrated_db(postgres_url: str, alembic_config: Config, _test_env: None) -> Iterator[str]:
    command.upgrade(alembic_config, "head")
    yield postgres_url
    command.downgrade(alembic_config, "base")
    command.upgrade(alembic_config, "head")


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
def _reset_engine_singletons() -> Iterator[None]:
    yield
    reset_session_factory()
