from __future__ import annotations

import pytest
from core.integration.enums import ICStatus
from core.intelligence.code_index.enums import EntityType
from core.intelligence.code_index.models import CodeEntity
from core.intelligence.code_index.parsers.imports import entity_key_for_qn
from core.traceability.lineage.factory import build_lineage_service
from sqlalchemy import select
from tests.fixtures.integration_harness import (
    add_implementation_code_task,
    attach_product_lineage,
    commit_files_in_worktree,
    create_and_run_integration,
    seed_integration_fixture,
)

pytestmark = [pytest.mark.integration, pytest.mark.git]

TEST_PATH = "tests/test_lineage_ac.py"
TEST_QN = "tests.test_lineage_ac.test_lineage_ac"


@pytest.mark.asyncio
async def test_forward_and_reverse_lineage_fixture_paths(
    db_session,
    system_ctx,
) -> None:
    fixture = await seed_integration_fixture(db_session, system_ctx, project_key="ic-lineage")
    bundle = await add_implementation_code_task(
        db_session,
        system_ctx,
        fixture,
        title="Lineage task",
        key_prefix="lin1",
    )
    lineage = await attach_product_lineage(db_session, fixture, bundle.task)
    test_ref = entity_key_for_qn(EntityType.TEST.value, TEST_PATH, TEST_QN)
    await commit_files_in_worktree(
        db_session,
        system_ctx,
        bundle,
        {
            "src/lineage_fn.py": "def lineage_fn():\n    return 42\n",
            TEST_PATH: "def test_lineage_ac():\n    assert True\n",
        },
        principal_symbols=["lineage_fn"],
        implementation_result={
            "summary": "ok",
            "changed_files": ["src/lineage_fn.py", TEST_PATH],
            "tests_added_or_changed": [TEST_PATH],
            "test_commands_run": [],
            "principal_symbols": ["lineage_fn"],
            "ac_test_mapping": [{"ac_ref": lineage.ac_lineage_key, "test_ref": test_ref}],
            "notes": [],
            "open_questions": [],
        },
    )
    ic = await create_and_run_integration(db_session, system_ctx, fixture.cycle.id)
    assert ic.status == ICStatus.READY

    assert ic.canonical_index_version_id is not None
    entity = (
        await db_session.execute(
            select(CodeEntity).where(
                CodeEntity.index_version_id == ic.canonical_index_version_id,
                CodeEntity.file_path == "src/lineage_fn.py",
                CodeEntity.type == EntityType.FUNCTION,
                CodeEntity.qualified_name.endswith("lineage_fn"),
            )
        )
    ).scalar_one()

    svc = build_lineage_service()
    reverse = await svc.reverse(db_session, entity.id)
    reverse_types = {n.type for n in reverse.nodes}
    assert "CODE_ENTITY" in reverse_types
    assert "IMPLEMENTATION_SPEC" in reverse_types or "FEATURE_SPEC" in reverse_types
    assert "FEATURE" in reverse_types
    assert "CAPABILITY" in reverse_types
    assert "EXECUTION" in reverse_types

    forward = await svc.forward(db_session, "FEATURE", lineage.feature_id)
    forward_types = {n.type for n in forward.nodes}
    assert "FEATURE" in forward_types
    assert "FEATURE_SPEC" in forward_types
    assert "IMPLEMENTATION_SPEC" in forward_types
    assert "CODE_ENTITY" in forward_types
