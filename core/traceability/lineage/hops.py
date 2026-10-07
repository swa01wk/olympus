"""Default forward lineage hops (Phase 08 fixture-complete paths)."""

from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.domain.enums import SpecStatus
from core.integration.enums import SpecCodeLinkStatus
from core.planning.models import ImplementationSpec, TaskSpecRef
from core.product_model.models import Capability, Feature, FeatureSpec
from core.traceability.lineage.service import LineageEdge, LineageGraph, LineageNode
from core.traceability.models import SpecCodeLink


async def hop_feature_to_specs(session: AsyncSession, graph: LineageGraph, root_id: str) -> None:
    feature = await session.get(Feature, uuid.UUID(root_id))
    if feature is None:
        return
    specs = await session.execute(
        select(FeatureSpec).where(
            FeatureSpec.feature_id == feature.id,
            FeatureSpec.status == SpecStatus.APPROVED,
        )
    )
    for spec in specs.scalars():
        node_id = str(spec.id)
        if any(n.id == node_id for n in graph.nodes):
            continue
        graph.nodes.append(
            LineageNode(
                type="FEATURE_SPEC",
                id=node_id,
                key=spec.lineage_key,
                version=spec.version,
            )
        )
        graph.edges.append(
            LineageEdge(from_id=root_id, to_id=node_id, relation="HAS_SPEC", origin="STRUCTURAL")
        )


async def hop_specs_to_impl_and_code(
    session: AsyncSession, graph: LineageGraph, _root_id: str
) -> None:
    for node in list(graph.nodes):
        if node.type == "FEATURE_SPEC":
            impls = await session.execute(
                select(ImplementationSpec).where(
                    ImplementationSpec.feature_spec_id == uuid.UUID(node.id),
                    ImplementationSpec.status == SpecStatus.APPROVED,
                )
            )
            for impl in impls.scalars():
                impl_id = str(impl.id)
                if not any(n.id == impl_id for n in graph.nodes):
                    graph.nodes.append(
                        LineageNode(
                            type="IMPLEMENTATION_SPEC",
                            id=impl_id,
                            key=impl.lineage_key,
                            version=impl.version,
                        )
                    )
                    graph.edges.append(
                        LineageEdge(
                            from_id=node.id,
                            to_id=impl_id,
                            relation="IMPLEMENTS_SPEC",
                            origin="STRUCTURAL",
                        )
                    )
                refs = await session.execute(
                    select(TaskSpecRef).where(
                        TaskSpecRef.ref_type == "IMPLEMENTATION_SPEC",
                        TaskSpecRef.ref_id == impl.id,
                    )
                )
                for ref in refs.scalars():
                    task_id = str(ref.task_id)
                    if not any(n.id == task_id for n in graph.nodes):
                        graph.nodes.append(
                            LineageNode(type="TASK", id=task_id, key=task_id),
                        )
                        graph.edges.append(
                            LineageEdge(
                                from_id=impl_id,
                                to_id=task_id,
                                relation="PLANNED_AS",
                                origin="STRUCTURAL",
                            )
                        )
        if node.type in {"IMPLEMENTATION_SPEC", "FEATURE_SPEC"}:
            links = await session.execute(
                select(SpecCodeLink).where(
                    SpecCodeLink.spec_id == uuid.UUID(node.id),
                    SpecCodeLink.status == SpecCodeLinkStatus.ACTIVE,
                )
            )
            for link in links.scalars():
                code_id = link.code_stable_key
                if not any(n.id == code_id for n in graph.nodes):
                    graph.nodes.append(
                        LineageNode(
                            type="CODE_ENTITY",
                            id=code_id,
                            key=code_id,
                            origin=link.origin.value,
                            confidence=link.confidence,
                        )
                    )
                graph.edges.append(
                    LineageEdge(
                        from_id=node.id,
                        to_id=code_id,
                        relation=link.relation.value,
                        origin=link.origin.value,
                        confidence=link.confidence,
                    )
                )


