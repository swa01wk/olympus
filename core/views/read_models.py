"""Query-only read models for the operator dashboard."""

from __future__ import annotations

import uuid
from typing import Any

from core.commands.context import CommandContext
from core.domain.actions.models import ActionRequest
from core.domain.approvals.models import Approval
from core.domain.delivery_cycles.models import DeliveryCycle
from core.domain.enums import (
    ActionStatus,
    ApprovalStatus,
    ClarificationStatus,
    ExecutionStatus,
    TaskStatus,
)
from core.domain.executions.models import Clarification, Execution
from core.domain.projects.models import Project
from core.domain.repositories.models import Repository
from core.domain.tasks.models import Task, TaskDependency
from core.integration.models import IntegrationCandidate
from core.intelligence.code_index.models import CodeEntity, CodeIndexVersion
from core.intelligence.code_index.retrieval.structural import StructuralRetrieval
from core.release.models import Release
from core.repositories.service import RepositoryService
from core.state.preview import TransitionPreviewService, preview_to_api
from core.traceability.models import RepositoryIndexPointer
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession


async def build_project_overview(
    session: AsyncSession,
    project_id: uuid.UUID,
    ctx: CommandContext,
) -> dict[str, Any]:
    project = await session.get(Project, project_id)
    if project is None:
        raise ValueError("project not found")
    cycles = (
        (
            await session.execute(
                select(DeliveryCycle)
                .where(DeliveryCycle.project_id == project_id)
                .order_by(DeliveryCycle.created_at.desc())
            )
        )
        .scalars()
        .all()
    )
    active = next((c for c in cycles if c.closed_at is None), cycles[0] if cycles else None)
    repo = (
        await session.execute(
            select(Repository).where(Repository.project_id == project_id).limit(1)
        )
    ).scalar_one_or_none()
    release = None
    if active:
        release = (
            await session.execute(
                select(Release)
                .where(Release.delivery_cycle_id == active.id)
                .order_by(Release.created_at.desc())
                .limit(1)
            )
        ).scalar_one_or_none()
    blockers: list[dict[str, Any]] = []
    pending_approvals = (
        await session.execute(
            select(func.count())
            .select_from(Approval)
            .where(
                Approval.project_id == project_id,
                Approval.status == ApprovalStatus.PENDING,
            )
        )
    ).scalar_one()
    if pending_approvals:
        blockers.append({"kind": "PENDING_APPROVALS", "count": pending_approvals})
    open_clarifications = (
        await session.execute(
            select(func.count())
            .select_from(Clarification)
            .where(Clarification.status == ClarificationStatus.OPEN)
        )
    ).scalar_one()
    if open_clarifications:
        blockers.append({"kind": "OPEN_CLARIFICATIONS", "count": open_clarifications})
    running_executions = 0
    task_count = 0
    cycle_overview = None
    if active:
        task_count = (
            await session.execute(
                select(func.count()).select_from(Task).where(Task.delivery_cycle_id == active.id)
            )
        ).scalar_one()
        running_executions = (
            await session.execute(
                select(func.count())
                .select_from(Execution)
                .where(
                    Execution.delivery_cycle_id == active.id,
                    Execution.status == ExecutionStatus.STARTED,
                )
            )
        ).scalar_one()
        cycle_overview = await build_cycle_overview(session, active.id, ctx)
    return {
        "project_id": str(project_id),
        "project_key": project.key,
        "active_cycle_id": str(active.id) if active else None,
        "active_cycle_key": active.key if active else None,
        "active_cycle_state": active.state if active else None,
        "current_release_id": str(release.id) if release else None,
        "current_release_key": release.key if release else None,
        "repository_id": str(repo.id) if repo else None,
        "canonical_commit": repo.canonical_commit if repo else None,
        "released_commit": repo.released_commit if repo else None,
        "task_count": task_count,
        "running_executions": running_executions,
        "blockers": blockers,
        "cycle_overview": cycle_overview,
    }


