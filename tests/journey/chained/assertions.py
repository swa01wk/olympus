"""Cross-cycle assertions for chained MVP (Phase 19 §4.5)."""

from __future__ import annotations

import os
import uuid

from core.domain.delivery_cycles.models import DeliveryCycle
from core.domain.enums import (
    DeliveryCycleType,
    ExecutionStatus,
    InboundEventStatus,
    ProjectReadiness,
)
from core.domain.executions.models import Execution
from core.domain.model_calls.models import ModelCall
from core.domain.projects.models import Project
from core.domain.tasks.models import Task
from core.integration.models import IntegrationCandidate
from core.integrations.inbound.models import InboundEvent
from core.intelligence.recovered_specs.context import ScoutContextBuilder
from core.release.enums import ReleaseStatus
from core.release.models import Release
from core.traceability.lineage.factory import build_lineage_service
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from tests.journey.bug_fix_acceptance import assert_bug_fix_phase15_acceptance
from tests.journey.feature_change_acceptance import assert_feature_change_phase14_acceptance
from tests.journey.helpers import assert_live_llm_proof


async def assert_chained_terminal_state(session: AsyncSession, project_id: uuid.UUID) -> None:
    project = await session.get(Project, project_id)
    assert project is not None
    assert project.readiness_state == ProjectReadiness.READY_FOR_CHANGE

    cycles = (
        await session.execute(
            select(DeliveryCycle)
            .where(DeliveryCycle.project_id == project_id)
            .order_by(DeliveryCycle.key)
        )
    ).scalars()
    by_type = {str(c.type): c for c in cycles}
    assert by_type.get("GREENFIELD_BUILD") and by_type["GREENFIELD_BUILD"].state == "COMPLETE"
    bf = by_type.get("BROWNFIELD_ONBOARDING")
    assert bf and bf.state == "READY"
    assert by_type.get("FEATURE_CHANGE") and by_type["FEATURE_CHANGE"].state == "COMPLETE"
    assert by_type.get("BUG_FIX") and by_type["BUG_FIX"].state == "COMPLETE"

    releases = (
        await session.execute(
            select(Release).where(Release.project_id == project_id).order_by(Release.key)
        )
    ).scalars()
    rel_by_key = {r.key: r for r in releases}
    for key in ("R1", "R2", "R3"):
        assert rel_by_key.get(key) is not None
        assert rel_by_key[key].status == ReleaseStatus.RELEASED


async def assert_chained_llm_proof(session: AsyncSession, project_id: uuid.UUID) -> None:
    cycles = (
        await session.execute(select(DeliveryCycle).where(DeliveryCycle.project_id == project_id))
    ).scalars()
    stage_map = {
        "GREENFIELD_BUILD": (
            "product_decomposition",
            "architecture",
            "planning",
            "implementation",
            "review",
            "verification_planning",
        ),
        "BROWNFIELD_ONBOARDING": ("repository_reasoning", "verification_planning"),
        "FEATURE_CHANGE": (
            "product_decomposition",
            "planning",
            "implementation",
            "review",
            "verification_planning",
        ),
        "BUG_FIX": (
            "product_decomposition",
            "verification_planning",
            "review",
            "planning",
            "implementation",
        ),
    }
    for cycle in cycles:
        aliases = stage_map.get(str(cycle.type))
        if aliases:
            await assert_live_llm_proof(session, cycle.id, aliases)

    fake_count = (
        await session.execute(
            select(func.count()).select_from(ModelCall).where(ModelCall.provider == "fake")
        )
    ).scalar_one()
    assert fake_count == 0, "model_calls must not contain provider=fake in journey env"


def assert_restart_fingerprints_match(fingerprints: dict[str, tuple[str, str]]) -> None:
    for boundary in ("RB-A", "RB-B", "RB-C", "RB-D"):
        assert boundary in fingerprints, f"missing restart boundary {boundary}"
        before, after = fingerprints[boundary]
        assert before == after, f"{boundary} fingerprint changed: {before} != {after}"


async def _cycle_by_type(
    session: AsyncSession, project_id: uuid.UUID, cycle_type: DeliveryCycleType
) -> DeliveryCycle:
    cycle = (
        await session.execute(
            select(DeliveryCycle).where(
                DeliveryCycle.project_id == project_id,
                DeliveryCycle.type == cycle_type,
            )
        )
    ).scalar_one()
    return cycle


