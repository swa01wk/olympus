"""REPAIR ImplementationSpec validation (Phase 15)."""

from __future__ import annotations

from core.planning.schemas import ImplementationSpecBody, ImplementationSpecDraft, TaskPlan
from core.policy.policy_service import get_cached_policy_content


def _non_test_files(file_scope: list[str]) -> list[str]:
    out: list[str] = []
    for raw in file_scope:
        g = raw.strip().replace("\\", "/")
        if g.startswith("tests/olympus_repro"):
            continue
        if g.startswith("tests/") and "olympus_repro" not in g:
            continue
        out.append(g)
    return out


class RepairSpecValidator:
    def validate_implementation_spec(
        self, draft: ImplementationSpecDraft
    ) -> tuple[bool, list[str]]:
        policy = get_cached_policy_content().get("bugfix", {})
        max_files = int(policy.get("max_repair_files", 3))
        errors: list[str] = []
        body = draft.body
        repair_files = _non_test_files(body.file_scope)
        if len(repair_files) > max_files:
            errors.append(f"max_repair_files_exceeded:{len(repair_files)}>{max_files}")
        if not body.required_tests:
            errors.append("regression_test_required")
        has_regression = any(
            "regression" in t.description.lower() or "closed" in t.description.lower()
            for t in body.required_tests
        )
        if not has_regression:
            errors.append("regression_test_not_described")
        return not errors, errors

    def validate_task_plan(self, plan: TaskPlan) -> tuple[bool, list[str]]:
        errors: list[str] = []
        if not plan.tasks:
            errors.append("no_tasks")
        for task in plan.tasks:
            regression = any(
                "tests/" in o and "olympus_repro" not in o for o in task.required_outputs
            )
            if not regression:
                errors.append(f"regression_test_path_missing:{task.ref}")
        return not errors, errors

    def regression_test_path_from_body(self, body: ImplementationSpecBody) -> str | None:
        def _concrete_test_path(path: str) -> bool:
            g = path.strip().replace("\\", "/")
            return (
                g.startswith("tests/")
                and "olympus_repro" not in g
                and "*" not in g
                and "?" not in g
            )

        for entry in body.ac_coverage:
            for loc in entry.locations:
                if _concrete_test_path(loc):
                    return loc.strip().replace("\\", "/")
        for test in body.required_tests:
            for token in test.description.replace("`", " ").split():
                if _concrete_test_path(token):
                    return token.rstrip(".,;").replace("\\", "/")
        return None
