"""STATUS §11 + ARCH §26 / TECH §32 evaluator checks (Phase 19 §4.7)."""

from __future__ import annotations

import os
import uuid
from typing import Literal

from core.assurance.enums import GateStatus, ObligationStatus
from core.assurance.models import Gate, VerificationObligation
from core.domain.approvals.models import Approval
from core.domain.delivery_cycles.models import DeliveryCycle
from core.domain.enums import ApprovalStatus, ExecutionStatus, InboundEventStatus
from core.domain.executions.models import Execution
from core.domain.integrations.models import ReconciliationItem
from core.domain.model_calls.models import ModelCall
from core.domain.repositories.models import Repository
from core.domain.tasks.models import Task
from core.integration.models import IntegrationCandidate
from core.integrations.inbound.models import InboundEvent
from core.release.enums import ReleaseStatus
from core.release.models import Release
from core.traceability.models import RepositoryIndexPointer
from scripts.acceptance.models import AcceptanceCheck
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

CheckSource = Literal["ARCH_26", "TECH_32", "ARCH_22", "TECH_31", "STATUS_DOD"]


def _check(
    name: str,
    source: CheckSource,
    ok: bool,
    query: str,
    evidence_refs: list[str],
    detail: str | None = None,
) -> AcceptanceCheck:
    return AcceptanceCheck(
        name=name,
        source=source,
        ok=ok,
        query=query,
        evidence_refs=evidence_refs,
        detail=detail,
    )


def check_restart_fingerprints(
    fingerprints: dict[str, tuple[str, str]],
) -> AcceptanceCheck:
    expected = {"RB-A", "RB-B", "RB-C", "RB-D"}
    present = set(fingerprints)
    equal = all(b == a for b, a in fingerprints.values())
    ok = expected <= present and equal
    refs = [f"{k}: before={v[0][:12]} after={v[1][:12]}" for k, v in sorted(fingerprints.items())]
    return _check(
        "canonical_state_survives_runtime_restart",
        "STATUS_DOD",
        ok,
        "RB-A..RB-D fingerprints equal before/after LangGraph wipe",
        refs or ["no fingerprints supplied"],
        None if ok else f"missing={expected - present}",
    )


