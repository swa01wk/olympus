"""Stage A–D entrypoints for manual demo (delegates to journey runner)."""

from __future__ import annotations

from scripts.demo.chained.driver import ChainedDriver
from tests.journey.chained.runner import ChainedRunContext, run_chained_mvp


async def run_all_stages(driver: ChainedDriver, ctx: ChainedRunContext) -> None:
    await run_chained_mvp(ctx, driver=driver)
