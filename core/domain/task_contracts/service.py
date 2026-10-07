"""Versioned TaskContract drafts, canonical hashing, issue, and supersede."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from core.commands.context import CommandContext
from core.domain.canonical_json import sha256_hex
from core.domain.enums import TaskContractStatus
from core.domain.events.append import append_domain_event
from core.domain.exceptions import DomainError
from core.domain.task_contracts.models import TaskContract
from core.domain.task_contracts.schemas import TaskContractBody
from core.state.transition_service import TransitionService
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession


class ContractService:
    def __init__(self, transitions: TransitionService | None = None) -> None:
        self.transitions = transitions or TransitionService()

    async def create_draft(
        self,
        session: AsyncSession,
        task_id: uuid.UUID,
        body: TaskContractBody,
        compiled_by: str,
        ctx: CommandContext,
        inputs_hash: str | None = None,
    ) -> TaskContract:
        result = await session.execute(
            select(TaskContract.version)
            .where(TaskContract.task_id == task_id)
            .order_by(TaskContract.version.desc())
            .limit(1)
        )
        latest = result.scalar_one_or_none() or 0
        contract = TaskContract(
            task_id=task_id,
            key=f"v{latest + 1}",
            version=latest + 1,
            status=TaskContractStatus.DRAFT,
            body=body.model_dump(mode="json"),
            compiled_by=compiled_by,
            compiler_inputs_hash=inputs_hash,
        )
        session.add(contract)
        await session.flush()
        return contract

    async def update_draft(
        self,
        session: AsyncSession,
        contract_id: uuid.UUID,
        body: TaskContractBody,
    ) -> TaskContract:
        contract = await session.get(TaskContract, contract_id)
        if contract is None:
            raise DomainError(code="NOT_FOUND", message="Contract not found")
        if contract.status != TaskContractStatus.DRAFT:
            raise DomainError(
                code="CONTRACT_NOT_DRAFT", message="Only DRAFT contracts are editable"
            )
        TaskContractBody.model_validate(body)
        contract.body = body.model_dump(mode="json")
        await session.flush()
        return contract

    async def issue(
        self,
        session: AsyncSession,
        contract_id: uuid.UUID,
        ctx: CommandContext,
    ) -> TaskContract:
        contract = await session.get(TaskContract, contract_id)
        if contract is None:
            raise DomainError(code="NOT_FOUND", message="Contract not found")
        from core.domain.enums import SpecStatus, TaskOrigin, WorkType
        from core.domain.tasks.models import Task
        from core.planning.models import ImplementationSpec

        task = await session.get(Task, contract.task_id)
        compiled_by = contract.compiled_by or ""
        integration_owned = compiled_by.startswith("integration.") or compiled_by.startswith(
            "compiler:integration."
        )
        if (
            task
            and not integration_owned
            and task.work_type == WorkType.CODE_CHANGE
            and task.origin
            in {
                TaskOrigin.IMPLEMENTATION_PLAN,
                TaskOrigin.REMEDIATION,
                TaskOrigin.REPAIR,
            }
        ):
            if not compiled_by.startswith("compiler:"):
                raise DomainError(
                    code="CONTRACT_COMPILE_REQUIRED",
                    message="CODE_CHANGE contracts for planned work must be compiler-issued",
                )
            if task.implementation_spec_id is None:
                raise DomainError(
                    code="IMPLEMENTATION_SPEC_REQUIRED",
                    message="Task missing implementation_spec_id",
                )
            impl = await session.get(ImplementationSpec, task.implementation_spec_id)
            if impl is None or impl.status != SpecStatus.APPROVED:
                raise DomainError(
                    code="IMPLEMENTATION_SPEC_NOT_APPROVED",
                    message="Task requires APPROVED ImplementationSpec",
                )

        body = TaskContractBody.model_validate(contract.body)
        content_hash = sha256_hex(body.model_dump(mode="json"))
        issued = await session.execute(
            select(TaskContract).where(
                TaskContract.task_id == contract.task_id,
                TaskContract.status == TaskContractStatus.ISSUED,
            )
        )
        previous = issued.scalar_one_or_none()
        if previous is not None:
            await self.transitions.transition(
                session,
                "task_contract",
                previous.id,
                TaskContractStatus.ISSUED.value,
                "supersede",
                ctx,
            )
            await append_domain_event(
                session,
                aggregate_type="task_contract",
                aggregate_id=previous.id,
                event_type="task_contract.superseded",
                payload={"version": previous.version},
                actor_id=ctx.actor.id,
                correlation_id=ctx.correlation_id,
            )
        contract.content_hash = content_hash
        contract.issued_at = datetime.now(UTC)
        await self.transitions.transition(
            session,
            "task_contract",
            contract_id,
            TaskContractStatus.DRAFT.value,
            "issue_contract",
            ctx,
        )
        from core.domain.tasks.models import Task

        task = await session.get(Task, contract.task_id)
        if task:
            task.current_contract_id = contract.id
        await append_domain_event(
            session,
            aggregate_type="task_contract",
            aggregate_id=contract.id,
            event_type="task_contract.issued",
            payload={"version": contract.version, "content_hash": content_hash},
            actor_id=ctx.actor.id,
            correlation_id=ctx.correlation_id,
        )
        return contract