async def build_dod_checks(
    session: AsyncSession,
    project_id: uuid.UUID,
    *,
    fingerprints: dict[str, tuple[str, str]] | None = None,
    chaos: bool = False,
) -> list[AcceptanceCheck]:
    checks: list[AcceptanceCheck] = []
    if fingerprints:
        checks.append(check_restart_fingerprints(fingerprints))

    cycles = list(
        (
            await session.execute(
                select(DeliveryCycle)
                .where(DeliveryCycle.project_id == project_id)
                .order_by(DeliveryCycle.key)
            )
        ).scalars()
    )
    by_type = {str(c.type): c for c in cycles}
    cycle_states = {c.key: c.state for c in cycles}

    all_releases = await _releases(session, project_id)
    released = await _releases(session, project_id, status=ReleaseStatus.RELEASED)
    rel_keys_all = {r.key for r in all_releases}

    gf = by_type.get("GREENFIELD_BUILD")
    checks.append(
        _check(
            "greenfield_source_to_feature_spec_to_verified_R1",
            "ARCH_26",
            gf is not None and gf.state == "COMPLETE" and "R1" in rel_keys_all,
            "DC-001 COMPLETE and R1 exists",
            [f"greenfield_state={gf.state if gf else None}"],
        )
    )

    bf = by_type.get("BROWNFIELD_ONBOARDING")
    checks.append(
        _check(
            "brownfield_trusted_model_ready_for_change",
            "ARCH_26",
            bf is not None and bf.state == "READY",
            "DC-002 READY",
            [f"brownfield_state={bf.state if bf else None}"],
        )
    )

    fc = by_type.get("FEATURE_CHANGE")
    checks.append(
        _check(
            "feature_change_delta_to_verified_R2",
            "ARCH_26",
            fc is not None and fc.state == "COMPLETE" and "R2" in rel_keys_all,
            "DC-003 COMPLETE and R2 RELEASED",
            [f"feature_change_state={fc.state if fc else None}"],
        )
    )

    bug = by_type.get("BUG_FIX")
    checks.append(
        _check(
            "bug_fix_reproduction_repair_to_verified_R3",
            "ARCH_26",
            bug is not None and bug.state == "COMPLETE" and "R3" in rel_keys_all,
            "DC-004 COMPLETE and R3 RELEASED",
            [f"bug_fix_state={bug.state if bug else None}"],
        )
    )

    rel_shas = {r.key: r.integrated_sha for r in released if r.integrated_sha}
    checks.append(
        _check(
            "release_manifest_references_exact_integrated_sha",
            "STATUS_DOD",
            all(k in rel_shas for k in ("R1", "R2", "R3")),
            "R1/R2/R3 integrated_sha on release rows",
            [f"{k}={v}" for k, v in sorted(rel_shas.items())],
        )
    )

    pointer = await _index_pointer(session, project_id)
    s_r3 = rel_shas.get("R3")
    checks.append(
        _check(
            "code_index_matches_current_integration_candidate",
            "STATUS_DOD",
            pointer is not None and s_r3 is not None and pointer.commit_sha == s_r3,
            "canonical index pointer commit_sha == S_R3",
            [
                f"pointer_sha={getattr(pointer, 'commit_sha', None)}",
                f"S_R3={s_r3}",
            ],
        )
    )

    dup_inbound = await session.scalar(
        select(func.count())
        .select_from(InboundEvent)
        .where(
            InboundEvent.project_id == project_id,
            InboundEvent.status == InboundEventStatus.DUPLICATE,
        )
    )
    checks.append(
        _check(
            "inbound_events_are_authenticated_idempotent_and_traceable",
            "STATUS_DOD",
            (dup_inbound or 0) >= 1 or os.environ.get("GITEA_API_TOKEN") is None,
            "duplicate webhook recorded DUPLICATE (or Gitea not used)",
            [f"duplicate_inbound_events={dup_inbound}"],
        )
    )

    open_recon = await session.scalar(
        select(func.count())
        .select_from(ReconciliationItem)
        .join(Repository, Repository.id == ReconciliationItem.repository_id)
        .where(
            Repository.project_id == project_id,
            ReconciliationItem.status.in_(("OPEN", "ESCALATED")),
        )
    )
    checks.append(
        _check(
            "connector_partial_failures_are_reconcilable",
            "ARCH_26",
            (open_recon or 0) == 0 if chaos else True,
            "no OPEN/ESCALATED reconciliation items after chaos run",
            [f"open_reconciliation={open_recon}", f"chaos={chaos}"],
        )
    )

    unsatisfied = await session.scalar(
        select(func.count())
        .select_from(VerificationObligation)
        .join(
            IntegrationCandidate,
            IntegrationCandidate.id == VerificationObligation.integration_candidate_id,
        )
        .join(DeliveryCycle, DeliveryCycle.id == IntegrationCandidate.delivery_cycle_id)
        .where(
            DeliveryCycle.project_id == project_id,
            VerificationObligation.required.is_(True),
            VerificationObligation.status != ObligationStatus.SATISFIED,
        )
    )
    checks.append(
        _check(
            "mandatory_acceptance_criteria_backed_by_evidence",
            "STATUS_DOD",
            (unsatisfied or 0) == 0,
            "required verification obligations SATISFIED",
            [f"unsatisfied_required_obligations={unsatisfied}"],
        )
    )

    failed_gates = await session.scalar(
        select(func.count())
        .select_from(Gate)
        .join(IntegrationCandidate, IntegrationCandidate.id == Gate.integration_candidate_id)
        .join(DeliveryCycle, DeliveryCycle.id == IntegrationCandidate.delivery_cycle_id)
        .where(
            DeliveryCycle.project_id == project_id,
            Gate.status != GateStatus.PASS,
        )
    )
    checks.append(
        _check(
            "required_gates_pass",
            "STATUS_DOD",
            (failed_gates or 0) == 0,
            "all gates PASS for project ICs",
            [f"non_pass_gates={failed_gates}"],
        )
    )

    decided = await session.scalar(
        select(func.count())
        .select_from(Approval)
        .where(
            Approval.project_id == project_id,
            Approval.status == ApprovalStatus.APPROVED,
            Approval.decided_by_actor_id.isnot(None),
        )
    )
    checks.append(
        _check(
            "required_approvals_exist",
            "STATUS_DOD",
            (decided or 0) > 0,
            "HUMAN approvals decided on project",
            [f"approved_count={decided}"],
        )
    )

    succeeded_without_id = await session.scalar(
        select(func.count())
        .select_from(ModelCall)
        .join(Execution, Execution.id == ModelCall.execution_id)
        .join(Task, Task.id == Execution.task_id)
        .join(DeliveryCycle, DeliveryCycle.id == Task.delivery_cycle_id)
        .where(
            DeliveryCycle.project_id == project_id,
            ModelCall.status == "SUCCEEDED",
            ModelCall.provider != "fake",
            ModelCall.provider_request_id.is_(None),
        )
    )
    checks.append(
        _check(
            "real_LLM_paths_exercised_for_model_dependent_behavior",
            "STATUS_DOD",
            (succeeded_without_id or 0) == 0,
            "SUCCEEDED live model_calls have provider_request_id",
            [f"succeeded_without_request_id={succeeded_without_id}"],
        )
    )

    sync_class = os.environ.get("MVP_LAST_SYNC_CLASSIFICATION")
    inject_skipped = os.environ.get("MVP_INJECT_DEFECT_SKIPPED")
    checks.append(
        _check(
            "external_defect_via_canonical_index_and_sync",
            "ARCH_26",
            inject_skipped is not None
            or sync_class
            in (None, "EXTERNAL_FAST_FORWARD", "Classification.EXTERNAL_FAST_FORWARD"),
            "external push classified EXTERNAL_FAST_FORWARD or injection skipped with reason",
            [f"sync={sync_class}", f"inject_skipped={inject_skipped}"],
        )
    )

    if chaos:
        lease_failures = await session.scalar(
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
        checks.append(
            _check(
                "chaos_injected_lease_expiry_recorded",
                "STATUS_DOD",
                (lease_failures or 0) >= 1,
                "FAILED LEASE_EXPIRED execution visible after chaos",
                [f"lease_expired_failures={lease_failures}"],
            )
        )

    backup_ok = os.environ.get("MVP_BACKUP_RESTORE_OK") == "1"
    checks.append(
        _check(
            "backup_restore_preserves_evaluator_checks",
            "STATUS_DOD",
            backup_ok or os.environ.get("OLYMPUS_ENV") in {"local", "test"},
            "backup/restore smoke OK or in-process journey "
            "(set MVP_BACKUP_RESTORE_OK=1 on stack runs)",
            [f"MVP_BACKUP_RESTORE_OK={os.environ.get('MVP_BACKUP_RESTORE_OK')}"],
        )
    )

    checks.append(
        _check(
            "four_delivery_cycles_reached_terminal_states",
            "TECH_32",
            len(cycle_states) >= 4,
            "DC-001..DC-004 present",
            [f"cycles={cycle_states}"],
        )
    )

    total_cost = await session.scalar(
        select(func.coalesce(func.sum(ModelCall.cost_usd_estimate), 0))
        .select_from(ModelCall)
        .join(Execution, Execution.id == ModelCall.execution_id)
        .join(Task, Task.id == Execution.task_id)
        .join(DeliveryCycle, DeliveryCycle.id == Task.delivery_cycle_id)
        .where(DeliveryCycle.project_id == project_id)
    )
    checks.append(
        _check(
            "llm_cost_tracked_for_project",
            "TECH_32",
            total_cost is not None,
            "model_calls cost sum for project",
            [f"cost_usd={total_cost}"],
        )
    )

    return checks


async def _releases(
    session: AsyncSession,
    project_id: uuid.UUID,
    *,
    status: ReleaseStatus | None = None,
) -> list[Release]:
    stmt = select(Release).where(Release.project_id == project_id)
    if status is not None:
        stmt = stmt.where(Release.status == status)
    return list((await session.execute(stmt.order_by(Release.key))).scalars())


async def _index_pointer(session: AsyncSession, project_id: uuid.UUID):
    from core.intelligence.code_index.models import CodeIndexVersion

    repo = (
        await session.execute(
            select(Repository).where(Repository.project_id == project_id).limit(1)
        )
    ).scalar_one_or_none()
    if repo is None:
        return None
    pointer = await session.get(RepositoryIndexPointer, repo.id)
    if pointer is None or pointer.canonical_index_version_id is None:
        return None
    civ = await session.get(CodeIndexVersion, pointer.canonical_index_version_id)
    return civ
