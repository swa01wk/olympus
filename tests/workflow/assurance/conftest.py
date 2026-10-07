"""Workflow assurance tests use integration fixtures and sentinel stubs."""

from __future__ import annotations

from tests.integration.assurance.conftest import (  # noqa: F401
    _patch_sentinel_execute,
    force_sentinel_fail,
)
from tests.integration.conftest import system_actor, system_ctx  # noqa: F401
