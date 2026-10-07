"""Supportdesk impact analysis fixtures (Phase 13)."""

from __future__ import annotations

import uuid
from dataclasses import dataclass

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
from core.integration.enums import SpecCodeLinkOrigin, SpecCodeLinkRelation, SpecCodeLinkStatus
from core.intelligence.code_index.enums import IndexKind, IndexSource
from core.intelligence.code_index.indexer import CodeIndexer
from core.intelligence.code_index.models import CodeIndexVersion
from core.product_model.models import AcceptanceCriterion, Feature, FeatureSpec
from core.product_model.schemas import FeatureSpecBody
from core.product_model.specifications.service import FeatureSpecService
from core.traceability.models import RepositoryIndexPointer, SpecCodeLink
from sqlalchemy.ext.asyncio import AsyncSession
from tests.fixtures.code_index_harness import materialize_supportdesk_r1


@dataclass
class SupportdeskImpactFixture:
    repository_id: uuid.UUID
    project_id: uuid.UUID
    commit_sha: str
    index_version: CodeIndexVersion
    feature_id: uuid.UUID
    spec_v1_id: uuid.UUID
    spec_v2_id: uuid.UUID
    cycle_id: uuid.UUID
    ac_create_lineage: str


async def seed_supportdesk_ticket_priority_impact(
    session: AsyncSession,
    ctx: CommandContext,
) -> SupportdeskImpactFixture:
    repo, sha = await materialize_supportdesk_r1(session, ctx)
    version = await CodeIndexer().build(
        session,
        repo.id,
        sha,
        IndexKind.CANDIDATE,
        IndexSource.REPOSITORY_SNAPSHOT,
        ctx,
        scope_ref="impact-fixture",
    )
    pointer = await session.get(RepositoryIndexPointer, repo.id)
    if pointer is None:
        pointer = RepositoryIndexPointer(repository_id=repo.id)
        session.add(pointer)
    pointer.canonical_index_version_id = version.id
    await session.flush()

    cycle = await DeliveryCycleService().create(
        session,
        repo.project_id,
        DeliveryCycleType.FEATURE_CHANGE,
        "ticket priority impact",
        ctx,
    )
    cycle.repository_id = repo.id
    cycle.base_sha = sha
    await session.flush()

    feature = Feature(
        project_id=repo.project_id,
        key="FEAT-TICKETS",
        name="Tickets",
        description="Ticket lifecycle",
        status=EntityStatus.PROPOSED,
        origin=ModelOrigin.HUMAN,
        source_refs=[],
    )
    session.add(feature)
    await session.flush()

    body_v1 = FeatureSpecBody(
        behavior="Create and update tickets",
        summary="Tickets",
        inputs=["subject", "description"],
        outputs=["ticket"],
        rules=["priority defaults to MEDIUM"],
        constraints=[],
    )
    body_v1_dict = body_v1.model_dump(mode="json")
    spec_v1 = FeatureSpec(
        project_id=repo.project_id,
        feature_id=feature.id,
        lineage_key="SPEC-FEAT-TICKETS",
        version=1,
        status=SpecStatus.APPROVED,
        body=body_v1_dict,
        content_hash=sha256_hex(body_v1_dict),
    )
    session.add(spec_v1)
    await session.flush()

    body_v2 = body_v1.model_copy(
        update={
            "inputs": ["subject", "description", "priority"],
            "rules": ["priority is LOW, MEDIUM, or HIGH", "priority defaults to MEDIUM"],
        }
    )
    spec_v2 = await FeatureSpecService().create_draft_version(session, feature.id, body_v2, ctx)
    spec_v2.status = SpecStatus.APPROVED
    await session.flush()

    ac = AcceptanceCriterion(
        feature_spec_id=spec_v2.id,
        lineage_key="AC-TICKET-PRIORITY",
        statement="Ticket stores priority LOW, MEDIUM, or HIGH",
        given="valid ticket payload",
        when="creating a ticket",
        then="priority is persisted",
        mandatory=True,
        evidence_requirement=EvidenceRequirement.EXECUTABLE,
        requirement_keys=[],
    )
    session.add(ac)
    await session.flush()

    route_key = "ROUTE:POST /tickets"
    for lineage, relation in (
        (spec_v2.lineage_key, SpecCodeLinkRelation.IMPLEMENTS),
        (ac.lineage_key, SpecCodeLinkRelation.VERIFIES),
    ):
        session.add(
            SpecCodeLink(
                project_id=repo.project_id,
                repository_id=repo.id,
                spec_type="FEATURE_SPEC" if relation == SpecCodeLinkRelation.IMPLEMENTS else "AC",
                spec_id=spec_v2.id if relation == SpecCodeLinkRelation.IMPLEMENTS else ac.id,
                spec_lineage_key=lineage,
                code_stable_key=route_key,
                relation=relation,
                origin=SpecCodeLinkOrigin.HUMAN_CONFIRMED,
                confidence=1.0,
                established_index_version_id=version.id,
                last_confirmed_index_version_id=version.id,
                status=SpecCodeLinkStatus.ACTIVE,
            )
        )
    await session.flush()

    return SupportdeskImpactFixture(
        repository_id=repo.id,
        project_id=repo.project_id,
        commit_sha=sha,
        index_version=version,
        feature_id=feature.id,
        spec_v1_id=spec_v1.id,
        spec_v2_id=spec_v2.id,
        cycle_id=cycle.id,
        ac_create_lineage=ac.lineage_key,
    )
