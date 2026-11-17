from __future__ import annotations

from collections import defaultdict, deque

from core.planning.glob_scope import scope_contains
from core.planning.schemas import ImplementationSpecBody, PlanValidationReport, TaskDraft, TaskPlan

_REQUIRED_OUTPUTS = {"candidate_commit", "changed_files", "test_results"}


def task_file_scope(
    task: TaskDraft, specs_by_lineage: dict[str, ImplementationSpecBody]
) -> list[str]:
    """Files a task may touch: its primary spec's file_scope plus those of any other approved
    implementation specs it lists in requirement_refs (planners group several features per task)."""
    scope: list[str] = []
    for key in [task.implementation_spec_ref, *task.requirement_refs]:
        body = specs_by_lineage.get(key)
        if body is None:
            continue
        scope.extend(p for p in body.file_scope if p not in scope)
    return scope


def stacked_dependencies(plan: TaskPlan) -> list[tuple[str, str]]:
    """The plan's dependencies plus a chain through every task, as (task_ref, depends_on_ref).

    Tasks are ordered so each comes after its declared dependencies (ties keep plan order),
    then each task also depends on the one before it. A task's base is then the previous
    task's candidate commit, which already contains all earlier work, so tasks build on each
    other instead of branching from the same commit and conflicting at integration. Assumes
    the plan is acyclic (the validator rejects cycles).
    """
    refs = [t.ref for t in plan.tasks]
    declared = [(d.task_ref, d.depends_on_ref) for d in plan.dependencies]
    waiting_on: dict[str, set[str]] = {r: set() for r in refs}
    for task_ref, dep_ref in declared:
        if task_ref in waiting_on and dep_ref in waiting_on:
            waiting_on[task_ref].add(dep_ref)
    order: list[str] = []
    while len(order) < len(refs):
        ready = next((r for r in refs if r not in order and waiting_on[r] <= set(order)), None)
        if ready is None:  # cycle: leave the declared edges alone
            return declared
        order.append(ready)
    edges = list(declared)
    for prev, ref in zip(order, order[1:], strict=False):
        if (ref, prev) not in edges:
            edges.append((ref, prev))
    return edges


class TaskPlanValidator:
    def validate(
        self,
        plan: TaskPlan,
        specs_by_lineage: dict[str, ImplementationSpecBody],
        mandatory_ac_keys: set[str],
        *,
        max_tasks: int = 12,
    ) -> PlanValidationReport:
        errors: list[str] = []
        refs = [t.ref for t in plan.tasks]
        if len(refs) != len(set(refs)):
            errors.append("duplicate task refs")

        spec_keys = set(specs_by_lineage.keys())
        task_by_ref = {t.ref: t for t in plan.tasks}
        for task in plan.tasks:
            if task.implementation_spec_ref not in spec_keys:
                errors.append(f"unknown implementation_spec_ref: {task.implementation_spec_ref}")
                continue
            if not scope_contains(task_file_scope(task, specs_by_lineage), task.allowed_scope):
                errors.append(f"task {task.ref} allowed_scope exceeds implementation file_scope")
            missing_out = _REQUIRED_OUTPUTS - set(task.required_outputs)
            if missing_out:
                errors.append(f"task {task.ref} missing required_outputs: {sorted(missing_out)}")
            if not task.verification_requirements:
                errors.append(f"task {task.ref} verification_requirements empty")

        for dep in plan.dependencies:
            if dep.task_ref not in task_by_ref or dep.depends_on_ref not in task_by_ref:
                errors.append(f"unknown dependency refs: {dep.task_ref} -> {dep.depends_on_ref}")

        if len(plan.tasks) > max_tasks:
            errors.append(f"too many tasks: {len(plan.tasks)} > {max_tasks}")

        if _has_cycle(plan):
            errors.append("dependency cycle detected")

        covered: set[str] = set()
        for task in plan.tasks:
            covered.update(task.ac_refs)
        missing_ac = mandatory_ac_keys - covered
        if missing_ac:
            errors.append(f"mandatory AC not covered: {sorted(missing_ac)}")

        for q in plan.open_questions:
            if q.blocking:
                errors.append(f"blocking open question: {q.question}")

        return PlanValidationReport(ok=not errors, errors=errors)


def _has_cycle(plan: TaskPlan) -> bool:
    graph: dict[str, list[str]] = defaultdict(list)
    nodes: set[str] = set()
    for t in plan.tasks:
        nodes.add(t.ref)
    for dep in plan.dependencies:
        graph[dep.task_ref].append(dep.depends_on_ref)
        nodes.add(dep.task_ref)
        nodes.add(dep.depends_on_ref)
    indegree = {n: 0 for n in nodes}
    for _src, targets in graph.items():
        for tgt in targets:
            indegree[tgt] = indegree.get(tgt, 0) + 1
    queue: deque[str] = deque([n for n, d in indegree.items() if d == 0])
    seen = 0
    while queue:
        n = queue.popleft()
        seen += 1
        for tgt in graph.get(n, []):
            indegree[tgt] -= 1
            if indegree[tgt] == 0:
                queue.append(tgt)
    return seen != len(nodes)
