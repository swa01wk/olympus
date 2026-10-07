"""Fault-injecting HTTP forward proxy for connector tests (Phase 16 §12).

Modes (header X-Olympus-Fault):
  timeout_after_forward — upstream forward then 504 to client
  reset                 — close without full response
  status_5xx            — return 502
  (absent)              — transparent forward

Run standalone:
  uvicorn tests.support.fault_proxy:app --port 9099
"""

from __future__ import annotations

import httpx
from fastapi import FastAPI, Request, Response

app = FastAPI(title="Olympus fault proxy")


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@app.api_route("/{path:path}", methods=["GET", "POST", "PUT", "PATCH", "DELETE", "HEAD"])
async def forward(path: str, request: Request) -> Response:
    fault = request.headers.get("x-olympus-fault", "").lower()
    target = request.headers.get("x-olympus-target")
    if not target:
        return Response(content=b"missing X-Olympus-Target", status_code=400)
    url = f"{target.rstrip('/')}/{path}"
    if request.url.query:
        url = f"{url}?{request.url.query}"
    headers = {
        k: v
        for k, v in request.headers.items()
        if k.lower() not in {"host", "x-olympus-fault", "x-olympus-target", "content-length"}
    }
    body = await request.body()
    if fault == "status_5xx":
        return Response(content=b"injected 502", status_code=502)
    if fault == "reset":
        return Response(content=b"", status_code=499)
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            upstream = await client.request(
                request.method,
                url,
                headers=headers,
                content=body,
            )
    except httpx.HTTPError as exc:
        return Response(content=str(exc).encode(), status_code=502)
    if fault == "timeout_after_forward":
        return Response(content=b"timeout_after_forward", status_code=504)
    return Response(
        content=upstream.content,
        status_code=upstream.status_code,
        headers=dict(upstream.headers),
    )
