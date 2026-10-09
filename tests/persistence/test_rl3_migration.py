"""RL3.1 migration upgrade/downgrade (enum value may remain on downgrade)."""

from __future__ import annotations

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine


@pytest.mark.persistence
async def test_rl3_migration_round_trip(
    alembic_config: Config,
    async_engine: AsyncEngine,
) -> None:
    command.upgrade(alembic_config, "0033_rl3_review_gates")
    async with async_engine.connect() as conn:
        col = await conn.scalar(
            text(
                "SELECT 1 FROM information_schema.columns "
                "WHERE table_name='expected_behavior_resolutions' "
                "AND column_name='contradicted_baseline_ids'"
            )
        )
        prov = await conn.scalar(
            text(
                "SELECT 1 FROM information_schema.columns "
                "WHERE table_name='behavioral_baselines' AND column_name='provisional'"
            )
        )
    assert col == 1
    assert prov == 1
    command.downgrade(alembic_config, "0032_p18_security_observability")
    async with async_engine.connect() as conn:
        col = await conn.scalar(
            text(
                "SELECT 1 FROM information_schema.columns "
                "WHERE table_name='expected_behavior_resolutions' "
                "AND column_name='contradicted_baseline_ids'"
            )
        )
    assert col is None
    command.upgrade(alembic_config, "head")