async def build_cycle_overview(
    session: AsyncSession,
    cycle_id: uuid.UUID,
    ctx: CommandContext,
) -> dict[str, Any]:
    cycle = await session.get(DeliveryCycle, cycle_id)
    if cycle is None:
        raise ValueError("cycle not found")
    ic = (
        await session.execute(
            select(IntegrationCandidate)
            .where(IntegrationCandidate.delivery_cycle_id == cycle_id)
            .order_by(IntegrationCandidate.created_at.desc())
            .limit(1)
        )
    ).scalar_one_or_none()
    running_executions = (
        await session.execute(
            select(func.count())
            .select_from(Execution)
            .where(
                Execution.delivery_cycle_id == cycle_id,
                Execution.status == ExecutionStatus.STARTED,
            )
        )
    ).scalar_one()
    blocked_tasks = (
        await session.execute(
            select(func.count())
            .select_from(Task)
            .where(Task.delivery_cycle_id == cycle_id, Task.status == TaskStatus.BLOCKED)
        )
    ).scalar_one()
    pending_approvals = (
        await session.execute(
            select(func.count())
            .select_from(Approval)
            .where(
                Approval.delivery_cycle_id == cycle_id,
                Approval.status == ApprovalStatus.PENDING,
            )
        )
    ).scalar_one()
    next_transitions = [
        preview_to_api(p)
        for p in await TransitionPreviewService().preview_delivery_cycle(session, cycle, ctx)
    ]
    return {
        "delivery_cycle_id": str(cycle_id),
        "key": cycle.key,
        "state": cycle.state,
        "running_executions": running_executions,
        "blocked_tasks": blocked_tasks,
        "pending_approvals": pending_approvals,
        "integration_candidate_key": ic.key if ic else None,
        "next_transitions": next_transitions,
    }


async def build_repository_view(
    session: AsyncSession,
    project_id: uuid.UUID,
) -> dict[str, Any]:
    repo = (
        await session.execute(
            select(Repository).where(Repository.project_id == project_id).limit(1)
        )
    ).scalar_one_or_none()
    if repo is None:
        return {"project_id": str(project_id), "repository": None}
    view = await RepositoryService().get_view(session, repo.id)
    ws = None
    if view.workspace:
        ws = {
            "id": str(view.workspace.id),
            "workspace_type": view.workspace.workspace_type,
            "storage_backend": view.workspace.storage_backend,
            "logical_location": view.workspace.logical_location,
            "materialized_commit": view.workspace.materialized_commit,
            "state": view.workspace.state.value,
        }
    return {
        "project_id": str(project_id),
        "repository": {
            "id": str(view.id),
            "project_id": str(view.project_id),
            "name": view.name,
            "source_type": view.source_type.value,
            "provider": view.provider.value,
            "remote_url": view.remote_url,
            "default_branch": view.default_branch,
            "registered_sha": view.registered_sha,
            "canonical_commit": view.canonical_commit,
            "released_commit": view.released_commit,
            "status": view.status.value,
            "status_reason": view.status_reason,
            "credential_ref": view.credential_ref,
            "credential_status": view.credential_status,
            "workspace": ws,
        },
    }


async def build_task_dag_view(session: AsyncSession, cycle_id: uuid.UUID) -> dict[str, Any]:
    tasks = (
        (await session.execute(select(Task).where(Task.delivery_cycle_id == cycle_id)))
        .scalars()
        .all()
    )
    task_ids = [t.id for t in tasks]
    deps: list[TaskDependency] = []
    if task_ids:
        deps = list(
            (
                await session.execute(
                    select(TaskDependency).where(TaskDependency.task_id.in_(task_ids))
                )
            )
            .scalars()
            .all()
        )
    return {
        "nodes": [
            {
                "id": str(t.id),
                "key": t.key,
                "title": t.title,
                "status": t.status.value,
                "work_type": t.work_type.value,
            }
            for t in tasks
        ],
        "edges": [{"from": str(d.depends_on_task_id), "to": str(d.task_id)} for d in deps],
    }


