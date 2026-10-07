"""Assurance bootstrap when IC becomes READY (Phase 09 §14)."""

from __future__ import annotations

import pytest
from core.assurance.enums import GateStatus, GateType
from core.assurance.models import Evidence, Gate, VerificationObligation
from core.integration.enums import ICStatus
from core.intelligence.code_index.enums import EntityType
from core.intelligence.code_index.parsers.imports import entity_key_for_qn
from sqlalchemy import select
from tests.fixtures.integration_harness import (
    add_implementation_code_task,
    attach_product_lineage,
    commit_files_in_worktree,
    create_and_run_integration,
    seed_integration_fixture,
)

pytestmark = [pytest.mark.integration, pytest.mark.git]

TEST_PATH = "tests/test_ac_assurance.py"
TEST_QN = "tests.test_ac_assurance.test_ac_assurance"


@pytest.mark.asyncio
async def test_ready_ic_derives_obligations_gates_and_sha_bound_evidence(
    db_session,
    system_ctx,
) -> None:
    fixture = await seed_integration_fixture(db_session, system_ctx, project_key="asr")
    bundle = await add_implementation_code_task(
        db_session,
        system_ctx,
        fixture,
        title="Assurance bootstrap",
        key_prefix="asr1",
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
            "src/ticket.py": "def create_ticket():\n    return 1\n",
            TEST_PATH: "def test_ac_assurance():\n    assert True\n",
        },
        principal_symbols=["create_ticket"],
        implementation_result=impl_output,
    )
    ic = await create_and_run_integration(db_session, system_ctx, fixture.cycle.id)
    assert ic.status == ICStatus.READY
    assert ic.integrated_sha is not None

    obligations = (
        (
            await db_session.execute(
                select(VerificationObligation).where(
                    VerificationObligation.integration_candidate_id == ic.id
                )
            )
        )
        .scalars()
        .all()
    )
    assert obligations
    assert any(o.subject_key == lineage.ac_lineage_key for o in obligations)

    gates = (
        (await db_session.execute(select(Gate).where(Gate.integration_candidate_id == ic.id)))
        .scalars()
        .all()
    )
    gate_types = {g.gate_type for g in gates}
    assert GateType.BASELINE in gate_types
    assert len(gates) == 4
    assert all(g.status == GateStatus.PENDING for g in gates)

    evidence = (
        (
            await db_session.execute(
                select(Evidence).where(Evidence.integration_candidate_id == ic.id)
            )
        )
        .scalars()
        .all()
    )
    assert evidence
    assert all(e.commit_sha == ic.integrated_sha for e in evidence)
