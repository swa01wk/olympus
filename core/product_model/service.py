from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.commands.context import CommandContext
from core.domain.canonical_json import sha256_hex
from core.domain.enums import (
    ClarificationStatus,
    DecompositionStatus,
    EntityStatus,
    KnowledgeClass,
    KnowledgeItemStatus,
    ModelOrigin,
    SpecStatus,
)
from core.domain.events.append import append_domain_event
from core.domain.executions.models import Clarification
from core.domain.sequences import next_project_key
from core.product_model.models import (
    AcceptanceCriterion,
    Capability,
    Feature,
    FeatureSpec,
    KnowledgeItem,
    Requirement,
    UserStory,
)
from core.product_model.models import (
    ProductDecomposition as ProductDecompositionRow,
)
from core.product_model.schemas import ProductDecomposition
from core.product_model.validation import sanitize_proposal_requirement_refs, validate_proposal


class ProductModelService:
    async def persist_proposal(
        self,
        session: AsyncSession,
        *,
        project_id: uuid.UUID,
        delivery_cycle_id: uuid.UUID,
        product_source_version_id: uuid.UUID,
        execution_id: uuid.UUID | None,
        proposal: ProductDecomposition,
        ctx: CommandContext,
    ) -> ProductDecompositionRow:
        proposal = sanitize_proposal_requirement_refs(proposal)
        errors = validate_proposal(proposal)
        if errors:
            raise ValueError(f"proposal validation failed: {errors}")

        await self._supersede_unapproved(session, project_id, delivery_cycle_id)

        cap_id_by_ref: dict[str, uuid.UUID] = {}
        for cap_draft in proposal.capabilities:
            key = await next_project_key(session, project_id, "capability", prefix="CAP")
            row = Capability(
                project_id=project_id,
                key=key,
                name=cap_draft.name,
                description=cap_draft.description,
                status=EntityStatus.PROPOSED,
                origin=ModelOrigin.GREENFIELD,
                source_refs=[
                    {
                        "product_source_version_id": str(product_source_version_id),
                        "section": s,
                    }
                    for s in cap_draft.source_sections
                ],
            )
            session.add(row)
            await session.flush()
            cap_id_by_ref[cap_draft.ref] = row.id

        feat_id_by_ref: dict[str, uuid.UUID] = {}
        for feat_draft in proposal.features:
            key = await next_project_key(session, project_id, "feature", prefix="FEAT")
            feat_row = Feature(
                project_id=project_id,
                capability_id=cap_id_by_ref.get(feat_draft.capability_ref),
                key=key,
                name=feat_draft.name,
                description=feat_draft.description,
                status=EntityStatus.PROPOSED,
                origin=ModelOrigin.GREENFIELD,
                source_refs=[
                    {
                        "product_source_version_id": str(product_source_version_id),
                        "section": s,
                    }
                    for s in feat_draft.source_sections
                ],
            )
            session.add(feat_row)
            await session.flush()
            feat_id_by_ref[feat_draft.ref] = feat_row.id

        spec_id_by_ref: dict[str, uuid.UUID] = {}
        for spec_draft in proposal.feature_specs:
            feature_id = feat_id_by_ref[spec_draft.feature_ref]
            feat = await session.get(Feature, feature_id)
            lineage = f"SPEC-{feat.key}" if feat else f"SPEC-{spec_draft.ref}"
            body = spec_draft.body.model_dump(mode="json")
            content_hash = sha256_hex(body)
            spec = FeatureSpec(
                project_id=project_id,
                feature_id=feature_id,
                lineage_key=lineage,
                version=1,
                status=SpecStatus.PROPOSED,
                body=body,
                content_hash=content_hash,
                derived_from_source_version_id=product_source_version_id,
            )
            session.add(spec)
            await session.flush()
            spec_id_by_ref[spec_draft.ref] = spec.id
            await append_domain_event(
                session,
                aggregate_type="feature_spec",
                aggregate_id=spec.id,
                event_type="feature_spec.proposed",
                payload={"lineage_key": lineage, "version": 1},
                actor_id=ctx.actor.id,
                correlation_id=ctx.correlation_id,
                project_id=project_id,
                delivery_cycle_id=delivery_cycle_id,
            )

        for req_draft in proposal.requirements:
            spec_id = spec_id_by_ref[req_draft.feature_spec_ref]
            session.add(
                Requirement(
                    feature_spec_id=spec_id,
                    lineage_key=req_draft.ref,
                    statement=req_draft.statement,
                    kind=req_draft.kind,
                    priority=req_draft.priority,
                )
            )

        for story_draft in proposal.user_stories:
            spec_id = spec_id_by_ref[story_draft.feature_spec_ref]
            session.add(
                UserStory(
                    feature_spec_id=spec_id,
                    lineage_key=story_draft.ref,
                    actor=story_draft.actor,
                    goal=story_draft.goal,
                    benefit=story_draft.benefit,
                )
            )

        for ac_draft in proposal.acceptance_criteria:
            spec_id = spec_id_by_ref[ac_draft.feature_spec_ref]
            session.add(
                AcceptanceCriterion(
                    feature_spec_id=spec_id,
                    lineage_key=ac_draft.ref,
                    statement=ac_draft.statement,
                    given=ac_draft.given,
                    when=ac_draft.when,
                    then=ac_draft.then,
                    mandatory=ac_draft.mandatory,
                    evidence_requirement=ac_draft.evidence_requirement,
                    requirement_keys=ac_draft.requirement_refs,
                )
            )

        for q in proposal.open_questions:
            cl_key = await next_project_key(session, project_id, "clarification", prefix="CL")
            session.add(
                Clarification(
                    key=cl_key,
                    project_id=project_id,
                    delivery_cycle_id=delivery_cycle_id,
                    execution_id=execution_id,
                    question=q.question,
                    context={"text": q.context, "related_refs": q.related_refs},
                    options=q.options,
                    blocking=q.blocking,
                    status=ClarificationStatus.OPEN,
                )
            )

        for idx, assumption in enumerate(proposal.assumptions):
            stmt = assumption.strip()
            if not stmt:
                continue
            session.add(
                KnowledgeItem(
                    project_id=project_id,
                    delivery_cycle_id=delivery_cycle_id,
                    knowledge_class=KnowledgeClass.ASSUMPTION,
                    statement=stmt,
                    subject_refs=[{"ref_type": "PRODUCT_DECOMPOSITION", "ref_id": str(idx)}],
                    provenance={"origin": "KIRA", "execution_id": str(execution_id or "")},
                    status=KnowledgeItemStatus.ACTIVE,
                    blocking=False,
                )
            )

        decomp = ProductDecompositionRow(
            delivery_cycle_id=delivery_cycle_id,
            product_source_version_id=product_source_version_id,
            execution_id=execution_id,
            status=DecompositionStatus.PROPOSED,
            validation_report={"errors": []},
        )
        session.add(decomp)
        await session.flush()

        for spec_id in spec_id_by_ref.values():
            spec_row = await session.get(FeatureSpec, spec_id)
            if spec_row:
                spec_row.decomposition_id = decomp.id

        await append_domain_event(
            session,
            aggregate_type="product_decomposition",
            aggregate_id=decomp.id,
            event_type="product_decomposition.proposed",
            payload={"execution_id": str(execution_id)},
            actor_id=ctx.actor.id,
            correlation_id=ctx.correlation_id,
            project_id=project_id,
            delivery_cycle_id=delivery_cycle_id,
        )
        return decomp

    async def _supersede_unapproved(
        self,
        session: AsyncSession,
        project_id: uuid.UUID,
        delivery_cycle_id: uuid.UUID,
    ) -> None:
        decomps = await session.execute(
            select(ProductDecompositionRow).where(
                ProductDecompositionRow.delivery_cycle_id == delivery_cycle_id,
                ProductDecompositionRow.status == DecompositionStatus.PROPOSED,
            )
        )
        for row in decomps.scalars():
            row.status = DecompositionStatus.SUPERSEDED

        specs = await session.execute(
            select(FeatureSpec).where(
                FeatureSpec.project_id == project_id,
                FeatureSpec.status.in_([SpecStatus.PROPOSED, SpecStatus.DRAFT]),
            )
        )
        for spec in specs.scalars():
            spec.status = SpecStatus.SUPERSEDED