async def build_entity_neighborhood_view(
    session: AsyncSession,
    stable_key: str,
    *,
    depth: int = 1,
    repository_id: uuid.UUID | None = None,
) -> dict[str, Any]:
    depth = min(max(depth, 1), 2)
    pointer = None
    if repository_id is not None:
        pointer = await session.get(RepositoryIndexPointer, repository_id)
    if pointer is None:
        row = (await session.execute(select(RepositoryIndexPointer).limit(1))).scalar_one_or_none()
        pointer = row
    if pointer is None or pointer.canonical_index_version_id is None:
        return {"stable_key": stable_key, "entities": [], "relations": []}
    entity = (
        await session.execute(
            select(CodeEntity).where(
                CodeEntity.index_version_id == pointer.canonical_index_version_id,
                CodeEntity.stable_key == stable_key,
            )
        )
    ).scalar_one_or_none()
    if entity is None:
        return {"stable_key": stable_key, "entities": [], "relations": []}
    hits = await StructuralRetrieval(session).neighbors(entity.id, None, "both", depth)
    entities: list[dict[str, Any]] = []
    relations: list[dict[str, Any]] = []
    seen: set[str] = {str(entity.id)}
    entities.append(
        {
            "id": str(entity.id),
            "stable_key": entity.stable_key,
            "qualified_name": entity.qualified_name,
            "type": entity.type.value,
            "file_path": entity.file_path,
        }
    )
    for hit in hits[:200]:
        eid = str(hit.entity_id)
        if eid not in seen:
            seen.add(eid)
            entity_row: CodeEntity | None = await session.get(CodeEntity, hit.entity_id)
            if entity_row is not None:
                entities.append(
                    {
                        "id": eid,
                        "stable_key": entity_row.stable_key,
                        "qualified_name": entity_row.qualified_name,
                        "type": entity_row.type.value,
                        "file_path": entity_row.file_path,
                    }
                )
        relations.append(
            {
                "entity_id": eid,
                "retrieval_source": hit.retrieval_source,
                "score": hit.score,
                "path": hit.path,
                "provenance": hit.provenance,
            }
        )
    canon_sha = None
    if pointer.canonical_index_version_id:
        version = await session.get(CodeIndexVersion, pointer.canonical_index_version_id)
        canon_sha = version.commit_sha if version else None
    return {
        "stable_key": stable_key,
        "canonical_index_version_id": str(pointer.canonical_index_version_id),
        "canonical_commit": canon_sha,
        "entities": entities,
        "relations": relations,
    }


async def build_ic_assurance_view(session: AsyncSession, ic_id: uuid.UUID) -> dict[str, Any]:
    from core.assurance.models import AcceptanceCoverage, Evidence, Gate, VerificationObligation

    gates = (
        (await session.execute(select(Gate).where(Gate.integration_candidate_id == ic_id)))
        .scalars()
        .all()
    )
    obligations = (
        (
            await session.execute(
                select(VerificationObligation).where(
                    VerificationObligation.integration_candidate_id == ic_id
                )
            )
        )
        .scalars()
        .all()
    )
    obligation_ids = [o.id for o in obligations]
    evidence: list[Evidence] = []
    coverage: list[AcceptanceCoverage] = []
    if obligation_ids:
        evidence = list(
            (
                await session.execute(
                    select(Evidence).where(Evidence.obligation_id.in_(obligation_ids))
                )
            )
            .scalars()
            .all()
        )
        coverage = list(
            (
                await session.execute(
                    select(AcceptanceCoverage).where(
                        AcceptanceCoverage.obligation_id.in_(obligation_ids)
                    )
                )
            )
            .scalars()
            .all()
        )
    return {
        "integration_candidate_id": str(ic_id),
        "gates": [
            {
                "id": str(g.id),
                "key": g.key,
                "gate_type": g.gate_type.value,
                "status": g.status.value,
                "reasons": list(g.reasons or []),
            }
            for g in gates
        ],
        "obligations": [
            {
                "id": str(o.id),
                "subject_key": o.subject_key,
                "reason": o.reason.value,
                "status": o.status.value,
            }
            for o in obligations
        ],
        "evidence": [
            {
                "id": str(e.id),
                "key": e.key,
                "type": e.evidence_type.value,
                "commit_sha": e.commit_sha,
                "result": e.result.value,
            }
            for e in evidence
        ],
        "coverage": [
            {
                "id": str(c.id),
                "obligation_id": str(c.obligation_id),
                "evidence_id": str(c.evidence_id),
                "satisfied": c.satisfied,
            }
            for c in coverage
        ],
    }


