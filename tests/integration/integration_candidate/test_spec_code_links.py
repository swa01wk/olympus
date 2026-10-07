from __future__ import annotations

import pytest
from core.integration.enums import ICStatus, SpecCodeLinkOrigin, SpecCodeLinkRelation
from core.intelligence.code_index.enums import EntityType
from core.intelligence.code_index.parsers.imports import entity_key_for_qn
from core.traceability.models import SpecCodeLink
from sqlalchemy import select
from tests.fixtures.integration_harness import (
    add_implementation_code_task,
    attach_product_lineage,
    commit_files_in_worktree,
    create_and_run_integration,
    seed_integration_fixture,
)

pytestmark = [pytest.mark.integration, pytest.mark.git]

TEST_PATH = "tests/test_ac_one.py"
TEST_QN = "tests.test_ac_one.test_ac_one"


@pytest.mark.asyncio
async def test_generated_lineage_implement_and_verifies_links(
    db_session,
    system_ctx,
) -> None:
    fixture = await seed_integration_fixture(db_session, system_ctx, project_key="ic-links")
    bundle = await add_implementation_code_task(
        db_session,
        system_ctx,
        fixture,
        title="Implement with lineage",
        key_prefix="lnk1",
    )
    lineage = await attach_product_lineage(db_session, fixture, bundle.task)
    test_ref = entity_key_for_qn(EntityType.TEST.value, TEST_PATH, TEST_QN)
    impl_output = {
        "summary": "done",
        "changed_files": ["src/ticket.py", TEST_PATH],
        "tests_added_or_changed": [TEST_PATH],
        "test_commands_run": ["pytest -q"],
        "principal_symbols": ["create_ticket"],
        "ac_test_mapping": [{"ac_ref": lineage.ac_lineage_key, "test_ref": test_ref}],
        "notes": [],
        "open_questions": [],
    }
    await commit_files_in_worktree(
        db_session,
        system_ctx,
        bundle,
        {
            "src/ticket.py": (
                "def create_ticket():\n    return 1\n\ndef _private():\n    return 0\n"
            ),
            TEST_PATH: "def test_ac_one():\n    assert True\n",
        },
        principal_symbols=["create_ticket"],
        implementation_result=impl_output,
    )

    ic = await create_and_run_integration(db_session, system_ctx, fixture.cycle.id)
    assert ic.status == ICStatus.READY

    links = (
        (
            await db_session.execute(
                select(SpecCodeLink).where(
                    SpecCodeLink.repository_id == fixture.repository.id,
                    SpecCodeLink.origin == SpecCodeLinkOrigin.GENERATED_LINEAGE,
                )
            )
        )
        .scalars()
        .all()
    )
    assert links
    implements = [link for link in links if link.relation == SpecCodeLinkRelation.IMPLEMENTS]
    verifies = [link for link in links if link.relation == SpecCodeLinkRelation.VERIFIES]
    assert implements
    assert verifies
    for link in implements + verifies:
        assert link.confidence == 1.0
        assert link.task_id == bundle.task.id
        assert link.execution_id == bundle.execution_bundle.execution.id
        assert link.commit_sha is not None
    code_keys = {link.code_stable_key for link in implements}
    assert any("create_ticket" in key or "ticket" in key for key in code_keys)
    assert verifies[0].spec_type == "ACCEPTANCE_CRITERION"
    assert verifies[0].spec_id == lineage.ac_id
    assert all("_private" not in link.code_stable_key for link in implements)
