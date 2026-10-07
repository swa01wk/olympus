"""SandboxRunner — isolated execution for untrusted tests and probes."""

from __future__ import annotations

from core.config.settings import OlympusSettings, get_settings
from core.execution.sandbox.types import SandboxRunner


def get_sandbox_runner(settings: OlympusSettings | None = None) -> SandboxRunner:
    cfg = settings or get_settings()
    if cfg.olympus_env in {"local", "test"}:
        from core.execution.sandbox.local import LocalSandboxRunner

        return LocalSandboxRunner()
    from core.execution.sandbox.bwrap import BwrapSandboxRunner

    return BwrapSandboxRunner()


def sandbox_available(settings: OlympusSettings | None = None) -> bool:
    cfg = settings or get_settings()
    if cfg.olympus_env in {"local", "test"}:
        return True
    from core.execution.sandbox.bwrap import bubblewrap_available

    return bubblewrap_available()
