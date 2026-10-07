"""Deterministic fault injection hooks (non-production only)."""

from __future__ import annotations

import os
from collections.abc import Iterator
from contextlib import contextmanager
from typing import Literal

from core.config.settings import get_settings

FaultPoint = Literal[
    "after_snapshot_persist",
    "after_worktree_create",
    "mid_model_call",
    "after_candidate_commit",
    "during_ic_merge",
    "after_gate_finalize",
    "during_release_ff",
    "after_connector_send",
]


def faults_enabled() -> bool:
    if os.environ.get("OLYMPUS_FAULTS", "").strip() == "":
        return False
    settings = get_settings()
    return settings.olympus_env != "production"


@contextmanager
def fault_point(name: FaultPoint) -> Iterator[None]:
    if not faults_enabled():
        yield
        return
    active = os.environ.get("OLYMPUS_FAULT_POINT", "").strip()
    if active == name:
        raise RuntimeError(f"fault injected at {name}")
    yield
