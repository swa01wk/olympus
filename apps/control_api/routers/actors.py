from __future__ import annotations

from core.domain.actors.models import Actor
from fastapi import APIRouter, Depends
from pydantic import BaseModel

from apps.control_api.deps import get_actor

router = APIRouter(prefix="/actors", tags=["actors"])


class ActorMeResponse(BaseModel):
    actor_id: str
    kind: str
    name: str
    roles: list[str]


@router.get("/me", response_model=ActorMeResponse)
async def me(actor: Actor = Depends(get_actor)) -> ActorMeResponse:
    return ActorMeResponse(
        actor_id=str(actor.id),
        kind=actor.kind.value,
        name=actor.name,
        roles=list(actor.roles or []),
    )