async def _ic_and_release(
    session: AsyncSession, cycle_id: uuid.UUID
) -> tuple[IntegrationCandidate, Release]:
    release = (
        await session.execute(
            select(Release)
            .where(Release.delivery_cycle_id == cycle_id)
            .order_by(Release.created_at.desc())
            .limit(1)
        )
    ).scalar_one()
    ic = await session.get(IntegrationCandidate, release.integration_candidate_id)
    assert ic is not None
    return ic, release


async def assert_brownfield_scout_isolation(session: AsyncSession, project_id: uuid.UUID) -> None:
    cycle = await _cycle_by_type(session, project_id, DeliveryCycleType.BROWNFIELD_ONBOARDING)
    payload, _ = await ScoutContextBuilder().build(session, cycle.id)
    manifest = payload.get("manifest_refs") or []
    joined = "\n".join(manifest)
    assert "FEATURE_SPEC" not in joined
    assert "ARCHITECTURE" not in joined
    assert "IMPLEMENTATION_SPEC" not in joined


async def assert_inbound_duplicate_recorded(session: AsyncSession, project_id: uuid.UUID) -> None:
    if not os.environ.get("GITEA_API_TOKEN"):
        return
    dup = await session.scalar(
        select(func.count())
        .select_from(InboundEvent)
        .where(
            InboundEvent.project_id == project_id,
            InboundEvent.status == InboundEventStatus.DUPLICATE,
        )
    )
    assert (dup or 0) >= 1, "expected DUPLICATE inbound event for redelivered webhook"


async def assert_chaos_failure_and_retry(session: AsyncSession, project_id: uuid.UUID) -> None:
    if os.environ.get("MVP_CHAOS") != "1":
        return
    lease_failed = await session.scalar(
        select(func.count())
        .select_from(Execution)
        .join(Task, Task.id == Execution.task_id)
        .join(DeliveryCycle, DeliveryCycle.id == Task.delivery_cycle_id)
        .where(
            DeliveryCycle.project_id == project_id,
            Execution.status == ExecutionStatus.FAILED,
            Execution.failure_class == "LEASE_EXPIRED",
        )
    )
    assert (lease_failed or 0) >= 1, "chaos run must record LEASE_EXPIRED failure"


async def assert_lineage_forward(session: AsyncSession, project_id: uuid.UUID) -> None:
    graph = await build_lineage_service().forward(session, "PROJECT", project_id)
    assert graph.nodes, "lineage forward from project should return nodes"


async def assert_release_shas_consistent(session: AsyncSession, project_id: uuid.UUID) -> None:
    releases = list(
        (
            await session.execute(
                select(Release).where(
                    Release.project_id == project_id,
                    Release.status == ReleaseStatus.RELEASED,
                )
            )
        ).scalars()
    )
    by_key = {r.key: r for r in releases}
    for key in ("R1", "R2", "R3"):
        assert key in by_key, f"missing release {key}"
        assert by_key[key].integrated_sha, f"{key} missing integrated_sha"


async def assert_chained_acceptance_criteria(
    session: AsyncSession,
    project_id: uuid.UUID,
    *,
    fingerprints: dict[str, tuple[str, str]],
) -> None:
    """Phase 19 §4.5 cross-cycle assertions (journey evidence)."""
    await assert_chained_terminal_state(session, project_id)
    if os.environ.get("MVP_SKIP_LLM_PROOF") != "1":
        await assert_chained_llm_proof(session, project_id)
    assert_restart_fingerprints_match(fingerprints)
    await assert_brownfield_scout_isolation(session, project_id)
    await assert_inbound_duplicate_recorded(session, project_id)
    await assert_chaos_failure_and_retry(session, project_id)
    await assert_lineage_forward(session, project_id)
    await assert_release_shas_consistent(session, project_id)

    fc = await _cycle_by_type(session, project_id, DeliveryCycleType.FEATURE_CHANGE)
    ic_fc, rel_fc = await _ic_and_release(session, fc.id)
    await assert_feature_change_phase14_acceptance(
        session,
        project_id=project_id,
        cycle_id=fc.id,
        ic=ic_fc,
        release=rel_fc,
    )

    bf = await _cycle_by_type(session, project_id, DeliveryCycleType.BUG_FIX)
    ic_bf, rel_bf = await _ic_and_release(session, bf.id)
    await assert_bug_fix_phase15_acceptance(
        session,
        project_id=project_id,
        cycle_id=bf.id,
        ic=ic_bf,
        release=rel_bf,
    )
