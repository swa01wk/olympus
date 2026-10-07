from __future__ import annotations

from core.commands.catalog import export_command_catalog
from fastapi import APIRouter

router = APIRouter(prefix="/commands", tags=["commands"])


@router.get("/catalog")
async def command_catalog() -> dict[str, object]:
    return export_command_catalog()
