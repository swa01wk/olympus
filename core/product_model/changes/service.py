"""ChangeRequest lifecycle and spec-delta materialization from interpretation."""

from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.commands.context import CommandContext
from core.domain.canonical_json import sha256_hex
from core.domain.delivery_cycles.service import DeliveryCycleService
from core.domain.enums import (
    DeliveryCycleType,
    EntityStatus,
    EvidenceRequirement,
    ModelOrigin,
    SpecStatus,
)
from core.domain.events.append import append_domain_event
from core.domain.exceptions import DomainError
from core.domain.sequences import next_project_key
from core.integrations.inbound.storage import sha256_text
from core.intelligence.code_index.retrieval.hybrid import HybridRetrieval
from core.intelligence.impact.staleness import StalenessService
from core.product_model.changes.interpretation import ChangeInterpretationValidator
from core.product_model.changes.models import ChangeRequest
from core.product_model.changes.schemas import AcChange, ChangeInterpretation
from core.product_model.models import AcceptanceCriterion, Feature, FeatureSpec, Requirement
from core.product_model.sources.service import ProductSourceService
from core.product_model.specifications.delta import SpecDeltaService
from core.product_model.specifications.service import FeatureSpecService


class ChangeRequestService:
    async def intake(
        self,
        session: AsyncSession,
        *,
        project_id: uuid.UUID,
        title: str,
        description: str,
        source_type: str,
        external_ref: str | None,
        inbound_event_id: uuid.UUID | None,
        ctx: CommandContext,
    ) -> ChangeRequest:
        if external_ref:
            existing = (
                await session.execute(
                    select(ChangeRequest).where(
                        ChangeRequest.project_id == project_id,
                        ChangeRequest.source_type == source_type,
                        ChangeRequest.external_ref == external_ref,
                    )
                )
            ).scalar_one_or_none()
            if existing is not None:
                return existing

        text_hash = sha256_text(description)
        lineage_key = f"cr-{external_ref or text_hash[:16]}"
        source_result = await ProductSourceService().ingest(
            session,
            project_id=project_id,
            lineage_key=lineage_key,
            source_type="CHANGE_REQUEST",
            title=title,
            mime_type="text/markdown",
            content_hash=text_hash,
            raw_storage_ref=f"inline://{lineage_key}",
            text=description,
            ctx=ctx,
            inbound_event_id=inbound_event_id,
        )
        product_source_id = uuid.UUID(source_result["product_source_id"])

        cycle = await DeliveryCycleService().create(
            session,
            project_id,
            DeliveryCycleType.FEATURE_CHANGE,
            title,
            ctx,
        )
        key = await next_project_key(session, project_id, "change_request", prefix="CR")
        cr = ChangeRequest(
            key=key,
            project_id=project_id,
            delivery_cycle_id=cycle.id,
            title=title,
            description=description,
            source_type=source_type,
            external_ref=external_ref,
            inbound_event_id=inbound_event_id,
            product_source_id=product_source_id,
            status="RECEIVED",
        )
        session.add(cr)
        await session.flush()
        await append_domain_event(
            session,
            aggregate_type="change_request",
            aggregate_id=cr.id,
            event_type="change_request.received",
            payload={"key": key, "cycle_id": str(cycle.id)},
            actor_id=ctx.actor.id,
            correlation_id=ctx.correlation_id,
            project_id=project_id,
            delivery_cycle_id=cycle.id,
        )
        return cr

    async def get_by_cycle(
        self, session: AsyncSession, cycle_id: uuid.UUID
    ) -> ChangeRequest | None:
        return (
            await session.execute(
                select(ChangeRequest).where(ChangeRequest.delivery_cycle_id == cycle_id)
            )
        ).scalar_one_or_none()

    async def get(self, session: AsyncSession, cr_id: uuid.UUID) -> ChangeRequest:
        row = await session.get(ChangeRequest, cr_id)
        if row is None:
            raise DomainError(code="NOT_FOUND", message="ChangeRequest not found")
        return row

    async def build_interpretation_context(
        self,
        session: AsyncSession,
        cycle_id: uuid.UUID,
    ) -> dict[str, Any]:
        cr = await self.get_by_cycle(session, cycle_id)
        if cr is None:
            raise DomainError(code="NOT_FOUND", message="ChangeRequest not linked")
        hybrid = HybridRetrieval(session)
        candidates = await hybrid.resolve_feature(cr.description, cr.project_id)
        cr.candidate_features = [c.model_dump(mode="json") for c in candidates]
        await session.flush()
        from core.planning.architecture.service import ArchitectureService

        arch = await ArchitectureService().get_approved(session, cr.project_id)
        arch_summary = ""
        if arch is not None:
            body = ArchitectureService().parse_body(arch)
            arch_summary = body.summary
        return {
            "change_request_text": cr.description,
            "candidates": cr.candidate_features,
            "architecture_summary": arch_summary,
            "project_id": str(cr.project_id),
        }

    async def persist_interpretation(
        self,
        session: AsyncSession,
        cycle_id: uuid.UUID,
        interpretation: ChangeInterpretation,
        execution_id: uuid.UUID,
        ctx: CommandContext,
    ) -> ChangeRequest:
        cr = await self.get_by_cycle(session, cycle_id)
        if cr is None:
            raise DomainError(code="NOT_FOUND", message="ChangeRequest not linked")
        candidates = cr.candidate_features or []
        candidate_keys = {str(c.get("feature_key")) for c in candidates if c.get("feature_key")}
        from_spec_id: uuid.UUID | None = None
        current_ac_keys: set[str] = set()
        if interpretation.resolution == "EXISTING_FEATURE":
            assert interpretation.feature_key
            feat_id = await ChangeInterpretationValidator().resolve_feature_id(
                session, cr.project_id, interpretation.feature_key
            )
            if feat_id is None:
                raise DomainError(code="INVALID_INPUT", message="feature_key not found")
            cr.resolved_feature_id = feat_id
            latest = (
                await session.execute(
                    select(FeatureSpec)
                    .where(
                        FeatureSpec.feature_id == feat_id,
                        FeatureSpec.status == SpecStatus.APPROVED,
                    )
                    .order_by(FeatureSpec.version.desc())
                    .limit(1)
                )
            ).scalar_one_or_none()
            if latest is None:
                raise DomainError(code="INVALID_STATE", message="No approved FeatureSpec")
            from_spec_id = latest.id
            current_ac_keys = await ChangeInterpretationValidator().load_current_ac_keys(
                session, latest.id
            )
        ok, errors = ChangeInterpretationValidator().validate(
            interpretation,
            candidate_feature_keys=candidate_keys,
            current_ac_lineage_keys=current_ac_keys,
        )
        if not ok:
            raise DomainError(
                code="INTERPRETATION_INVALID",
                message="; ".join(errors),
                details={"errors": errors},
            )

        to_spec = await self._materialize_proposed_spec(
            session,
            cr,
            interpretation,
            from_spec_id,
            ctx,
        )
        delta = await SpecDeltaService().compute(
            session,
            from_spec_id=from_spec_id,
            to_spec_id=to_spec.id,
            delivery_cycle_id=cycle_id,
            ctx=ctx,
        )
        await SpecDeltaService().request_approval(session, delta.id, ctx)
        cr.interpretation = interpretation.model_dump(mode="json")
        cr.interpretation_execution_id = execution_id
        cr.spec_delta_id = delta.id
        cr.status = "INTERPRETED"
        await session.flush()
        await append_domain_event(
            session,
            aggregate_type="change_request",
            aggregate_id=cr.id,
            event_type="change_request.interpreted",
            payload={"spec_delta_id": str(delta.id), "to_spec_id": str(to_spec.id)},
            actor_id=ctx.actor.id,
            correlation_id=ctx.correlation_id,
            project_id=cr.project_id,
            delivery_cycle_id=cycle_id,
        )
        return cr

    async def on_spec_delta_approved(
        self,
        session: AsyncSession,
        delta_id: uuid.UUID,
        approval_id: uuid.UUID,
        ctx: CommandContext,
    ) -> None:
        delta = await SpecDeltaService().mark_approved(session, delta_id, approval_id, ctx)
        to_spec = await session.get(FeatureSpec, delta.to_spec_id)
        if to_spec is None:
            return
        to_spec.status = SpecStatus.APPROVED
        to_spec.approval_id = approval_id
        if delta.from_spec_id:
            from_spec = await session.get(FeatureSpec, delta.from_spec_id)
            if from_spec is not None and from_spec.status == SpecStatus.APPROVED:
                from_spec.status = SpecStatus.SUPERSEDED
        await session.flush()
        await StalenessService().on_spec_delta_approved(
            session,
            project_id=to_spec.project_id,
            delivery_cycle_id=delta.delivery_cycle_id,
            from_spec_id=delta.from_spec_id,
            to_spec_id=delta.to_spec_id,
            ctx=ctx,
        )
        cr = (
            await session.execute(
                select(ChangeRequest).where(ChangeRequest.spec_delta_id == delta.id)
            )
        ).scalar_one_or_none()
        if cr is not None:
            cr.status = "SPEC_APPROVED"
            await session.flush()

    async def mark_in_delivery(
        self, session: AsyncSession, cycle_id: uuid.UUID, ctx: CommandContext
    ) -> None:
        cr = await self.get_by_cycle(session, cycle_id)
        if cr is not None and cr.status == "SPEC_APPROVED":
            cr.status = "IN_DELIVERY"
            await session.flush()

    async def decline_architecture_delta(
        self,
        session: AsyncSession,
        cycle_id: uuid.UUID,
        note: str,
        ctx: CommandContext,
    ) -> uuid.UUID:
        from core.domain.approvals.service import ApprovalService
        from core.domain.enums import ApprovalType

        cr = await self.get_by_cycle(session, cycle_id)
        if cr is None:
            raise DomainError(code="NOT_FOUND", message="ChangeRequest not linked")
        content_hash = sha256_hex({"decision": "no_architecture_change", "note": note})
        approval = await ApprovalService().request(
            session,
            cr.project_id,
            cycle_id,
            ApprovalType.ARCHITECTURE_DELTA,
            subject_type="ARCHITECTURE_DELTA_DECLINED",
            subject_id=cycle_id,
            subject_version=1,
            subject_hash=content_hash,
            ctx=ctx,
        )
        await append_domain_event(
            session,
            aggregate_type="architecture",
            aggregate_id=cycle_id,
            event_type="architecture_delta.declined",
            payload={"note": note, "approval_id": str(approval.id)},
            actor_id=ctx.actor.id,
            correlation_id=ctx.correlation_id,
            project_id=cr.project_id,
            delivery_cycle_id=cycle_id,
        )
        return approval.id

    async def mark_done(
        self,
        session: AsyncSession,
        cycle_id: uuid.UUID,
        release_id: uuid.UUID,
        ctx: CommandContext,
    ) -> None:
        cr = await self.get_by_cycle(session, cycle_id)
        if cr is None:
            return
        cr.status = "DONE"
        cr.release_id = release_id
        await session.flush()
        await append_domain_event(
            session,
            aggregate_type="change_request",
            aggregate_id=cr.id,
            event_type="change_request.done",
            payload={"release_id": str(release_id)},
            actor_id=ctx.actor.id,
            correlation_id=ctx.correlation_id,
            project_id=cr.project_id,
            delivery_cycle_id=cycle_id,
        )

    async def _materialize_proposed_spec(
        self,
        session: AsyncSession,
        cr: ChangeRequest,
        interpretation: ChangeInterpretation,
        from_spec_id: uuid.UUID | None,
        ctx: CommandContext,
    ) -> FeatureSpec:
        if interpretation.resolution == "EXISTING_FEATURE":
            assert cr.resolved_feature_id is not None
            feature_id = cr.resolved_feature_id
        else:
            # The model's feature_key may name an existing feature; new keys come from the sequence.
            feat_key = await next_project_key(session, cr.project_id, "feature", prefix="FEAT")
            feature = Feature(
                project_id=cr.project_id,
                key=feat_key,
                name=feat_key,
                description=interpretation.proposed_feature_spec.summary,
                status=EntityStatus.PROPOSED,
                origin=ModelOrigin.CHANGE,
                source_refs=[{"change_request_id": str(cr.id)}],
            )
            session.add(feature)
            await session.flush()
            feature_id = feature.id
            cr.resolved_feature_id = feature_id

        body = interpretation.proposed_feature_spec
        spec = await FeatureSpecService().create_draft_version(session, feature_id, body, ctx)
        spec.status = SpecStatus.PROPOSED
        await session.flush()

        if from_spec_id:
            _, from_reqs, _, from_acs = await FeatureSpecService().get_with_children(
                session, from_spec_id
            )
            req_map = {r.lineage_key: r for r in from_reqs}
            ac_map = {a.lineage_key: a for a in from_acs}
        else:
            req_map = {}
            ac_map = {}

        for change in interpretation.acceptance_criteria_changes:
            await self._apply_ac_change(session, spec.id, change, ac_map)

        for req in req_map.values():
            session.add(
                Requirement(
                    feature_spec_id=spec.id,
                    lineage_key=req.lineage_key,
                    statement=req.statement,
                    kind=req.kind,
                    priority=req.priority,
                    locked=req.locked,
                )
            )
        for ac in ac_map.values():
            removed_keys = {
                c.lineage_key
                for c in interpretation.acceptance_criteria_changes
                if c.op == "REMOVE"
            }
            if ac.lineage_key in removed_keys:
                continue
            if any(
                c.op in {"ADD", "MODIFY"} and c.lineage_key == ac.lineage_key
                for c in interpretation.acceptance_criteria_changes
            ):
                continue
            session.add(
                AcceptanceCriterion(
                    feature_spec_id=spec.id,
                    lineage_key=ac.lineage_key,
                    statement=ac.statement,
                    given=ac.given,
                    when=ac.when,
                    then=ac.then,
                    mandatory=ac.mandatory,
                    evidence_requirement=ac.evidence_requirement,
                    requirement_keys=list(ac.requirement_keys or []),
                )
            )
        await session.flush()
        return spec

    async def _apply_ac_change(
        self,
        session: AsyncSession,
        spec_id: uuid.UUID,
        change: AcChange,
        ac_map: dict[str, AcceptanceCriterion],
    ) -> None:
        if change.op == "ADD":
            assert change.lineage_key and change.statement is not None
            session.add(
                AcceptanceCriterion(
                    feature_spec_id=spec_id,
                    lineage_key=change.lineage_key,
                    statement=change.statement,
                    given=change.given,
                    when=change.when,
                    then=change.then,
                    mandatory=bool(change.mandatory),
                    evidence_requirement=change.evidence_requirement
                    or EvidenceRequirement.EXECUTABLE,
                    requirement_keys=[],
                    change_kind="ADDED",
                )
            )
        elif change.op == "MODIFY":
            assert change.lineage_key
            prev = ac_map.get(change.lineage_key)
            if prev is None:
                raise DomainError(
                    code="INVALID_INPUT",
                    message=f"MODIFY AC unknown lineage: {change.lineage_key}",
                )
            session.add(
                AcceptanceCriterion(
                    feature_spec_id=spec_id,
                    lineage_key=change.lineage_key,
                    statement=change.statement or prev.statement,
                    given=change.given if change.given is not None else prev.given,
                    when=change.when if change.when is not None else prev.when,
                    then=change.then if change.then is not None else prev.then,
                    mandatory=change.mandatory if change.mandatory is not None else prev.mandatory,
                    evidence_requirement=(
                        change.evidence_requirement
                        if change.evidence_requirement is not None
                        else prev.evidence_requirement
                    ),
                    requirement_keys=list(prev.requirement_keys),
                    change_kind="MODIFIED",
                )
            )
