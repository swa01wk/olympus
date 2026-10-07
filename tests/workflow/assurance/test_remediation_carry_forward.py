"""Phase 09 §12 workflow — superseding IC carries forward unchanged verification evidence."""

from __future__ import annotations

import pytest
from core.assurance.enums import GateStatus, GateType
from core.assurance.models import Evidence
from core.domain.enums import TaskOrigin
from core.integration.enums import ICStatus
from core.intelligence.code_index.enums import EntityType
from core.intelligence.code_index.parsers.imports import entity_key_for_qn
from sqlalchemy import select
from tests.fixtures.assurance_harness import (
    DEFAULT_TEST_PATH,
    DEFAULT_TEST_QN,
    add_warden_review_evidence,
    finalize_all_pending_gates,
    gate_by_type,
    human_finalize_ctx,
    patch_agentless_assurance,
    ready_ic_with_sentinel_evidence,
)
from tests.fixtures.integration_harness import (
    add_implementation_code_task,
    commit_files_in_worktree,
    create_and_run_integration,
)

pytestmark = [pytest.mark.workflow, pytest.mark.integration, pytest.mark.git]


@pytest.mark.asyncio
async def test_ic_ready_when_ac_test_fails_but_integration_pytest_scoped(
    db_session,
    system_ctx,
) -> None:
    """IC merge checks use `[tool.olympus].integration_pytest_args`, not full suite."""
    ic, _, _ = await ready_ic_with_sentinel_evidence(
        db_session, system_ctx, project_key="p9-ic-scope", passing=False
    )
    assert ic.status == ICStatus.READY
    assert ic.integrated_sha is not None


@pytest.mark.asyncio
async def test_remediation_second_ic_carries_forward_unchanged_evidence(
    db_session,
    system_ctx,
) -> None:
    ic1, lineage, fixture = await ready_ic_with_sentinel_evidence(
        db_session, system_ctx, project_key="p9-rem", passing=True
    )
    fin_ctx = await human_finalize_ctx(db_session)
    await finalize_all_pending_gates(db_session, ic1.id, fin_ctx)

    bundle = await add_implementation_code_task(
        db_session,
        system_ctx,
        fixture,
        title="Remediation fix",
        key_prefix="remfix",
        base_sha=ic1.integrated_sha,
    )
    bundle.task.origin = TaskOrigin.REMEDIATION
    test_ref = entity_key_for_qn(EntityType.TEST.value, DEFAULT_TEST_PATH, DEFAULT_TEST_QN)
    impl_output = {
        "summary": "fix",
        "changed_files": ["src/ticket.py", DEFAULT_TEST_PATH],
        "tests_added_or_changed": [DEFAULT_TEST_PATH],
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
            DEFAULT_TEST_PATH: "def test_ac_assurance():\n    assert True\n",
            "docs/remediation.txt": "remediation complete\n",
        },
        principal_symbols=["create_ticket"],
        implementation_result=impl_output,
    )

    with patch_agentless_assurance():
        ic2 = await create_and_run_integration(db_session, system_ctx, fixture.cycle.id)
    assert ic2.status == ICStatus.READY
    assert ic2.supersedes_id == ic1.id
    await db_session.refresh(ic1)
    assert ic1.status == ICStatus.SUPERSEDED

    from core.assurance.carry_forward import EvidenceCarryForwardService

    await EvidenceCarryForwardService().carry_from_superseded(db_session, ic2, ic1.id, system_ctx)

    carried = (
        (
            await db_session.execute(
                select(Evidence).where(
                    Evidence.integration_candidate_id == ic2.id,
                    Evidence.carried_forward_from_id.isnot(None),
                )
            )
        )
        .scalars()
        .all()
    )
    assert carried, "expected CARRIED_FORWARD evidence on superseding IC"
    prior_ids = {c.carried_forward_from_id for c in carried}
    ic1_evidence = (
        (
            await db_session.execute(
                select(Evidence.id).where(Evidence.integration_candidate_id == ic1.id)
            )
        )
        .scalars()
        .all()
    )
    assert prior_ids.intersection(set(ic1_evidence))

    await add_warden_review_evidence(db_session, ic2, system_ctx)
    with patch_agentless_assurance():
        from tests.fixtures.assurance_harness import _refresh_sentinel_plan_and_execute

        await _refresh_sentinel_plan_and_execute(db_session, system_ctx, ic2.id)
    gates = await finalize_all_pending_gates(db_session, ic2.id, fin_ctx)
    sentinel_gate = gate_by_type(gates, GateType.SENTINEL)
    assert sentinel_gate.status == GateStatus.PASS, sentinel_gate.reasons
