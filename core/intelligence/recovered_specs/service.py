from __future__ import annotations

import uuid
from typing import Any

from agents.scout.schemas import RecoveredFeatureSpec, RepositorySurvey
from sqlalchemy.ext.asyncio import AsyncSession

from core.commands.context import CommandContext
from core.domain.canonical_json import sha256_hex
from core.domain.enums import (
    EntityStatus,
    KnowledgeClass,
    KnowledgeItemStatus,
    ModelOrigin,
    SpecKind,
    SpecStatus,
)
from core.domain.events.append import append_domain_event
from core.domain.sequences import next_project_key
from core.integration.enums import SpecCodeLinkOrigin, SpecCodeLinkRelation, SpecCodeLinkStatus
from core.intelligence.brownfield.enums import RecoveryProposalStatus
from core.intelligence.brownfield.models import RecoveredSpecEvidence, RecoveryProposal
from core.planning.models import Architecture, ImplementationSpec
from core.product_model.models import (
    AcceptanceCriterion,
    Capability,
    Feature,
    FeatureSpec,
    KnowledgeItem,
    Requirement,
)
from core.traceability.models import SpecCodeLink


class RecoveryService:
    async def persist(
        self,
        session: AsyncSession,
        *,
        delivery_cycle_id: uuid.UUID,
        project_id: uuid.UUID,
        survey: RepositorySurvey,
        feature_specs: list[RecoveredFeatureSpec],
        survey_execution_id: uuid.UUID,
        feature_execution_ids: list[uuid.UUID],
        context_manifest_hash: str,
        validation_report: dict[str, Any],
        ctx: CommandContext,
        repository_id: uuid.UUID,
        index_version_id: uuid.UUID,
        commit_sha: str,
    ) -> RecoveryProposal:
        from core.domain.enums import EvidenceRequirement

        arch_body = survey.recovered_architecture.model_dump(mode="json")
        arch = Architecture(
            project_id=project_id,
            version=1,
            status=SpecStatus.PROPOSED,
            kind="RECOVERED",
            body=arch_body,
            content_hash=sha256_hex(arch_body),
            execution_id=survey_execution_id,
        )
        session.add(arch)
        await session.flush()

        cap_ids: dict[str, uuid.UUID] = {}
        for cap in survey.capabilities:
            key = await next_project_key(session, project_id, "capability", prefix="CAP")
            cap_row = Capability(
                project_id=project_id,
                key=key,
                name=cap.name,
                description=cap.description,
                status=EntityStatus.PROPOSED,
                origin=ModelOrigin.RECOVERED,
            )
            session.add(cap_row)
            await session.flush()
            cap_ids[cap.ref] = cap_row.id

        feat_ids: dict[str, uuid.UUID] = {}
        for feature_draft in survey.features:
            key = await next_project_key(session, project_id, "feature", prefix="FEAT")
            feature_row = Feature(
                project_id=project_id,
                capability_id=cap_ids.get(feature_draft.capability_ref),
                key=key,
                name=feature_draft.name,
                description=feature_draft.description,
                status=EntityStatus.PROPOSED,
                origin=ModelOrigin.RECOVERED,
            )
            session.add(feature_row)
            await session.flush()
            feat_ids[feature_draft.ref] = feature_row.id

        spec_by_ref: dict[str, FeatureSpec] = {}
        for recovered in feature_specs:
            feature_id = feat_ids.get(recovered.feature_ref)
            if feature_id is None:
                continue
            feature_entity = await session.get(Feature, feature_id)
            if feature_entity is None:
                continue
            body = recovered.body.model_dump(mode="json")
            claimed = recovered.confidence
            persisted = (
                validation_report.get("features", {})
                .get(recovered.feature_ref, {})
                .get("persisted_confidence", claimed)
            )
            spec = FeatureSpec(
                project_id=project_id,
                feature_id=feature_id,
                lineage_key=f"SPEC-{feature_entity.key}",
                version=1,
                status=SpecStatus.PROPOSED,
                spec_kind=SpecKind.RECOVERED,
                body=body,
                content_hash=sha256_hex(body),
                confidence=persisted,
                claimed_confidence=claimed,
                uncertainty_count=len(recovered.uncertainties),
            )
            session.add(spec)
            await session.flush()
            spec_by_ref[recovered.feature_ref] = spec
            for req in recovered.requirements:
                session.add(
                    Requirement(
                        feature_spec_id=spec.id,
                        lineage_key=req.ref,
                        statement=req.statement,
                        kind="FUNCTIONAL",
                        priority="SHOULD",
                    )
                )
            for ac in recovered.acceptance_criteria:
                session.add(
                    AcceptanceCriterion(
                        feature_spec_id=spec.id,
                        lineage_key=ac.ref,
                        statement=ac.statement,
                        given=ac.given,
                        when=ac.when,
                        then=ac.then,
                        mandatory=False,
                        evidence_requirement=EvidenceRequirement.EXECUTABLE,
                    )
                )
                for cit in ac.citations:
                    session.add(
                        RecoveredSpecEvidence(
                            feature_spec_id=spec.id,
                            element_type="AC",
                            element_key=ac.ref,
                            support_type=cit.ref_type,
                            support_ref=cit.ref,
                            strength="PRIMARY",
                        )
                    )
            if recovered.implementation is not None:
                impl_body = recovered.implementation.model_dump(mode="json")
                session.add(
                    ImplementationSpec(
                        project_id=project_id,
                        lineage_key=f"IMPL-{spec.lineage_key}",
                        version=1,
                        status=SpecStatus.PROPOSED,
                        kind="RECOVERED",
                        feature_spec_id=spec.id,
                        architecture_id=arch.id,
                        body=impl_body,
                        content_hash=sha256_hex(impl_body),
                    )
                )
            for link in recovered.principal_entity_links:
                raw_conf = link.get("confidence", 0.7)
                link_conf = float(raw_conf) if isinstance(raw_conf, int | float | str) else 0.7
                session.add(
                    SpecCodeLink(
                        project_id=project_id,
                        repository_id=repository_id,
                        spec_type="FEATURE_SPEC",
                        spec_id=spec.id,
                        spec_lineage_key=spec.lineage_key,
                        code_stable_key=str(link.get("stable_key", "")),
                        relation=SpecCodeLinkRelation.IMPLEMENTS,
                        origin=SpecCodeLinkOrigin.DISCOVERED,
                        status=SpecCodeLinkStatus.ACTIVE,
                        confidence=link_conf,
                        evidence_refs=[],
                        established_index_version_id=index_version_id,
                        last_confirmed_index_version_id=index_version_id,
                        commit_sha=commit_sha,
                    )
                )

        for inf in survey.inferences + [i for fs in feature_specs for i in fs.inferences]:
            session.add(
                KnowledgeItem(
                    project_id=project_id,
                    delivery_cycle_id=delivery_cycle_id,
                    knowledge_class=KnowledgeClass.INFERENCE,
                    statement=inf.statement,
                    provenance={
                        "origin": "SCOUT",
                        "citations": [c.model_dump() for c in inf.citations],
                    },
                    confidence=inf.confidence,
                    status=KnowledgeItemStatus.ACTIVE,
                )
            )
        for unc in survey.uncertainties + [u for fs in feature_specs for u in fs.uncertainties]:
            session.add(
                KnowledgeItem(
                    project_id=project_id,
                    delivery_cycle_id=delivery_cycle_id,
                    knowledge_class=KnowledgeClass.UNCERTAINTY,
                    statement=unc.question,
                    provenance={"origin": "SCOUT", "why": unc.why_uncertain},
                    status=KnowledgeItemStatus.ACTIVE,
                    blocking=unc.blocking_suggested,
                )
            )

        proposal = RecoveryProposal(
            delivery_cycle_id=delivery_cycle_id,
            survey_execution_id=survey_execution_id,
            feature_execution_ids=[str(i) for i in feature_execution_ids],
            status=RecoveryProposalStatus.VALIDATED,
            validation_report=validation_report,
            context_manifest_hash=context_manifest_hash,
        )
        session.add(proposal)
        await session.flush()
        await append_domain_event(
            session,
            aggregate_type="recovery_proposal",
            aggregate_id=proposal.id,
            event_type="recovery.validated",
            payload={"delivery_cycle_id": str(delivery_cycle_id)},
            actor_id=ctx.actor.id,
            correlation_id=ctx.correlation_id,
            project_id=project_id,
            delivery_cycle_id=delivery_cycle_id,
        )
        return proposal
