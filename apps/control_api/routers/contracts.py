from __future__ import annotations

import uuid
from typing import Any

from core.commands.bus import CommandBus
from core.commands.context import CommandContext
from core.domain.task_contracts.models import TaskContract
from core.domain.task_contracts.schemas import TaskContractBody
from fastapi import APIRouter, Depends
from pydantic import BaseModel, ConfigDict
from sqlalchemy.ext.asyncio import AsyncSession

from apps.control_api.command_dispatch import dispatch
from apps.control_api.deps import command_context, get_command_bus, get_db

router = APIRouter(tags=["contracts"])


class ContractResponse(BaseModel):
    id: uuid.UUID
    task_id: uuid.UUID
    key: str
    version: int
    status: str
    body: dict[str, Any]
    content_hash: str | None


class CreateContractRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    body: TaskContractBody
    compiled_by: str = "manual"


def _contract_response(contract: TaskContract) -> ContractResponse:
    return ContractResponse(
        id=contract.id,
        task_id=contract.task_id,
        key=contract.key,
        version=contract.version,
        status=contract.status.value,
        body=contract.body,
        content_hash=contract.content_hash,
    )


async def _load_contract(session: AsyncSession, contract_id: str) -> ContractResponse:
    contract = await session.get(TaskContract, uuid.UUID(contract_id))
    assert contract is not None
    return _contract_response(contract)


@router.post("/tasks/{task_id}/contracts", response_model=ContractResponse, status_code=201)
async def create_contract(
    task_id: uuid.UUID,
    body: CreateContractRequest,
    session: AsyncSession = Depends(get_db),
    ctx: CommandContext = Depends(command_context),
    bus: CommandBus = Depends(get_command_bus),
) -> ContractResponse:
    payload = {
        "task_id": str(task_id),
        "body": body.body.model_dump(mode="json"),
        "compiled_by": body.compiled_by,
    }
    result = await dispatch(
        session,
        bus,
        name="contract.create_draft",
        target_type="task",
        target_id=str(task_id),
        payload=payload,
        ctx=ctx,
    )
    return await _load_contract(session, result.data["contract_id"])


@router.put("/task-contracts/{contract_id}", response_model=ContractResponse)
async def update_contract(
    contract_id: uuid.UUID,
    body: TaskContractBody,
    session: AsyncSession = Depends(get_db),
    ctx: CommandContext = Depends(command_context),
    bus: CommandBus = Depends(get_command_bus),
) -> ContractResponse:
    payload = {
        "contract_id": str(contract_id),
        "body": body.model_dump(mode="json"),
    }
    result = await dispatch(
        session,
        bus,
        name="contract.update_draft",
        target_type="task_contract",
        target_id=str(contract_id),
        payload=payload,
        ctx=ctx,
    )
    return await _load_contract(session, result.data["contract_id"])


@router.post("/task-contracts/{contract_id}/commands/issue", response_model=ContractResponse)
async def issue_contract(
    contract_id: uuid.UUID,
    session: AsyncSession = Depends(get_db),
    ctx: CommandContext = Depends(command_context),
    bus: CommandBus = Depends(get_command_bus),
) -> ContractResponse:
    result = await dispatch(
        session,
        bus,
        name="contract.issue",
        target_type="task_contract",
        target_id=str(contract_id),
        payload={"contract_id": str(contract_id)},
        ctx=ctx,
    )
    return await _load_contract(session, result.data["contract_id"])


@router.get("/tasks/{task_id}/contracts", response_model=list[ContractResponse])
async def list_contracts(
    task_id: uuid.UUID,
    session: AsyncSession = Depends(get_db),
) -> list[ContractResponse]:
    from sqlalchemy import select

    result = await session.execute(
        select(TaskContract).where(TaskContract.task_id == task_id).order_by(TaskContract.version)
    )
    return [_contract_response(c) for c in result.scalars()]


@router.get("/tasks/{task_id}/contract", response_model=ContractResponse | None)
async def current_contract(
    task_id: uuid.UUID,
    session: AsyncSession = Depends(get_db),
) -> ContractResponse | None:
    from core.domain.enums import TaskContractStatus
    from sqlalchemy import select

    result = await session.execute(
        select(TaskContract).where(
            TaskContract.task_id == task_id,
            TaskContract.status == TaskContractStatus.ISSUED,
        )
    )
    contract = result.scalar_one_or_none()
    if contract is None:
        return None
    return _contract_response(contract)
