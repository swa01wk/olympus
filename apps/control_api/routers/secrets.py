from __future__ import annotations

from core.domain.exceptions import DomainError
from core.integrations.connectors.secrets import store_secret
from fastapi import APIRouter, Depends
from pydantic import BaseModel, ConfigDict, SecretStr
from sqlalchemy.ext.asyncio import AsyncSession

from apps.control_api.deps import get_db

router = APIRouter(tags=["secrets"])


class PutSecretRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    value: SecretStr


class PutSecretResponse(BaseModel):
    credential_ref: str


@router.put("/secrets/{name}", response_model=PutSecretResponse)
async def put_secret(
    name: str,
    body: PutSecretRequest,
    session: AsyncSession = Depends(get_db),
) -> PutSecretResponse:
    if not name or "/" in name:
        raise DomainError(code="INVALID_NAME", message="Invalid secret name")
    ref = await store_secret(session, name, body.value.get_secret_value())
    await session.commit()
    return PutSecretResponse(credential_ref=ref)
