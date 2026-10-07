#!/usr/bin/env python3
"""MVP demo preflight checks (Phase 19 §4.1)."""

from __future__ import annotations

import asyncio
import os
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[2]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

import httpx


def _fail(name: str, detail: str) -> None:
    print(f"PREFLIGHT FAIL: {name} — {detail}", file=sys.stderr)


async def _check_live_diagnostic() -> bool:
    import uuid

    from core.config.settings import clear_settings_cache, get_settings
    from core.db.engine import create_async_engine_from_settings
    from core.runtime.contracts import ContextItem, ModelRequest
    from core.runtime.model_router import ModelRouter, build_providers
    from core.runtime.profiles.diagnostic import DiagnosticSummary
    from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
    from tests.fixtures.planning_workflow_harness import ensure_system_actor
    from tests.live_credentials import any_live_provider_configured

    clear_settings_cache()
    settings = get_settings()
    if settings.olympus_env not in {"journey", "integration"}:
        _fail("OLYMPUS_ENV", f"expected journey, got {settings.olympus_env}")
        return False
    if not any_live_provider_configured():
        _fail("LLM credentials", "No OPENAI_API_KEY or ANTHROPIC_API_KEY configured")
        return False

    text = Path("tests/fixtures/diagnostic/paragraph.txt").read_text(encoding="utf-8")
    engine = create_async_engine_from_settings(settings)
    factory = async_sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False)
    try:
        async with factory() as session:
            actor = await ensure_system_actor(session)
            await session.commit()
            router = ModelRouter(
                session,
                actor_id=actor.id,
                providers=build_providers(),
            )
            result = await router.invoke(
                ModelRequest(
                    purpose="mvp.preflight",
                    alias="verification_planning",
                    system_instructions="Summarize the text into the required JSON schema.",
                    context=[ContextItem(kind="TEXT", content=text, provenance="DETERMINISTIC")],
                    output_schema=DiagnosticSummary,
                    metadata={
                        "agent_profile": "diagnostic.structured_echo",
                        "correlation_id": str(uuid.uuid4()),
                    },
                )
            )
    except Exception as exc:  # noqa: BLE001
        _fail("ModelRouter.invoke", str(exc))
        return False
    finally:
        await engine.dispose()
    return result is not None and isinstance(result.parsed_output, DiagnosticSummary)


def main() -> int:
    failures: list[str] = []

    if os.environ.get("LLM_LIVE_TESTS") != "1":
        failures.append("LLM_LIVE_TESTS=1")
    if os.environ.get("OLYMPUS_ENV") != "journey":
        failures.append("OLYMPUS_ENV=journey")

    budget = os.environ.get("LLM_TEST_BUDGET_USD", "")
    try:
        if not budget or float(budget) < 5:
            failures.append("LLM_TEST_BUDGET_USD>=5 (Q-06 ceiling TBD)")
    except ValueError:
        failures.append("LLM_TEST_BUDGET_USD numeric")

    api = os.environ.get("OLYMPUS_API_BASE", "http://127.0.0.1:8000").rstrip("/")
    try:
        ready = httpx.get(f"{api}/ready", timeout=5.0)
        if ready.status_code != 200:
            body = ready.json() if ready.content else {}
            sandbox_only = (
                body.get("db") == "ok"
                and body.get("migrations") == "head"
                and body.get("sandbox") == "error"
            )
            if sandbox_only and sys.platform == "darwin":
                print(
                    "preflight warning: bubblewrap sandbox unavailable on macOS "
                    "(Plan 19 sign-off expects Linux); continuing local demo.",
                    file=sys.stderr,
                )
            else:
                failures.append(f"control-api /ready={ready.status_code} {body}")
    except httpx.HTTPError as exc:
        failures.append(f"control-api unreachable: {exc}")

    for url, name in (
        (os.environ.get("OLYMPUS_GITEA_URL", "http://127.0.0.1:3000"), "gitea"),
        (os.environ.get("OLYMPUS_CI_RUNNER_URL", "http://127.0.0.1:8090/health"), "ci-runner"),
        (os.environ.get("OLYMPUS_MINIO_URL", "http://127.0.0.1:9000/minio/health/live"), "minio"),
    ):
        try:
            httpx.get(url.rstrip("/") if name == "gitea" else url, timeout=5.0).raise_for_status()
        except httpx.HTTPError:
            failures.append(f"{name} unhealthy")

    for path, label in (
        ("/healthz", "scheduler-worker"),
        ("/healthz", "execution-worker"),
    ):
        worker_base = os.environ.get(f"OLYMPUS_{label.upper().replace('-', '_')}_URL")
        if not worker_base:
            continue
        try:
            httpx.get(f"{worker_base.rstrip('/')}{path}", timeout=5.0).raise_for_status()
        except httpx.HTTPError:
            failures.append(f"{label} unhealthy")

    try:
        from core.runtime.providers.fake_provider import FakeProvider

        FakeProvider()
        failures.append("FakeProvider must not construct in journey env")
    except Exception:
        pass

    if not asyncio.run(_check_live_diagnostic()):
        failures.append("live diagnostic.structured_echo")

    if failures:
        for item in failures:
            _fail("check", item)
        return 1
    print("preflight ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
