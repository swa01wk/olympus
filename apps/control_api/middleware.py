from __future__ import annotations

from collections.abc import Awaitable, Callable

from core.observability.correlation import (
    CORRELATION_HEADER,
    bind_correlation_id,
    is_valid_correlation_id,
)
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response


class CorrelationIdMiddleware(BaseHTTPMiddleware):
    async def dispatch(
        self,
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        incoming = request.headers.get(CORRELATION_HEADER)
        if incoming and not is_valid_correlation_id(incoming):
            incoming = None
        correlation_id = bind_correlation_id(incoming)
        response = await call_next(request)
        response.headers[CORRELATION_HEADER] = correlation_id
        return response
