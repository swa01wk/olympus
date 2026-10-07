from __future__ import annotations

import uuid
from datetime import datetime

from core.domain.exceptions import DomainError
from core.security.tokens import create_api_token, revoke_api_token, rotate_api_token
from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from apps.control_api.deps import get_db, require_scope

router = APIRouter(prefix="/auth/tokens", tags=["auth"])


class CreateTokenRequest(BaseModel):
    actor_id: uuid.UUID
    scopes: list[str] = Field(default_factory=lambda: ["read", "operate"])
    expires_at: datetime | None = None


class TokenCreatedResponse(BaseModel):
    token_id: str
    bearer_token: str
    scopes: list[str]


class TokenActionResponse(BaseModel):
    token_id: str
    bearer_token: str | None = None


@router.post("", response_model=TokenCreatedResponse)
async def create_token(
    body: CreateTokenRequest,
    session: AsyncSession = Depends(get_db),
    _admin: object = Depends(require_scope("admin")),
) -> TokenCreatedResponse:
    raw, row = await create_api_token(
        session,
        actor_id=body.actor_id,
        scopes=body.scopes,
        expires_at=body.expires_at,
    )
    return TokenCreatedResponse(
        token_id=str(row.id),
        bearer_token=raw,
        scopes=list(row.scopes or []),
    )


@router.post("/{token_id}/rotate", response_model=TokenActionResponse)
async def rotate_token(
    token_id: uuid.UUID,
    session: AsyncSession = Depends(get_db),
    _admin: object = Depends(require_scope("admin")),
) -> TokenActionResponse:
    try:
        raw, row = await rotate_api_token(session, token_id)
    except ValueError as exc:
        raise DomainError(code="NOT_FOUND", message=str(exc)) from exc
    return TokenActionResponse(token_id=str(row.id), bearer_token=raw)


@router.post("/{token_id}/revoke")
async def revoke_token(
    token_id: uuid.UUID,
    session: AsyncSession = Depends(get_db),
    _admin: object = Depends(require_scope("admin")),
) -> dict[str, str]:
    try:
        await revoke_api_token(session, token_id)
    except ValueError as exc:
        raise DomainError(code="NOT_FOUND", message=str(exc)) from exc
    return {"status": "revoked"}
