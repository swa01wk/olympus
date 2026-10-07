from __future__ import annotations

import uuid

from core.domain.exceptions import DomainError
from core.domain.executions.models import Execution, ExecutionLease
from core.tools.tokens import TokenValidationError, validate_token
from fastapi import Depends, Header
from sqlalchemy.ext.asyncio import AsyncSession

from apps.control_api.deps import get_db


async def execution_from_bearer_token(
    authorization: str | None = Header(default=None, alias="Authorization"),
    session: AsyncSession = Depends(get_db),
) -> tuple[Execution, ExecutionLease]:
    if not authorization or not authorization.startswith("Bearer "):
        raise DomainError(code="UNAUTHENTICATED", message="Execution Bearer token required")
    token = authorization.removeprefix("Bearer ").strip()
    try:
        return await validate_token(session, token)
    except TokenValidationError as exc:
        raise DomainError(code="UNAUTHENTICATED", message=exc.reason) from exc


async def execution_scoped_token(
    execution_id: uuid.UUID,
    token_ctx: tuple[Execution, ExecutionLease] = Depends(execution_from_bearer_token),
) -> tuple[Execution, ExecutionLease]:
    execution, lease = token_ctx
    if execution.id != execution_id:
        raise DomainError(code="UNAUTHENTICATED", message="token execution mismatch")
    return execution, lease