async def build_inbox_view(
    session: AsyncSession,
    ctx: CommandContext,
    *,
    project_id: uuid.UUID | None = None,
    delivery_cycle_id: uuid.UUID | None = None,
) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    approval_filters = [Approval.status == ApprovalStatus.PENDING]
    if delivery_cycle_id is not None:
        approval_filters.append(Approval.delivery_cycle_id == delivery_cycle_id)
    elif project_id is not None:
        approval_filters.append(Approval.project_id == project_id)
    approvals = (
        (
            await session.execute(
                select(Approval).where(*approval_filters).order_by(Approval.created_at)
            )
        )
        .scalars()
        .all()
    )
    for a in approvals:
        items.append(
            {
                "kind": "APPROVAL",
                "id": str(a.id),
                "title": f"{a.approval_type.value} {a.key}",
                "why": "Human approval required",
                "project_id": str(a.project_id),
                "delivery_cycle_id": str(a.delivery_cycle_id) if a.delivery_cycle_id else None,
                "approval": {
                    "id": str(a.id),
                    "key": a.key,
                    "approval_type": a.approval_type.value,
                    "subject_type": a.subject_type,
                    "subject_id": str(a.subject_id),
                    "subject_hash": a.subject_hash,
                    "status": a.status.value,
                },
            }
        )
    clarification_filters = [Clarification.status == ClarificationStatus.OPEN]
    if delivery_cycle_id is not None:
        clarification_filters.append(Clarification.delivery_cycle_id == delivery_cycle_id)
    elif project_id is not None:
        clarification_filters.append(Clarification.project_id == project_id)
    clarifications = (
        (await session.execute(select(Clarification).where(*clarification_filters))).scalars().all()
    )
    for c in clarifications:
        items.append(
            {
                "kind": "CLARIFICATION",
                "id": str(c.id),
                "title": c.key,
                "why": c.question,
                "clarification": {
                    "id": str(c.id),
                    "key": c.key,
                    "question": c.question,
                    "status": c.status.value,
                },
            }
        )
    _ = ctx  # reserved for role-filtered views later
    return items


async def build_project_coverage_view(
    session: AsyncSession, project_id: uuid.UUID
) -> dict[str, Any]:
    from core.assurance.models import AcceptanceCoverage, VerificationObligation
    from core.product_model.models import AcceptanceCriterion, FeatureSpec

    specs = (
        (await session.execute(select(FeatureSpec).where(FeatureSpec.project_id == project_id)))
        .scalars()
        .all()
    )
    acs = (
        (
            await session.execute(
                select(AcceptanceCriterion)
                .join(FeatureSpec, FeatureSpec.id == AcceptanceCriterion.feature_spec_id)
                .where(FeatureSpec.project_id == project_id)
            )
        )
        .scalars()
        .all()
    )
    ac_total = len(acs)
    satisfied_rows = (
        await session.execute(
            select(func.count())
            .select_from(AcceptanceCoverage)
            .join(
                VerificationObligation,
                VerificationObligation.id == AcceptanceCoverage.obligation_id,
            )
            .join(DeliveryCycle, DeliveryCycle.id == VerificationObligation.delivery_cycle_id)
            .where(DeliveryCycle.project_id == project_id, AcceptanceCoverage.satisfied.is_(True))
        )
    ).scalar_one()
    obligations = (
        await session.execute(
            select(func.count())
            .select_from(VerificationObligation)
            .join(DeliveryCycle, DeliveryCycle.id == VerificationObligation.delivery_cycle_id)
            .where(DeliveryCycle.project_id == project_id)
        )
    ).scalar_one()
    return {
        "project_id": str(project_id),
        "feature_spec_count": len(specs),
        "acceptance_criterion_count": ac_total,
        "acceptance_criteria_with_evidence_pct": (100.0 * satisfied_rows / ac_total)
        if ac_total
        else 0.0,
        "verification_obligations": obligations,
    }


