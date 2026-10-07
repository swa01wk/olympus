"""Restart boundaries and canonical fingerprint (Phase 19 §4.4)."""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
import uuid
from collections.abc import Callable, Coroutine
from typing import Any

from core.domain.enums import ExecutionStatus
from core.domain.executions.models import Execution
from core.ops.invariants import assert_system_invariants
from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from tests.journey.helpers import wait_for

_ACTIVE_EXEC = {
    ExecutionStatus.LEASED,
    ExecutionStatus.STARTED,
    ExecutionStatus.OUTPUT_PRODUCED,
    ExecutionStatus.VALIDATING,
}


async def wait_for_quiescent_executions(session: AsyncSession) -> None:
    count = (
        await session.execute(
            select(func.count()).select_from(Execution).where(Execution.status.in_(_ACTIVE_EXEC))
        )
    ).scalar_one()
    if count > 0:
        raise RuntimeError("executions still active before restart boundary")


async def canonical_fingerprint(session: AsyncSession, project_id: uuid.UUID) -> str:
    """Stable hash over canonical delivery state (runtime-excluded)."""
    parts: dict[str, Any] = {}

    async def _rows(sql: str, **params: Any) -> list[dict[str, Any]]:
        result = await session.execute(text(sql), params)
        keys = result.keys()
        return [dict(zip(keys, row, strict=True)) for row in result.fetchall()]

    parts["project"] = await _rows(
        "SELECT id, key, readiness_state FROM projects WHERE id = :pid",
        pid=project_id,
    )
    parts["cycles"] = await _rows(
        "SELECT id, key, type, state FROM delivery_cycles WHERE project_id = :pid ORDER BY key",
        pid=project_id,
    )
    parts["releases"] = await _rows(
        """
        SELECT r.id, r.key, r.status, ic.integrated_sha
        FROM releases r
        JOIN integration_candidates ic ON ic.id = r.integration_candidate_id
        WHERE r.project_id = :pid
        ORDER BY r.key
        """,
        pid=project_id,
    )
    parts["index_pointer"] = await _rows(
        """
        SELECT rip.repository_id, rip.canonical_index_version_id, civ.commit_sha
        FROM repository_index_pointers rip
        JOIN code_index_versions civ ON civ.id = rip.canonical_index_version_id
        JOIN repositories rep ON rep.id = rip.repository_id
        WHERE rep.project_id = :pid
        """,
        pid=project_id,
    )
    payload = json.dumps(parts, sort_keys=True, default=str, separators=(",", ":"))
    return hashlib.sha256(payload.encode()).hexdigest()


async def truncate_langgraph_runtime(session: AsyncSession) -> None:
    schema = os.environ.get("RUNTIME_CHECKPOINT_SCHEMA", "langgraph_runtime")
    await session.execute(text(f'DROP SCHEMA IF EXISTS "{schema}" CASCADE'))
    await session.execute(text(f'CREATE SCHEMA IF NOT EXISTS "{schema}"'))


def _docker_compose_stop_workers() -> None:
    if os.environ.get("MVP_RESTART_DOCKER", "").strip() != "1":
        return
    subprocess.run(
        [
            "docker",
            "compose",
            "-f",
            "docker-compose.yml",
            "-f",
            "deploy/compose.test.yaml",
            "-f",
            "deploy/compose.demo.yaml",
            "stop",
            "control-api",
            "scheduler-worker",
            "execution-worker",
        ],
        check=False,
    )


def _docker_compose_start_workers() -> None:
    if os.environ.get("MVP_RESTART_DOCKER", "").strip() != "1":
        return
    subprocess.run(
        [
            "docker",
            "compose",
            "-f",
            "docker-compose.yml",
            "-f",
            "deploy/compose.test.yaml",
            "-f",
            "deploy/compose.demo.yaml",
            "--profile",
            "integrations",
            "--profile",
            "demo",
            "up",
            "-d",
            "control-api",
            "scheduler-worker",
            "execution-worker",
        ],
        check=False,
    )


async def restart_boundary(
    name: str,
    *,
    factory: async_sessionmaker[AsyncSession],
    project_id: uuid.UUID,
    fingerprints: dict[str, tuple[str, str]],
    ready_probe: Callable[[], Coroutine[Any, Any, bool]] | None = None,
) -> None:
    async with factory() as session, session.begin():
        await wait_for_quiescent_executions(session)
        before = await canonical_fingerprint(session, project_id)

    _docker_compose_stop_workers()

    async with factory() as session, session.begin():
        await truncate_langgraph_runtime(session)

    _docker_compose_start_workers()

    if ready_probe is not None:
        await wait_for(ready_probe, timeout=300.0, interval=3.0)

    async with factory() as session, session.begin():
        after = await canonical_fingerprint(session, project_id)
        report = await assert_system_invariants(session, project_id)
        if not report.ok:
            raise AssertionError(f"invariants failed after {name}: {report.violations}")
    if before != after:
        raise AssertionError(f"fingerprint mismatch at {name}: {before} != {after}")
    fingerprints[name] = (before, after)
