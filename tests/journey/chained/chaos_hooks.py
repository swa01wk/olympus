"""Chaos injection for chained MVP (Phase 19 §4.6) and RC-01 wiring."""

from __future__ import annotations

import os
import subprocess
import uuid
from datetime import UTC, datetime, timedelta

from core.commands.context import CommandContext
from core.domain.enums import ExecutionStatus, LeaseState, WorkType
from core.domain.executions.models import Execution, ExecutionLease
from core.domain.tasks.models import Task
from core.execution.leases.sweeper import LeaseSweeper
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

_rc01_forge_done = False
_rc04_sentinel_done = False
_docker_worker_kill_done = False
_control_api_restart_done = False


def _chaos_enabled() -> bool:
    return os.environ.get("MVP_CHAOS") == "1"


def kill_docker_execution_worker_once() -> bool:
    """RC-01: SIGKILL the demo stack execution-worker container (once per run)."""
    global _docker_worker_kill_done
    if _docker_worker_kill_done or os.environ.get("MVP_CHAOS_FORGE_KILL") != "1":
        return False
    try:
        proc = subprocess.run(
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
                "ps",
                "-q",
                "execution-worker",
            ],
            capture_output=True,
            text=True,
            check=False,
            timeout=30,
        )
        cid = (proc.stdout or "").strip().splitlines()
        if not cid:
            return False
        subprocess.run(
            ["docker", "kill", "-s", "KILL", cid[0]],
            check=False,
            timeout=15,
        )
        _docker_worker_kill_done = True
        return True
    except (OSError, subprocess.TimeoutExpired):
        return False


def restart_control_api_once() -> bool:
    """Chaos: restart control-api during SSE / UI walkthrough (demo stack only)."""
    global _control_api_restart_done
    if _control_api_restart_done or os.environ.get("MVP_CHAOS_SSE_RESTART") != "1":
        return False
    try:
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
                "restart",
                "control-api",
            ],
            check=False,
            timeout=120,
        )
        _control_api_restart_done = True
        return True
    except (OSError, subprocess.TimeoutExpired):
        return False


def _cycle_from_env() -> uuid.UUID | None:
    raw = os.environ.get("MVP_CHAOS_CYCLE_ID", "").strip()
    if not raw:
        return None
    try:
        return uuid.UUID(raw)
    except ValueError:
        return None


async def inject_rc01_forge_lease_expiry(
    session: AsyncSession,
    ctx: CommandContext,
    delivery_cycle_id: uuid.UUID | None,
) -> bool:
    """In-process RC-01 surrogate: expire lease on STARTED CODE_CHANGE execution."""
    global _rc01_forge_done
    if _rc01_forge_done or os.environ.get("MVP_CHAOS_FORGE_KILL") != "1":
        return False
    kill_docker_execution_worker_once()

    if delivery_cycle_id is None:
        delivery_cycle_id = _cycle_from_env()

    stmt = (
        select(Execution)
        .join(Task, Task.id == Execution.task_id)
        .where(
            Execution.status == ExecutionStatus.STARTED,
            Task.work_type == WorkType.CODE_CHANGE,
        )
    )
    if delivery_cycle_id is not None:
        stmt = stmt.where(Task.delivery_cycle_id == delivery_cycle_id)
    execution = (await session.execute(stmt.limit(1))).scalar_one_or_none()
    if execution is None:
        return False

    lease = (
        await session.execute(
            select(ExecutionLease).where(
                ExecutionLease.execution_id == execution.id,
                ExecutionLease.state == LeaseState.ACTIVE,
            )
        )
    ).scalar_one_or_none()
    if lease is None:
        return False

    lease.expires_at = datetime.now(UTC) - timedelta(seconds=30)
    swept = await LeaseSweeper().sweep_expired(session, ctx)
    if swept:
        _rc01_forge_done = True
        return True
    return False


async def inject_sentinel_lease_expiry(
    session: AsyncSession,
    ctx: CommandContext,
    delivery_cycle_id: uuid.UUID,
) -> bool:
    """DC-004 chaos: expire lease during sentinel.execute (VERIFICATION tasks)."""
    global _rc04_sentinel_done
    if _rc04_sentinel_done or os.environ.get("MVP_CHAOS_SENTINEL_LEASE") != "1":
        return False

    execution = (
        await session.execute(
            select(Execution)
            .join(Task, Task.id == Execution.task_id)
            .where(
                Execution.status == ExecutionStatus.STARTED,
                Task.delivery_cycle_id == delivery_cycle_id,
                Task.work_type == WorkType.VERIFICATION,
            )
            .limit(1)
        )
    ).scalar_one_or_none()
    if execution is None:
        return False

    lease = (
        await session.execute(
            select(ExecutionLease).where(
                ExecutionLease.execution_id == execution.id,
                ExecutionLease.state == LeaseState.ACTIVE,
            )
        )
    ).scalar_one_or_none()
    if lease is None:
        return False

    lease.expires_at = datetime.now(UTC) - timedelta(seconds=30)
    if await LeaseSweeper().sweep_expired(session, ctx) > 0:
        _rc04_sentinel_done = True
        return True
    return False


async def maybe_chaos_before_worker_round(
    session: AsyncSession,
    ctx: CommandContext,
    *,
    delivery_cycle_id: uuid.UUID | None = None,
) -> None:
    if not _chaos_enabled():
        return
    await inject_rc01_forge_lease_expiry(session, ctx, delivery_cycle_id)
    if delivery_cycle_id is not None:
        await inject_sentinel_lease_expiry(session, ctx, delivery_cycle_id)
