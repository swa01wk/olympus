from __future__ import annotations

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine


@pytest.mark.persistence
async def test_migrations_round_trip(
    postgres_url: str,
    alembic_config: Config,
    async_engine: AsyncEngine,
) -> None:
    command.downgrade(alembic_config, "base")
    command.upgrade(alembic_config, "head")

    async with async_engine.connect() as conn:
        vector = await conn.scalar(text("SELECT 1 FROM pg_extension WHERE extname = 'vector'"))
        trgm = await conn.scalar(text("SELECT 1 FROM pg_extension WHERE extname = 'pg_trgm'"))
        schema = await conn.scalar(
            text(
                "SELECT 1 FROM information_schema.schemata WHERE schema_name = 'langgraph_runtime'"
            )
        )

    assert vector == 1
    assert trgm == 1
    assert schema == 1
