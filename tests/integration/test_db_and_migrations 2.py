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
    from alembic.script import ScriptDirectory

    command.downgrade(alembic_config, "base")
    script = ScriptDirectory.from_config(alembic_config)
    revisions = [r.revision for r in script.walk_revisions()]
    assert "0000_p00_baseline" in revisions
    for rev in (
        "0001_p01_repos",
        "0002_p01_tasks",
        "0003_p01_gov",
        "0004_p01_events",
        "0005_p02_model_calls",
    ):
        assert rev in revisions, f"missing migration revision {rev}"
    for rev in (
        "0001_p01_repos",
        "0002_p01_tasks",
        "0003_p01_gov",
        "0004_p01_events",
        "0005_p02_model_calls",
    ):
        command.upgrade(alembic_config, rev)
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
