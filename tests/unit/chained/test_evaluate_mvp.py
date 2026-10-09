"""Evaluator check helpers (Phase 19 §12)."""

from __future__ import annotations

import uuid

import pytest
from core.domain.enums import ProjectReadiness
from core.domain.projects.models import Project
from scripts.acceptance.evaluate_mvp import _db_checks
from sqlalchemy.ext.asyncio import AsyncSession


@pytest.mark.persistence
@pytest.mark.asyncio
async def test_db_checks_fail_without_releases(db_session: AsyncSession) -> None:
    project = Project(key=f"EV-{uuid.uuid4().hex[:6]}", name="ev")
    project.readiness_state = ProjectReadiness.UNKNOWN
    db_session.add(project)
    await db_session.flush()
    checks = await _db_checks(db_session, project.id, fingerprints={}, chaos=False)
    names = {c.name for c in checks}
    assert "releases_r1_r2_r3_released" in names
    rel_check = next(c for c in checks if c.name == "releases_r1_r2_r3_released")
    assert rel_check.ok is False