async def hop_ac_to_evidence(session: AsyncSession, graph: LineageGraph, _root_id: str) -> None:
    from core.assurance.models import Evidence
    from core.product_model.models import AcceptanceCriterion

    for node in list(graph.nodes):
        if node.type != "ACCEPTANCE_CRITERION":
            continue
        ac = await session.get(AcceptanceCriterion, uuid.UUID(node.id))
        if ac is None:
            continue
        evidence_rows = await session.execute(
            select(Evidence).where(
                Evidence.subject_type == "AC",
                Evidence.subject_id == ac.id,
            )
        )
        for ev in evidence_rows.scalars():
            ev_id = str(ev.id)
            if not any(n.id == ev_id for n in graph.nodes):
                graph.nodes.append(
                    LineageNode(type="EVIDENCE", id=ev_id, key=ev.key, label=ev.commit_sha)
                )
                graph.edges.append(
                    LineageEdge(
                        from_id=node.id,
                        to_id=ev_id,
                        relation="VERIFIED_BY",
                        origin="STRUCTURAL",
                    )
                )


async def hop_evidence_to_ic(session: AsyncSession, graph: LineageGraph, _root_id: str) -> None:
    from core.assurance.models import Evidence
    from core.integration.models import IntegrationCandidate

    for node in list(graph.nodes):
        if node.type != "EVIDENCE":
            continue
        ev = await session.get(Evidence, uuid.UUID(node.id))
        if ev is None or ev.integration_candidate_id is None:
            continue
        ic = await session.get(IntegrationCandidate, ev.integration_candidate_id)
        if ic is None:
            continue
        ic_id = str(ic.id)
        if not any(n.id == ic_id for n in graph.nodes):
            graph.nodes.append(
                LineageNode(
                    type="INTEGRATION_CANDIDATE",
                    id=ic_id,
                    key=ic.key,
                    label=ic.integrated_sha,
                )
            )
        graph.edges.append(
            LineageEdge(
                from_id=node.id,
                to_id=ic_id,
                relation="TARGETS",
                origin="STRUCTURAL",
            )
        )


async def hop_finding_to_remediation_task(
    session: AsyncSession, graph: LineageGraph, _root_id: str
) -> None:
    from core.assurance.models import Finding

    for node in list(graph.nodes):
        if node.type != "FINDING":
            continue
        finding = await session.get(Finding, uuid.UUID(node.id))
        if finding is None or finding.remediation_task_id is None:
            continue
        task_id = str(finding.remediation_task_id)
        if not any(n.id == task_id for n in graph.nodes):
            graph.nodes.append(LineageNode(type="TASK", id=task_id, key=task_id))
        graph.edges.append(
            LineageEdge(
                from_id=node.id,
                to_id=task_id,
                relation="REMEDIATED_BY",
                origin="STRUCTURAL",
            )
        )


async def hop_reverse_product_context(
    session: AsyncSession, graph: LineageGraph, _root_id: str
) -> None:
    """Extend reverse graphs from FEATURE_SPEC toward Feature and Capability."""
    for node in list(graph.nodes):
        if node.type != "FEATURE_SPEC":
            continue
        spec = await session.get(FeatureSpec, uuid.UUID(node.id))
        if spec is None or spec.feature_id is None:
            continue
        feature = await session.get(Feature, spec.feature_id)
        if feature is None:
            continue
        feat_id = str(feature.id)
        if not any(n.id == feat_id for n in graph.nodes):
            graph.nodes.append(
                LineageNode(type="FEATURE", id=feat_id, key=feature.key, label=feature.name)
            )
            graph.edges.append(
                LineageEdge(
                    from_id=feat_id,
                    to_id=node.id,
                    relation="HAS_SPEC",
                    origin="STRUCTURAL",
                )
            )
        if feature.capability_id is not None:
            cap = await session.get(Capability, feature.capability_id)
            if cap is not None:
                cap_id = str(cap.id)
                if not any(n.id == cap_id for n in graph.nodes):
                    graph.nodes.append(
                        LineageNode(type="CAPABILITY", id=cap_id, key=cap.key, label=cap.name)
                    )
                    graph.edges.append(
                        LineageEdge(
                            from_id=cap_id,
                            to_id=feat_id,
                            relation="INCLUDES",
                            origin="STRUCTURAL",
                        )
                    )
