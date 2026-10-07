"""Fail-closed guard registry for delivery-cycle and repository transition edges."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from core.domain.delivery_cycles.models import DeliveryCycle
from core.domain.enums import RepositoryStatus, WorkspaceState
from core.domain.repositories.models import Repository, RepositoryWorkspace
from core.state.machines import DELIVERY_CYCLE_MACHINES

GuardCallable = Callable[[AsyncSession, Any, Any], Awaitable["GuardResult"]]


@dataclass(frozen=True)
class GuardResult:
    ok: bool
    reasons: tuple[str, ...] = ()


class GuardRegistry:
    def __init__(self) -> None:
        self._guards: dict[str, GuardCallable] = {}
        self._overrides: dict[str, GuardCallable] = {}

    def register(self, guard_id: str, fn: GuardCallable) -> None:
        self._guards[guard_id] = fn

    def override(self, guard_id: str, fn: GuardCallable) -> None:
        """Test-only guard override."""
        self._overrides[guard_id] = fn

    def clear_overrides(self) -> None:
        self._overrides.clear()

    async def evaluate(
        self,
        guard_id: str,
        session: AsyncSession,
        row: Any,
        ctx: Any,
    ) -> GuardResult:
        fn = self._overrides.get(guard_id) or self._guards.get(guard_id)
        if fn is None:
            return GuardResult(ok=False, reasons=(f"GUARD_NOT_IMPLEMENTED:{guard_id}",))
        return await fn(session, row, ctx)


async def repository_ready_with_canonical_commit(
    session: AsyncSession,
    cycle: DeliveryCycle,
    _ctx: Any,
) -> GuardResult:
    if cycle.repository_id is None:
        return GuardResult(ok=False, reasons=("REPOSITORY_NOT_BOUND",))
    repo = await session.get(Repository, cycle.repository_id)
    if repo is None:
        return GuardResult(ok=False, reasons=("REPOSITORY_NOT_BOUND",))
    if repo.status != RepositoryStatus.READY:
        return GuardResult(ok=False, reasons=(f"REPOSITORY_NOT_READY:{repo.status}",))
    if repo.canonical_commit is None:
        return GuardResult(ok=False, reasons=("REPOSITORY_NOT_READY:MISSING_CANONICAL",))
    if repo.workspace_id is None:
        return GuardResult(ok=False, reasons=("WORKSPACE_NOT_READY:MISSING",))
    ws = await session.get(RepositoryWorkspace, repo.workspace_id)
    if ws is None or ws.state != WorkspaceState.READY:
        state = ws.state if ws else "MISSING"
        return GuardResult(ok=False, reasons=(f"WORKSPACE_NOT_READY:{state}",))
    return GuardResult(ok=True)


async def _placeholder(_session: AsyncSession, _row: Any, _ctx: Any) -> GuardResult:
    return GuardResult(ok=False, reasons=("GUARD_NOT_IMPLEMENTED:placeholder",))


def _collect_guard_ids() -> set[str]:
    ids: set[str] = set()
    for machine in DELIVERY_CYCLE_MACHINES.values():
        for edge in machine.edges.values():
            ids.update(edge.guards)
    return ids


def build_guard_registry() -> GuardRegistry:
    from core.assurance.guards import required_gates_pass
    from core.integration.guards import (
        all_code_tasks_completed,
        ic_ready_and_canonical_index_current,
        remediation_tasks_exist,
    )
    from core.intelligence.baselines.guards import (
        baseline_review_complete,
        readiness_assessment_ready,
        readiness_failed_remediable,
        remediation_integrated_and_reindexed,
    )
    from core.intelligence.impact.guards import (
        architecture_delta_resolved,
        impact_assessment_complete,
    )
    from core.intelligence.impact.spec_delta_guard import spec_delta_approved
    from core.intelligence.recovered_specs.guards import (
        canonical_repository_index_ready,
        recovery_proposal_persisted,
    )
    from core.planning.guards import (
        architecture_approved,
        implementation_specs_approved,
        task_plan_accepted_contracts_issued,
    )
    from core.product_model.changes.guards import change_request_linked, project_change_ready
    from core.product_model.defects.guards import (
        defect_triaged,
        expected_behavior_resolved,
        repair_spec_approved_contracts_issued,
        reproduction_and_regression_pass,
        reproduction_recorded,
    )
    from core.product_model.guards import product_source_ingested, scope_approved
    from core.release.guards import release_executed

    registry = GuardRegistry()
    registry.register("canonical_repository_index_ready", canonical_repository_index_ready)
    registry.register("recovery_proposal_persisted", recovery_proposal_persisted)
    registry.register("baseline_review_complete", baseline_review_complete)
    registry.register("readiness_failed_remediable", readiness_failed_remediable)
    registry.register("remediation_integrated_and_reindexed", remediation_integrated_and_reindexed)
    registry.register("readiness_assessment_ready", readiness_assessment_ready)
    registry.register("all_code_tasks_completed", all_code_tasks_completed)
    registry.register("ic_ready_and_canonical_index_current", ic_ready_and_canonical_index_current)
    registry.register("remediation_tasks_exist", remediation_tasks_exist)
    registry.register("required_gates_pass", required_gates_pass)
    registry.register(
        "repository_ready_with_canonical_commit", repository_ready_with_canonical_commit
    )
    registry.register("product_source_ingested", product_source_ingested)
    registry.register("scope_approved", scope_approved)
    registry.register("architecture_approved", architecture_approved)
    registry.register("implementation_specs_approved", implementation_specs_approved)
    registry.register("task_plan_accepted_contracts_issued", task_plan_accepted_contracts_issued)
    registry.register("release_executed", release_executed)
    registry.register("impact_assessment_complete", impact_assessment_complete)
    registry.register("architecture_delta_resolved", architecture_delta_resolved)
    registry.register("spec_delta_approved", spec_delta_approved)
    registry.register("change_request_linked", change_request_linked)
    registry.register("project_change_ready", project_change_ready)
    registry.register("defect_triaged", defect_triaged)
    registry.register("reproduction_recorded", reproduction_recorded)
    registry.register("expected_behavior_resolved", expected_behavior_resolved)
    registry.register(
        "repair_spec_approved_contracts_issued",
        repair_spec_approved_contracts_issued,
    )
    registry.register("reproduction_and_regression_pass", reproduction_and_regression_pass)
    for guard_id in _collect_guard_ids():
        if guard_id not in registry._guards:
            registry.register(guard_id, _make_placeholder(guard_id))
    return registry


def _make_placeholder(guard_id: str) -> GuardCallable:
    async def _fn(_session: AsyncSession, _row: Any, _ctx: Any) -> GuardResult:
        return GuardResult(ok=False, reasons=(f"GUARD_NOT_IMPLEMENTED:{guard_id}",))

    return _fn


guard_registry = build_guard_registry()
