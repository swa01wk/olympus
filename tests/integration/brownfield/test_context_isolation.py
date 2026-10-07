from __future__ import annotations

import pytest
from core.domain.canonical_json import sha256_hex
from core.domain.enums import EntityStatus, ModelOrigin, SpecKind, SpecStatus
from core.intelligence.recovered_specs.context import ScoutContextBuilder
from core.planning.models import Architecture
from core.product_model.models import Capability, Feature, FeatureSpec
from tests.fixtures.brownfield_harness import brownfield_cycle_at_code_index

pytestmark = [pytest.mark.integration, pytest.mark.asyncio]


async def test_scout_manifest_excludes_canonical_product_model(db_session, system_ctx) -> None:
    cycle, _, _ = await brownfield_cycle_at_code_index(db_session, system_ctx)
    cap = Capability(
        project_id=cycle.project_id,
        key="CAP-ISO",
        name="Canonical cap",
        description="",
        status=EntityStatus.APPROVED,
        origin=ModelOrigin.GREENFIELD,
    )
    db_session.add(cap)
    await db_session.flush()
    feat = Feature(
        project_id=cycle.project_id,
        capability_id=cap.id,
        key="FEAT-ISO",
        name="Canonical feature",
        description="",
        status=EntityStatus.APPROVED,
        origin=ModelOrigin.GREENFIELD,
    )
    db_session.add(feat)
    await db_session.flush()
    body = {"summary": "canonical"}
    db_session.add(
        FeatureSpec(
            project_id=cycle.project_id,
            feature_id=feat.id,
            lineage_key="SPEC-FEAT-ISO",
            version=1,
            status=SpecStatus.APPROVED,
            spec_kind=SpecKind.CANONICAL,
            body=body,
            content_hash=sha256_hex(body),
        )
    )
    db_session.add(
        Architecture(
            project_id=cycle.project_id,
            version=1,
            status=SpecStatus.APPROVED,
            kind="CANONICAL",
            body=body,
            content_hash=sha256_hex(body),
        )
    )
    await db_session.flush()
    payload, _ = await ScoutContextBuilder().build(db_session, cycle.id)
    manifest = payload.get("manifest_refs") or []
    joined = "\n".join(manifest)
    assert "FEATURE_SPEC" not in joined
    assert "ARCHITECTURE" not in joined
    assert "IMPLEMENTATION_SPEC" not in joined
