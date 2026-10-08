from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.commands.context import CommandContext
from core.domain.canonical_json import sha256_hex
from core.domain.enums import ApprovalType, SpecStatus
from core.domain.events.append import append_domain_event
from core.domain.exceptions import DomainError
from core.planning.architecture.validation import validate_architecture_proposal
from core.planning.models import Architecture, ArchitectureContract
from core.planning.schemas import ArchitectureBody, ArchitectureProposal
from core.review.auto_request import ensure_pending_approval


class ArchitectureService:
    async def persist_proposal(
        self,
        session: AsyncSession,
        *,
        project_id: uuid.UUID,
        proposal: ArchitectureProposal,
        execution_id: uuid.UUID | None,
        ctx: CommandContext,
        delivery_cycle_id: uuid.UUID | None = None,
    ) -> Architecture:
        errors = validate_architecture_proposal(proposal)
        if errors:
            raise DomainError(
                code="VALIDATION_FAILED",
                message="Architecture proposal invalid",
                details={"errors": errors},
            )

        latest = await session.execute(
            select(Architecture)
            .where(Architecture.project_id == project_id, Architecture.lineage_key == "ARCH")
            .order_by(Architecture.version.desc())
            .limit(1)
        )
        latest_row = latest.scalar_one_or_none()
        if latest_row and latest_row.status == SpecStatus.APPROVED or latest_row:
            version = latest_row.version + 1
            supersedes_id = latest_row.id
            latest_row.status = SpecStatus.SUPERSEDED
        else:
            version = 1
            supersedes_id = None

        body_dict = proposal.body.model_dump(mode="json")
        row = Architecture(
            project_id=project_id,
            lineage_key="ARCH",
            version=version,
            status=SpecStatus.PROPOSED,
            kind="BASELINE",
            body=body_dict,
            content_hash=sha256_hex(body_dict),
            supersedes_id=supersedes_id,
            execution_id=execution_id,
        )
        session.add(row)
        await session.flush()
        for contract in proposal.contracts:
            definition = {
                "method": contract.method,
                "path": contract.path,
                "description": contract.description,
            }
            session.add(
                ArchitectureContract(
                    architecture_id=row.id,
                    key=contract.key,
                    kind=contract.kind,
                    name=contract.name,
                    definition=definition,
                )
            )
        await append_domain_event(
            session,
            aggregate_type="architecture",
            aggregate_id=row.id,
            event_type="architecture.proposed",
            payload={"version": version},
            actor_id=ctx.actor.id,
            correlation_id=ctx.correlation_id,
            project_id=project_id,
        )
        if delivery_cycle_id is not None:
            await ensure_pending_approval(
                session,
                project_id=project_id,
                approval_type=ApprovalType.ARCHITECTURE,
                subject_type="architecture",
                subject_id=row.id,
                subject_version=row.version,
                subject_hash=row.content_hash,
                delivery_cycle_id=delivery_cycle_id,
                ctx=ctx,
            )
        return row

    async def get_approved(
        self, session: AsyncSession, project_id: uuid.UUID
    ) -> Architecture | None:
        result = await session.execute(
            select(Architecture)
            .where(
                Architecture.project_id == project_id,
                Architecture.status == SpecStatus.APPROVED,
            )
            .order_by(Architecture.version.desc())
            .limit(1)
        )
        return result.scalar_one_or_none()

    async def get_contracts(
        self, session: AsyncSession, architecture_id: uuid.UUID
    ) -> list[ArchitectureContract]:
        rows = await session.execute(
            select(ArchitectureContract).where(
                ArchitectureContract.architecture_id == architecture_id
            )
        )
        return list(rows.scalars())

    async def request_approval(
        self,
        session: AsyncSession,
        architecture_id: uuid.UUID,
        delivery_cycle_id: uuid.UUID,
        ctx: CommandContext,
    ) -> uuid.UUID:
        arch = await session.get(Architecture, architecture_id)
        if arch is None:
            raise DomainError(code="NOT_FOUND", message="Architecture not found")
        if arch.status != SpecStatus.PROPOSED:
            raise DomainError(code="INVALID_STATE", message="Architecture must be PROPOSED")
        approval = await ensure_pending_approval(
            session,
            project_id=arch.project_id,
            approval_type=ApprovalType.ARCHITECTURE,
            subject_type="architecture",
            subject_id=arch.id,
            subject_version=arch.version,
            subject_hash=arch.content_hash,
            delivery_cycle_id=delivery_cycle_id,
            ctx=ctx,
        )
        return approval.id

    async def on_approved(
        self,
        session: AsyncSession,
        architecture_id: uuid.UUID,
        approval_id: uuid.UUID,
        ctx: CommandContext,
    ) -> None:
        arch = await session.get(Architecture, architecture_id)
        if arch is None or arch.status == SpecStatus.APPROVED:
            return
        arch.status = SpecStatus.APPROVED
        arch.approval_id = approval_id
        await append_domain_event(
            session,
            aggregate_type="architecture",
            aggregate_id=arch.id,
            event_type="architecture.approved",
            payload={"version": arch.version},
            actor_id=ctx.actor.id,
            correlation_id=ctx.correlation_id,
            project_id=arch.project_id,
        )

    def parse_body(self, arch: Architecture) -> ArchitectureBody:
        return ArchitectureBody.model_validate(arch.body)
