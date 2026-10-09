from __future__ import annotations

import uuid

from agents.atlas.schemas import ArchitectureDeltaProposal
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.commands.context import CommandContext
from core.domain.canonical_json import sha256_hex
from core.domain.enums import ApprovalType, SpecStatus
from core.domain.events.append import append_domain_event
from core.domain.exceptions import DomainError
from core.planning.architecture.validation import validate_architecture_proposal
from core.planning.models import Architecture, ArchitectureContract
from core.planning.schemas import ArchitectureBody, ArchitectureProposal, ContractDraft
from core.review.auto_request import cancel_pending_approvals, ensure_pending_approval


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

    async def persist_delta(
        self,
        session: AsyncSession,
        *,
        project_id: uuid.UUID,
        delivery_cycle_id: uuid.UUID,
        proposal: ArchitectureDeltaProposal,
        execution_id: uuid.UUID | None,
        ctx: CommandContext,
    ) -> Architecture:
        latest = await session.execute(
            select(Architecture)
            .where(Architecture.project_id == project_id, Architecture.lineage_key == "ARCH")
            .order_by(Architecture.version.desc())
            .limit(1)
        )
        latest_row = latest.scalar_one_or_none()
        if latest_row:
            version = latest_row.version + 1
            supersedes_id = latest_row.id if latest_row.status == SpecStatus.PROPOSED else None
            if latest_row.status == SpecStatus.PROPOSED:
                latest_row.status = SpecStatus.SUPERSEDED
        else:
            version = 1
            supersedes_id = None

        body_dict = proposal.model_dump(mode="json")
        row = Architecture(
            project_id=project_id,
            lineage_key="ARCH",
            version=version,
            status=SpecStatus.PROPOSED,
            kind="DELTA",
            body=body_dict,
            content_hash=sha256_hex(body_dict),
            supersedes_id=supersedes_id,
            execution_id=execution_id,
        )
        session.add(row)
        await session.flush()
        for contract in proposal.changed_contracts:
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
            event_type="architecture_delta.proposed",
            payload={"version": version, "execution_id": str(execution_id or "")},
            actor_id=ctx.actor.id,
            correlation_id=ctx.correlation_id,
            project_id=project_id,
            delivery_cycle_id=delivery_cycle_id,
        )
        await ensure_pending_approval(
            session,
            project_id=project_id,
            approval_type=ApprovalType.ARCHITECTURE_DELTA,
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
                # A delta body is an ArchitectureDeltaProposal, not an ArchitectureBody.
                Architecture.kind != "DELTA",
            )
            .order_by(Architecture.version.desc())
            .limit(1)
        )
        return result.scalar_one_or_none()

    async def effective(
        self, session: AsyncSession, project_id: uuid.UUID
    ) -> tuple[Architecture, ArchitectureBody, list[ArchitectureContract]] | None:
        """Latest approved full architecture with later approved deltas applied in order."""
        base = await self.get_approved(session, project_id)
        if base is None:
            return None
        body = self.parse_body(base)
        contracts = {c.key: c for c in await self.get_contracts(session, base.id)}
        deltas = (
            await session.execute(
                select(Architecture)
                .where(
                    Architecture.project_id == project_id,
                    Architecture.status == SpecStatus.APPROVED,
                    Architecture.kind == "DELTA",
                    Architecture.version > base.version,
                )
                .order_by(Architecture.version)
            )
        ).scalars()
        for delta in deltas:
            proposal = ArchitectureDeltaProposal.model_validate(delta.body)
            components = {c.name: c for c in body.components}
            for comp in proposal.changed_components + proposal.added_components:
                components[comp.name] = comp
            decisions = {d.id: d for d in body.decisions}
            for dec in proposal.decisions:
                decisions[dec.id] = dec
            body = body.model_copy(
                update={
                    "components": list(components.values()),
                    "decisions": list(decisions.values()),
                }
            )
            for contract in await self.get_contracts(session, delta.id):
                contracts[contract.key] = contract
        return base, body, list(contracts.values())

    async def get_latest(self, session: AsyncSession, project_id: uuid.UUID) -> Architecture | None:
        result = await session.execute(
            select(Architecture)
            .where(Architecture.project_id == project_id)
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

    async def create_edited_version(
        self,
        session: AsyncSession,
        *,
        architecture_id: uuid.UUID,
        body: ArchitectureBody,
        contracts: list[ContractDraft] | None,
        note: str | None,
        delivery_cycle_id: uuid.UUID,
        ctx: CommandContext,
    ) -> Architecture:
        from core.domain.delivery_cycles.models import DeliveryCycle
        from core.domain.enums import ActorKind
        from core.domain.exceptions import Unauthorized

        if ctx.actor.kind != ActorKind.HUMAN:
            raise Unauthorized("Only a human may edit an architecture")
        current = await session.get(Architecture, architecture_id)
        if current is None:
            raise DomainError(code="NOT_FOUND", message="Architecture not found")
        if current.status != SpecStatus.PROPOSED:
            raise DomainError(
                code="INVALID_STATE", message="Only PROPOSED architecture is editable"
            )
        if current.kind == "DELTA":
            raise DomainError(
                code="INVALID_STATE", message="Architecture deltas are not directly editable"
            )
        cycle = await session.get(DeliveryCycle, delivery_cycle_id)
        if cycle is None or cycle.project_id != current.project_id:
            raise DomainError(code="NOT_FOUND", message="Delivery cycle not found for project")
        if cycle.state != "ARCHITECTURE":
            raise DomainError(
                code="INVALID_STATE", message="Cycle stage does not allow architecture edit"
            )
        if contracts is None:
            contracts = [
                ContractDraft(
                    key=c.key,
                    kind=c.kind,  # type: ignore[arg-type]
                    name=c.name,
                    method=(c.definition or {}).get("method") or "",
                    path=(c.definition or {}).get("path") or "",
                    description=(c.definition or {}).get("description") or "",
                )
                for c in (
                    await session.execute(
                        select(ArchitectureContract).where(
                            ArchitectureContract.architecture_id == current.id
                        )
                    )
                ).scalars()
            ]
        proposal = ArchitectureProposal(body=body, contracts=contracts)
        errors = validate_architecture_proposal(proposal)
        if errors:
            raise DomainError(
                code="VALIDATION_FAILED",
                message="Architecture body invalid",
                details={"errors": errors},
            )
        current.status = SpecStatus.SUPERSEDED
        await cancel_pending_approvals(
            session,
            approval_type=ApprovalType.ARCHITECTURE,
            subject_type="architecture",
            subject_id=current.id,
            correlation_id=ctx.correlation_id,
        )
        body_dict = body.model_dump(mode="json")
        row = Architecture(
            project_id=current.project_id,
            lineage_key=current.lineage_key,
            version=current.version + 1,
            status=SpecStatus.PROPOSED,
            kind=current.kind,
            body=body_dict,
            content_hash=sha256_hex(body_dict),
            supersedes_id=current.id,
            execution_id=None,
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
            event_type="architecture.edited",
            payload={"note": note or "", "previous_version": current.version},
            actor_id=ctx.actor.id,
            correlation_id=ctx.correlation_id,
            project_id=row.project_id,
            delivery_cycle_id=delivery_cycle_id,
        )
        await ensure_pending_approval(
            session,
            project_id=row.project_id,
            approval_type=ApprovalType.ARCHITECTURE,
            subject_type="architecture",
            subject_id=row.id,
            subject_version=row.version,
            subject_hash=row.content_hash,
            delivery_cycle_id=delivery_cycle_id,
            ctx=ctx,
        )
        if note and note.strip():
            from core.domain.enums import KnowledgeClass, KnowledgeItemStatus
            from core.product_model.models import KnowledgeItem

            session.add(
                KnowledgeItem(
                    project_id=row.project_id,
                    delivery_cycle_id=delivery_cycle_id,
                    knowledge_class=KnowledgeClass.DECISION,
                    statement=f"ARCHITECTURE {row.lineage_key} v{row.version}: {note.strip()}",
                    subject_refs=[{"ref_type": "ARCHITECTURE", "ref_id": str(row.id)}],
                    provenance={"origin": "HUMAN", "actor_id": str(ctx.actor.id)},
                    status=KnowledgeItemStatus.ACTIVE,
                    blocking=False,
                )
            )
            await session.flush()
        return row
