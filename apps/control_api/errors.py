from __future__ import annotations

from core.domain.exceptions import (
    DomainError,
    GuardFailed,
    IdempotencyConflict,
    IllegalTransition,
    StateConflict,
    Unauthorized,
)
from fastapi import Request
from fastapi.responses import JSONResponse


async def domain_error_handler(_request: Request, exc: DomainError) -> JSONResponse:
    status = 400
    if exc.code == "UNAUTHENTICATED":
        status = 401
    elif exc.code == "FORBIDDEN" or isinstance(exc, Unauthorized):
        status = 403
    elif isinstance(exc, StateConflict | IllegalTransition):
        status = 409
    elif isinstance(exc, GuardFailed | IdempotencyConflict):
        status = 422
    return JSONResponse(
        status_code=status,
        content={"code": exc.code, "message": exc.message, "details": exc.details},
    )
