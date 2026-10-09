from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.commands.context import CommandContext
from core.domain.canonical_json import sha256_hex
from core.domain.enums import ApprovalType, SpecStatus
from core.domain.events.append import append_domain_event
from core.domain.exceptions import DomainError
from core.planning.architecture.service import ArchitectureService
from core.planning.implementation_specs.conformance import ArchitectureConformanceValidator
from core.planning.models import ImplementationSpec
from core.planning.schemas import ImplementationSpecBody, ImplementationSpecDraft
from core.product_model.models import Feature, FeatureSpec
from core.review.auto_request import ensure_pending_approval


class ImplementationSpecService:
    def __init__(self) -> None:
        self._arch = ArchitectureService()
        self._conformance = ArchitectureConformanceValidator()

    async def persist_repair_draft(
        self,
        session: AsyncSession,
        *,
        feature_spec_id: uuid.UUID,
        draft: ImplementationSpecDraft,
        execution_id: uuid.UUID | None,
        ctx: CommandContext,
        delivery_cycle_id: uuid.UUID | None = None,
    ) -> ImplementationSpec:
        from core.product_model.defects.repair import RepairSpecValidator

        ok, errors = RepairSpecValidator().validate_implementation_spec(draft)
        if not ok:
            raise DomainError(
                code="VALIDATION_FAILED",
                message="REPAIR ImplementationSpec invalid",
                details={"errors": errors},
            )
        row = await self.persist_draft(
            session,
            feature_spec_id=feature_spec_id,
            draft=draft,
            execution_id=execution_id,
            ctx=ctx,
            for_delta=False,
            kind_override="REPAIR",
            delivery_cycle_id=delivery_cycle_id,
        )
        return row

    async def persist_draft(
        self,
        session: AsyncSession,
        *,
        feature_spec_id: uuid.UUID,
        draft: ImplementationSpecDraft,
        execution_id: uuid.UUID | None,
        ctx: CommandContext,
        for_delta: bool = False,
        kind_override: str | None = None,
        delivery_cycle_id: uuid.UUID | None = None,
    ) -> ImplementationSpec:
        spec = await session.get(FeatureSpec, feature_spec_id)
        if spec is None:
            raise DomainError(code="NOT_FOUND", message="FeatureSpec not found")
        effective = await self._arch.effective(session, spec.project_id)
        if effective is None:
            raise DomainError(code="INVALID_STATE", message="No approved architecture")
        arch, arch_body, contracts = effective
        report = self._conformance.validate(draft.body, arch_body, contracts)
        if not report.ok:
            await append_domain_event(
                session,
                aggregate_type="implementation_spec",
                aggregate_id=feature_spec_id,
                event_type="implementation_spec.rejected_conformance",
                payload={"violations": report.violations},
                actor_id=ctx.actor.id,
                correlation_id=ctx.correlation_id,
                project_id=spec.project_id,
            )
            raise DomainError(
                code="ARCHITECTURE_DELTA_REQUIRED",
                message="ImplementationSpec failed architecture conformance",
                details={
                    "violations": report.violations,
                    "conformance_report": report.model_dump(),
                },
            )

        feature = await session.get(Feature, spec.feature_id)
        lineage = f"SPEC-IMPL-{feature.key}" if feature else f"SPEC-IMPL-{spec.lineage_key}"

        latest = await session.execute(
            select(ImplementationSpec)
            .where(
                ImplementationSpec.project_id == spec.project_id,
                ImplementationSpec.lineage_key == lineage,
            )
            .order_by(ImplementationSpec.version.desc())
            .limit(1)
        )
        latest_row = latest.scalar_one_or_none()
        if latest_row:
            version = latest_row.version + 1
            supersedes_id = None if for_delta else latest_row.id
            if not for_delta and latest_row.status == SpecStatus.PROPOSED:
                latest_row.status = SpecStatus.SUPERSEDED
        else:
            version = 1
            supersedes_id = None

        body_dict = draft.body.model_dump(mode="json")
        row = ImplementationSpec(
            project_id=spec.project_id,
            lineage_key=lineage,
            version=version,
            status=SpecStatus.PROPOSED,
            kind=kind_override or ("DELTA" if for_delta else "FEATURE"),
            feature_spec_id=feature_spec_id,
            architecture_id=arch.id,
            body=body_dict,
            content_hash=sha256_hex(body_dict),
            supersedes_id=supersedes_id,
            execution_id=execution_id,
            conformance_report=report.model_dump(mode="json"),
        )
        session.add(row)
        await session.flush()
        await append_domain_event(
            session,
            aggregate_type="implementation_spec",
            aggregate_id=row.id,
            event_type="implementation_spec.proposed",
            payload={"feature_spec_id": str(feature_spec_id), "version": version},
            actor_id=ctx.actor.id,
            correlation_id=ctx.correlation_id,
            project_id=spec.project_id,
        )
        if delivery_cycle_id is not None and not for_delta:
            await ensure_pending_approval(
                session,
                project_id=spec.project_id,
                approval_type=ApprovalType.IMPLEMENTATION_SPEC,
                subject_type="implementation_spec",
                subject_id=row.id,
                subject_version=row.version,
                subject_hash=row.content_hash,
                delivery_cycle_id=delivery_cycle_id,
                ctx=ctx,
            )
        return row

    async def request_approval(
        self,
        session: AsyncSession,
        impl_spec_id: uuid.UUID,
        delivery_cycle_id: uuid.UUID,
        ctx: CommandContext,
    ) -> uuid.UUID:
        row = await session.get(ImplementationSpec, impl_spec_id)
        if row is None:
            raise DomainError(code="NOT_FOUND", message="ImplementationSpec not found")
        if row.status != SpecStatus.PROPOSED:
            raise DomainError(code="INVALID_STATE", message="ImplementationSpec must be PROPOSED")
        approval = await ensure_pending_approval(
            session,
            project_id=row.project_id,
            approval_type=ApprovalType.IMPLEMENTATION_SPEC,
            subject_type="implementation_spec",
            subject_id=row.id,
            subject_version=row.version,
            subject_hash=row.content_hash,
            delivery_cycle_id=delivery_cycle_id,
            ctx=ctx,
        )
        return approval.id

    async def on_approved(
        self,
        session: AsyncSession,
        impl_spec_id: uuid.UUID,
        approval_id: uuid.UUID,
        ctx: CommandContext,
    ) -> None:
        row = await session.get(ImplementationSpec, impl_spec_id)
        if row is None or row.status == SpecStatus.APPROVED:
            return
        row.status = SpecStatus.APPROVED
        row.approval_id = approval_id
        await append_domain_event(
            session,
            aggregate_type="implementation_spec",
            aggregate_id=row.id,
            event_type="implementation_spec.approved",
            payload={"version": row.version},
            actor_id=ctx.actor.id,
            correlation_id=ctx.correlation_id,
            project_id=row.project_id,
        )

    async def list_approved_for_scope(
        self,
        session: AsyncSession,
        project_id: uuid.UUID,
        feature_spec_ids: list[uuid.UUID],
    ) -> list[ImplementationSpec]:
        out: list[ImplementationSpec] = []
        for fs_id in feature_spec_ids:
            result = await session.execute(
                select(ImplementationSpec)
                .where(
                    ImplementationSpec.feature_spec_id == fs_id,
                    ImplementationSpec.status == SpecStatus.APPROVED,
                )
                .order_by(ImplementationSpec.version.desc())
                .limit(1)
            )
            row = result.scalar_one_or_none()
            if row is None:
                continue
            out.append(row)
        return out

    def parse_body(self, row: ImplementationSpec) -> ImplementationSpecBody:
        return ImplementationSpecBody.model_validate(row.body)

    async def create_edited_version(
        self,
        session: AsyncSession,
        *,
        spec_id: uuid.UUID,
        body: ImplementationSpecBody,
        note: str | None,
        delivery_cycle_id: uuid.UUID,
        ctx: CommandContext,
    ) -> ImplementationSpec:
        from core.domain.delivery_cycles.models import DeliveryCycle
        from core.domain.enums import ActorKind, KnowledgeClass, KnowledgeItemStatus
        from core.domain.exceptions import Unauthorized
        from core.planning.schemas import ImplementationSpecDraft
        from core.product_model.models import KnowledgeItem
        from core.review.auto_request import cancel_pending_approvals

        if ctx.actor.kind != ActorKind.HUMAN:
            raise Unauthorized("Only a human may edit an implementation spec")
        current = await session.get(ImplementationSpec, spec_id)
        if current is None:
            raise DomainError(code="NOT_FOUND", message="ImplementationSpec not found")
        if current.status != SpecStatus.PROPOSED:
            raise DomainError(
                code="INVALID_STATE", message="Only PROPOSED implementation spec is editable"
            )
        cycle = await session.get(DeliveryCycle, delivery_cycle_id)
        if cycle is None or cycle.project_id != current.project_id:
            raise DomainError(code="NOT_FOUND", message="Delivery cycle not found for project")
        owning_stage = "ROOT_CAUSE" if current.kind == "REPAIR" else "PLANNING"
        if cycle.state != owning_stage:
            raise DomainError(
                code="INVALID_STATE", message="Cycle stage does not allow implementation spec edit"
            )
        draft = ImplementationSpecDraft(body=body)
        row = await self.persist_draft(
            session,
            feature_spec_id=current.feature_spec_id,
            draft=draft,
            execution_id=None,
            ctx=ctx,
            kind_override=current.kind,
            delivery_cycle_id=delivery_cycle_id,
        )
        current.status = SpecStatus.SUPERSEDED
        await cancel_pending_approvals(
            session,
            approval_type=ApprovalType.IMPLEMENTATION_SPEC,
            subject_type="implementation_spec",
            subject_id=current.id,
            correlation_id=ctx.correlation_id,
        )
        await append_domain_event(
            session,
            aggregate_type="implementation_spec",
            aggregate_id=row.id,
            event_type="implementation_spec.edited",
            payload={"note": note or "", "previous_id": str(current.id)},
            actor_id=ctx.actor.id,
            correlation_id=ctx.correlation_id,
            project_id=row.project_id,
            delivery_cycle_id=delivery_cycle_id,
        )
        if note and note.strip():
            session.add(
                KnowledgeItem(
                    project_id=row.project_id,
                    delivery_cycle_id=delivery_cycle_id,
                    knowledge_class=KnowledgeClass.DECISION,
                    statement=(
                        f"IMPLEMENTATION_SPEC {row.lineage_key} v{row.version}: {note.strip()}"
                    ),
                    subject_refs=[{"ref_type": "IMPLEMENTATION_SPEC", "ref_id": str(row.id)}],
                    provenance={"origin": "HUMAN", "actor_id": str(ctx.actor.id)},
                    status=KnowledgeItemStatus.ACTIVE,
                    blocking=False,
                )
            )
            await session.flush()
        return row
