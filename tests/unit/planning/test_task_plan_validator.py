import pytest
from core.planning.schemas import DependencyDraft, ImplementationSpecBody, TaskDraft, TaskPlan
from core.planning.task_plans.validation import TaskPlanValidator
from tests.fixtures.planning_harness import minimal_task_plan

pytestmark = pytest.mark.unit


def test_task_plan_ac_coverage_and_cycle() -> None:
    plan = minimal_task_plan()
    specs = {
        "SPEC-IMPL-FEAT-1": ImplementationSpecBody(
            summary="s",
            components=["api"],
            file_scope=["app/api/**", "tests/**"],
        )
    }
    report = TaskPlanValidator().validate(plan, specs, {"AC-1"})
    assert report.ok


def test_task_plan_rejects_cycle() -> None:
    plan = TaskPlan(
        tasks=[
            TaskDraft(
                ref="A",
                title="a",
                objective="a",
                implementation_spec_ref="SPEC-IMPL-FEAT-1",
                ac_refs=["AC-1"],
                allowed_scope=["app/api/**"],
                required_outputs=["candidate_commit", "changed_files", "test_results"],
                verification_requirements=["v"],
                estimated_size="S",
            ),
            TaskDraft(
                ref="B",
                title="b",
                objective="b",
                implementation_spec_ref="SPEC-IMPL-FEAT-1",
                ac_refs=["AC-1"],
                allowed_scope=["app/api/**"],
                required_outputs=["candidate_commit", "changed_files", "test_results"],
                verification_requirements=["v"],
                estimated_size="S",
            ),
        ],
        dependencies=[
            DependencyDraft(task_ref="A", depends_on_ref="B", reason="r"),
            DependencyDraft(task_ref="B", depends_on_ref="A", reason="r"),
        ],
    )
    specs = {
        "SPEC-IMPL-FEAT-1": ImplementationSpecBody(
            summary="s", components=["api"], file_scope=["app/api/**"]
        )
    }
    report = TaskPlanValidator().validate(plan, specs, {"AC-1"})
    assert not report.ok
