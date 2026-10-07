#!/usr/bin/env python3
"""Manual chained MVP demo entrypoint (Phase 19 §4.2)."""

from __future__ import annotations

import argparse
import asyncio
import os
import sys
from pathlib import Path

import httpx

_REPO_ROOT = Path(__file__).resolve().parents[2]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from scripts.demo.chained.driver import ChainedDriver, ChainedDriverConfig
from scripts.demo.chained.stages import run_all_stages
from tests.journey.chained.runner import ChainedRunContext


async def _run(args: argparse.Namespace) -> int:
    token = args.human_token or os.environ.get("OLYMPUS_HUMAN_TOKEN")
    if not token:
        print("Set OLYMPUS_HUMAN_TOKEN", file=sys.stderr)
        return 1

    from core.config.settings import get_settings
    from core.db.engine import create_async_engine_from_settings

    settings = get_settings()
    engine = create_async_engine_from_settings(settings)
    config = ChainedDriverConfig(
        api_base=args.api_base,
        human_token=token,
        viewer_token=os.environ.get("OLYMPUS_VIEWER_TOKEN"),
        pause_before=args.pause_before,
        chaos=args.chaos,
        report_dir=Path(args.report) if args.report else None,
        dashboard_base=args.dashboard_base,
    )
    driver = ChainedDriver(config)
    ctx = ChainedRunContext(
        async_engine=engine,
        client=driver._client,
        operator_token=token,
        human_token=token,
        chaos=args.chaos,
    )
    try:
        await run_all_stages(driver, ctx)
    finally:
        await driver.aclose()
    if config.report_dir:
        driver.report.project_id = ctx.project_id and str(ctx.project_id)
        driver.report.releases = ctx.releases
        driver.report.cycles = ctx.cycles
        driver.report.write(config.report_dir)
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Run chained SUPPORTDESK MVP demo")
    parser.add_argument(
        "--api-base", default=os.environ.get("OLYMPUS_API_BASE", "http://127.0.0.1:8000")
    )
    parser.add_argument("--human-token", default=None)
    parser.add_argument("--chaos", action="store_true")
    parser.add_argument("--pause-before", default=None)
    parser.add_argument(
        "--dashboard-base",
        default=os.environ.get("OLYMPUS_DASHBOARD_BASE", "http://127.0.0.1:3010"),
    )
    parser.add_argument("--report", type=str, default="var/olympus/reports")
    parser.add_argument("--strategy", choices=["A", "B"], default="A")
    args = parser.parse_args()
    _ = args.strategy
    api = args.api_base.rstrip("/")
    try:
        ready = httpx.get(f"{api}/ready", timeout=5.0)
        if ready.status_code != 200:
            body = ready.json() if ready.content else {}
            sandbox_only = (
                body.get("db") == "ok"
                and body.get("migrations") == "head"
                and body.get("sandbox") == "error"
            )
            if not (sandbox_only and sys.platform == "darwin"):
                print(
                    f"Control API not ready at {api} (GET /ready → {ready.status_code}).",
                    file=sys.stderr,
                )
                if body:
                    print(body, file=sys.stderr)
                print("Start the MVP stack first: make mvp-env", file=sys.stderr)
                return 1
            print(
                "warning: /ready sandbox check failed on macOS; "
                "continuing (use Linux for sign-off).",
                file=sys.stderr,
            )
        httpx.get(f"{api}/health", timeout=5.0).raise_for_status()
    except httpx.HTTPError as exc:
        print(f"Control API unreachable at {api}: {exc}", file=sys.stderr)
        print("Start the MVP stack first: make mvp-env", file=sys.stderr)
        print("(Docker compose + migrate + seed actors + preflight)", file=sys.stderr)
        return 1
    return asyncio.run(_run(args))


if __name__ == "__main__":
    raise SystemExit(main())
