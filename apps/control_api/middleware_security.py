from __future__ import annotations

from collections.abc import Awaitable, Callable

from core.config.settings import get_settings
from core.security.rate_limit import check_rate_limit
from fastapi import Request
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse, Response


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(
        self,
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        response = await call_next(request)
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("X-Frame-Options", "DENY")
        response.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
        settings = get_settings()
        if settings.olympus_env != "production":
            response.headers.setdefault(
                "Content-Security-Policy",
                "default-src 'self'; frame-ancestors 'none'",
            )
        return response


class RateLimitMiddleware(BaseHTTPMiddleware):
    async def dispatch(
        self,
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        if request.url.path in {"/health", "/ready", "/metrics"}:
            return await call_next(request)
        auth = request.headers.get("Authorization", "")
        if auth:
            key = f"token:{auth[-16:]}"
        else:
            host = request.client.host if request.client else "unknown"
            key = f"ip:{host}"
        factory: async_sessionmaker[AsyncSession] | None = getattr(
            request.app.state, "session_factory", None
        )
        if factory is None:
            return await call_next(request)
        async with factory() as session, session.begin():
            allowed, count = await check_rate_limit(session, key=key, limit=600)
        if not allowed:
            return JSONResponse(
                status_code=429,
                content={"error": "rate limit exceeded", "count": count},
            )
        return await call_next(request)
