import pytest
from core.domain.enums import SpecStatus
from core.planning.models import Architecture, ImplementationSpec
from sqlalchemy.exc import DBAPIError
from tests.fixtures.planning_harness import supportdesk_architecture_proposal

pytestmark = pytest.mark.persistence


@pytest.mark.asyncio
async def test_approved_architecture_immutable(db_session, operator_ctx) -> None:
    from core.domain.canonical_json import sha256_hex
    from core.domain.projects.models import Project

    project = Project(key="arch-immut", name="Arch")
    db_session.add(project)
    await db_session.flush()
    body = supportdesk_architecture_proposal().body.model_dump(mode="json")
    arch = Architecture(
        project_id=project.id,
        lineage_key="ARCH",
        version=1,
        status=SpecStatus.APPROVED,
        kind="BASELINE",
        body=body,
        content_hash=sha256_hex(body),
    )
    db_session.add(arch)
    await db_session.flush()
    arch.body = {"tampered": True}
    with pytest.raises(DBAPIError):
        await db_session.flush()


@pytest.mark.asyncio
async def test_approved_implementation_spec_immutable(db_session) -> None:
    from core.domain.canonical_json import sha256_hex
    from core.domain.projects.models import Project
    from core.product_model.models import Feature, FeatureSpec

    project = Project(key="impl-immut", name="Impl")
    db_session.add(project)
    await db_session.flush()
    from core.domain.enums import ModelOrigin

    feat = Feature(
        project_id=project.id,
        key="F1",
        name="F",
        description="d",
        origin=ModelOrigin.GREENFIELD,
    )
    db_session.add(feat)
    await db_session.flush()
    fs_body = {"summary": "s", "behavior": "b", "rules": []}
    fs = FeatureSpec(
        project_id=project.id,
        feature_id=feat.id,
        lineage_key="SPEC-F1",
        version=1,
        status=SpecStatus.APPROVED,
        body=fs_body,
        content_hash=sha256_hex(fs_body),
    )
    db_session.add(fs)
    await db_session.flush()
    arch_body = supportdesk_architecture_proposal().body.model_dump(mode="json")
    arch = Architecture(
        project_id=project.id,
        lineage_key="ARCH",
        version=1,
        status=SpecStatus.APPROVED,
        kind="BASELINE",
        body=arch_body,
        content_hash=sha256_hex(arch_body),
    )
    db_session.add(arch)
    await db_session.flush()
    impl_body = {"summary": "i", "components": ["api"], "file_scope": ["app/api/**"]}
    impl = ImplementationSpec(
        project_id=project.id,
        lineage_key="SPEC-IMPL-F1",
        version=1,
        status=SpecStatus.APPROVED,
        kind="FEATURE",
        feature_spec_id=fs.id,
        architecture_id=arch.id,
        body=impl_body,
        content_hash=sha256_hex(impl_body),
    )
    db_session.add(impl)
    await db_session.flush()
    impl.body = {"tampered": True}
    with pytest.raises(DBAPIError):
        await db_session.flush()
