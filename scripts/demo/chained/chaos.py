"""Failure-injection hooks for chained MVP chaos run (Phase 19 §4.6)."""

from __future__ import annotations

import os


def enable_chaos_for_stage(stage: str) -> None:
    os.environ["OLYMPUS_FAULTS"] = "1"
    if stage == "dc003_forge":
        os.environ["MVP_CHAOS_FORGE_KILL"] = "1"
    if stage == "dc003_issue_close":
        os.environ["MVP_CHAOS_ISSUE_CLOSE_FAULT"] = "timeout_after_forward"
    if stage == "dc004_sentinel":
        os.environ["MVP_CHAOS_SENTINEL_LEASE"] = "1"
    if stage == "walkthrough_sse":
        os.environ["MVP_CHAOS_SSE_RESTART"] = "1"


def chaos_issue_close_fault_mode() -> str | None:
    if os.environ.get("MVP_CHAOS") != "1":
        return None
    return os.environ.get("MVP_CHAOS_ISSUE_CLOSE_FAULT")
