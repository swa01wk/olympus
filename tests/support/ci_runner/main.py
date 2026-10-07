"""Minimal CI runner: accept trigger, post signed callback to Olympus inbound (Phase 16 §12)."""

from __future__ import annotations

import hashlib
import hmac
import json
import os
from datetime import UTC, datetime

import httpx
from fastapi import FastAPI
from pydantic import BaseModel, Field

app = FastAPI(title="Olympus test CI runner")

_RUNS: dict[str, dict[str, object]] = {}


class TriggerRequest(BaseModel):
    sha: str
    correlation_id: str
    callback_url: str
    secret: str = Field(default="ci-test-secret")
    run_id: str | None = None
    suite: str = "default"


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/v1/trigger")
async def trigger(body: TriggerRequest) -> dict[str, object]:
    run_id = body.run_id or f"run-{body.sha[:8]}"
    payload = {
        "run_id": run_id,
        "sha": body.sha,
        "status": "PASSED",
        "suite": body.suite,
        "correlation_id": body.correlation_id,
        "project_id": os.environ.get("CI_RUNNER_PROJECT_ID"),
    }
    raw = json.dumps(payload, separators=(",", ":")).encode()
    sig = hmac.new(body.secret.encode(), raw, hashlib.sha256).hexdigest()
    headers = {
        "Content-Type": "application/json",
        "X-Gitea-Signature": f"sha256={sig}",
    }
    async with httpx.AsyncClient(timeout=15.0) as client:
        resp = await client.post(body.callback_url, content=raw, headers=headers)
    _RUNS[run_id] = {
        "run_id": run_id,
        "sha": body.sha,
        "status": "PASSED",
        "correlation_id": body.correlation_id,
    }
    return {
        "run_id": run_id,
        "callback_status": resp.status_code,
        "finished_at": datetime.now(UTC).isoformat(),
    }


@app.get("/v1/runs/{run_id}")
async def get_run(run_id: str) -> dict[str, object]:
    row = _RUNS.get(run_id)
    if row is None:
        from fastapi import HTTPException

        raise HTTPException(status_code=404, detail="run not found")
    return row