async def build_control_plane_view(
    session: AsyncSession,
    cycle_id: uuid.UUID,
    ctx: CommandContext,
) -> dict[str, Any]:
    from core.assurance.enums import GateStatus, GateType
    from core.assurance.models import Gate
    from core.release.eligibility import ReleaseEligibilityService

    cycle = await session.get(DeliveryCycle, cycle_id)
    if cycle is None:
        raise ValueError("cycle not found")
    blocked_tasks = (
        await session.execute(
            select(func.count())
            .select_from(Task)
            .where(Task.delivery_cycle_id == cycle_id, Task.status == TaskStatus.BLOCKED)
        )
    ).scalar_one()
    queued_tasks = (
        await session.execute(
            select(func.count())
            .select_from(Task)
            .where(
                Task.delivery_cycle_id == cycle_id,
                Task.status.in_([TaskStatus.READY, TaskStatus.QUEUED]),
            )
        )
    ).scalar_one()
    running_executions = (
        await session.execute(
            select(func.count())
            .select_from(Execution)
            .where(
                Execution.delivery_cycle_id == cycle_id,
                Execution.status == ExecutionStatus.STARTED,
            )
        )
    ).scalar_one()
    denied_actions = (
        await session.execute(
            select(func.count())
            .select_from(ActionRequest)
            .join(Execution, Execution.id == ActionRequest.execution_id)
            .where(
                Execution.delivery_cycle_id == cycle_id,
                ActionRequest.status == ActionStatus.DENIED,
            )
        )
    ).scalar_one()
    ic = (
        await session.execute(
            select(IntegrationCandidate)
            .where(IntegrationCandidate.delivery_cycle_id == cycle_id)
            .order_by(IntegrationCandidate.created_at.desc())
            .limit(1)
        )
    ).scalar_one_or_none()
    sentinel_fail = False
    if ic is not None:
        sentinel_fail = (
            await session.execute(
                select(func.count())
                .select_from(Gate)
                .where(
                    Gate.integration_candidate_id == ic.id,
                    Gate.gate_type == GateType.SENTINEL,
                    Gate.status == GateStatus.FAIL,
                )
            )
        ).scalar_one() > 0
    release_row = (
        await session.execute(
            select(Release)
            .where(Release.delivery_cycle_id == cycle_id)
            .order_by(Release.created_at.desc())
            .limit(1)
        )
    ).scalar_one_or_none()
    eligible: bool | None = None
    try:
        eligible, _ = await ReleaseEligibilityService().evaluate(
            session, cycle, release=release_row
        )
    except Exception:
        eligible = None
    _ = ctx
    return {
        "delivery_cycle_id": str(cycle_id),
        "scheduler": {"queued_tasks": queued_tasks, "blocked_tasks": blocked_tasks},
        "execution_manager": {"running": running_executions},
        "policy": {"denied_actions": denied_actions},
        "integration": {"active_ic": ic.key if ic else None},
        "assurance": {"sentinel_fail": sentinel_fail},
        "release": {"eligible": eligible},
    }


async def build_agent_activity_view(
    session: AsyncSession,
    project_id: uuid.UUID,
) -> dict[str, Any]:
    cycles = (
        (
            await session.execute(
                select(DeliveryCycle.id).where(DeliveryCycle.project_id == project_id)
            )
        )
        .scalars()
        .all()
    )
    if not cycles:
        return {"project_id": str(project_id), "profiles": []}
    cycle_ids = list(cycles)
    executions = (
        (
            await session.execute(
                select(Execution)
                .where(Execution.delivery_cycle_id.in_(cycle_ids))
                .order_by(Execution.created_at.desc())
                .limit(50)
            )
        )
        .scalars()
        .all()
    )
    by_profile: dict[str, list[dict[str, Any]]] = {}
    for ex in executions:
        profile = ex.agent_profile or "unknown"
        by_profile.setdefault(profile, []).append(
            {
                "execution_id": str(ex.id),
                "delivery_cycle_id": str(ex.delivery_cycle_id),
                "status": ex.status.value,
                "executor_kind": ex.executor_kind,
                "updated_at": ex.created_at.isoformat() if ex.created_at else None,
            }
        )
    profiles = [
        {
            "agent_profile": profile,
            "active_executions": [e for e in rows if e["status"] == "STARTED"],
            "recent_executions": rows[:10],
        }
        for profile, rows in sorted(by_profile.items())
    ]
    return {"project_id": str(project_id), "profiles": profiles}
