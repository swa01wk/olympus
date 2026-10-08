from __future__ import annotations

import uuid

import pytest
from core.domain.delivery_cycles.service import DeliveryCycleService
from core.domain.enums import (
    DeliveryCycleType,
    EntityStatus,
    EvidenceRequirement,
    KnowledgeClass,
    KnowledgeItemStatus,
    ModelOrigin,
    SpecKind,
    SpecStatus,
)
from core.intelligence.brownfield.models import RecoveredSpecEvidence
from core.product_model.models import (
    AcceptanceCriterion,
    Capability,
    Feature,
    FeatureSpec,
    KnowledgeItem,
    ProductSource,
)
from core.product_model.service import ProductModelService
from core.product_model.sources.service import ProductSourceService
from core.product_model.spec_view import ProductSpecViewService
from core.product_model.specifications.scope import ScopeService
from sqlalchemy import select
from tests.fixtures.product_model_harness import supportdesk_decomposition

pytestmark = pytest.mark.persistence


@pytest.mark.asyncio
async def test_product_spec_view_greenfield_decomposed(
    db_session, sample_project, operator_actor, operator_ctx
) -> None:
    cycle = await DeliveryCycleService().create(
        db_session,
        sample_project.id,
        DeliveryCycleType.GREENFIELD_BUILD,
        "product-spec-gf",
        operator_ctx,
    )
    ingest = await ProductSourceService().ingest(
        db_session,
        project_id=sample_project.id,
        lineage_key="psv",
        source_type="PRD",
        title="Support PRD",
        mime_type="text/plain",
        content_hash="abc12345",
        raw_storage_ref="inbound/sha256/x/abc12345",
        text="hello",
        ctx=operator_ctx,
        delivery_cycle_id=cycle.id,
    )
    source = await db_session.get(ProductSource, uuid.UUID(ingest["product_source_id"]))
    assert source is not None
    await ProductModelService().persist_proposal(
        db_session,
        project_id=sample_project.id,
        delivery_cycle_id=cycle.id,
        product_source_version_id=source.id,
        execution_id=None,
        proposal=supportdesk_decomposition(),
        ctx=operator_ctx,
    )
    specs = (
        await db_session.execute(
            select(FeatureSpec).where(FeatureSpec.project_id == sample_project.id)
        )
    ).scalars()
    spec_ids = [s.id for s in specs]
    scope_set, approval_id = await ScopeService().request_scope_approval(
        db_session,
        cycle.id,
        spec_ids,
        sample_project.id,
        operator_ctx,
    )
    from core.domain.approvals.service import ApprovalService
    from core.domain.enums import ApprovalStatus

    await ApprovalService().decide(
        db_session, approval_id, ApprovalStatus.APPROVED, None, operator_ctx
    )
    await ScopeService().on_scope_approved(db_session, scope_set.id, approval_id, operator_ctx)

    doc = await ProductSpecViewService().build(db_session, sample_project.id)
    assert doc["capabilities"]
    feat = doc["capabilities"][0]["features"][0]
    prov = feat["spec"]["provenance"]
    assert prov["kind"] == "greenfield"
    assert prov["product_source_title"] == "Support PRD"
    assert prov["product_source_version"] == source.version


@pytest.mark.asyncio
async def test_product_spec_view_brownfield_promoted(
    db_session, sample_project, operator_ctx
) -> None:
    cap = Capability(
        project_id=sample_project.id,
        key="CAP-BF",
        name="Cards",
        description="Card domain",
        status=EntityStatus.APPROVED,
        origin=ModelOrigin.RECOVERED,
        source_refs=[],
    )
    db_session.add(cap)
    await db_session.flush()
    feat = Feature(
        project_id=sample_project.id,
        capability_id=cap.id,
        key="FEAT-BF",
        name="Move card",
        description="Move cards on board",
        status=EntityStatus.APPROVED,
        origin=ModelOrigin.RECOVERED,
        source_refs=[{"section": "Board"}],
    )
    db_session.add(feat)
    await db_session.flush()
    recovered = FeatureSpec(
        project_id=sample_project.id,
        feature_id=feat.id,
        lineage_key="REC-1",
        version=1,
        status=SpecStatus.PROMOTED,
        spec_kind=SpecKind.RECOVERED,
        body={"behavior": "Drag card", "summary": "Move", "inputs": [], "outputs": [], "rules": []},
        content_hash="recoveredhash1",
        confidence="HIGH",
    )
    db_session.add(recovered)
    await db_session.flush()
    db_session.add(
        RecoveredSpecEvidence(
            feature_spec_id=recovered.id,
            element_type="AC",
            element_key="AC-1",
            support_type="TEST",
            support_ref="tests/test_cards.py::test_move_card",
            strength="HIGH",
        )
    )
    canonical = FeatureSpec(
        project_id=sample_project.id,
        feature_id=feat.id,
        lineage_key="CAN-1",
        version=1,
        status=SpecStatus.APPROVED,
        spec_kind=SpecKind.CANONICAL,
        body={
            "behavior": "Drag card",
            "summary": "Move",
            "inputs": [],
            "outputs": [],
            "rules": ["Cards move between columns"],
        },
        content_hash="canonicalhash1",
        promoted_from_id=recovered.id,
    )
    db_session.add(canonical)
    await db_session.flush()
    db_session.add(
        AcceptanceCriterion(
            feature_spec_id=canonical.id,
            lineage_key="AC-1",
            statement="Card moves",
            given="a card on column A",
            when="user drags to column B",
            then="card is on column B",
            mandatory=True,
            evidence_requirement=EvidenceRequirement.EXECUTABLE,
        )
    )
    db_session.add(
        KnowledgeItem(
            project_id=sample_project.id,
            knowledge_class=KnowledgeClass.UNCERTAINTY,
            statement="Edge case unverified",
            subject_refs=[{"feature_id": str(feat.id)}],
            provenance={"accepted_known_gap": True},
            status=KnowledgeItemStatus.ACTIVE,
        )
    )
    await db_session.flush()

    doc = await ProductSpecViewService().build(db_session, sample_project.id)
    assert len(doc["capabilities"]) == 1
    entry = doc["capabilities"][0]["features"][0]
    prov = entry["spec"]["provenance"]
    assert prov["kind"] == "brownfield"
    assert prov["confidence"] == "HIGH"
    assert prov["recovered_evidence"][0]["support_ref"] == "tests/test_cards.py::test_move_card"
    ac = entry["spec"]["acceptance_criteria"][0]
    assert ac["given"] == "a card on column A"
    assert entry["spec"]["known_gaps"][0]["statement"] == "Edge case unverified"
