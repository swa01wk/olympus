from __future__ import annotations

import pytest
from core.planning.schemas import ImplementationSpecBody, TaskDraft, TaskPlan
from core.planning.task_plans.validation import TaskPlanValidator, task_file_scope


def _body(scope: list[str]) -> ImplementationSpecBody:
    return ImplementationSpecBody.model_construct(file_scope=scope)


def _task(allowed: list[str], refs: list[str]) -> TaskDraft:
    return TaskDraft.model_construct(
        ref="T1",
        title="t",
        objective="o",
        implementation_spec_ref="SPEC-A",
        requirement_refs=refs,
        ac_refs=[],
        allowed_scope=allowed,
        constraints=[],
        verification_requirements=["tests"],
        required_outputs=["candidate_commit", "changed_files", "test_results"],
        estimated_size="M",
        work_type="CODE_CHANGE",
    )


SPECS = {"SPEC-A": _body(["app/api/**"]), "SPEC-B": _body(["app/main.py", "app/repos/**"])}


def _errors(task: TaskDraft) -> list[str]:
    plan = TaskPlan.model_construct(tasks=[task], dependencies=[], risks=[], open_questions=[])
    return TaskPlanValidator().validate(plan, SPECS, set()).errors


@pytest.mark.unit
def test_task_may_use_file_scope_of_other_listed_specs() -> None:
    task = _task(["app/api/**", "app/main.py", "app/repos/**"], ["SPEC-B", "REQ-9"])
    assert task_file_scope(task, SPECS) == ["app/api/**", "app/main.py", "app/repos/**"]
    assert _errors(task) == []


@pytest.mark.unit
def test_task_still_rejected_outside_its_listed_specs() -> None:
    assert any("exceeds" in e for e in _errors(_task(["app/main.py"], [])))
    assert any("exceeds" in e for e in _errors(_task(["app/api/**", "secrets/**"], ["SPEC-B"])))


def _plan(refs: list[str], deps: list[tuple[str, str]]) -> TaskPlan:
    from core.planning.schemas import DependencyDraft

    return TaskPlan.model_construct(
        tasks=[_task([], []).model_copy(update={"ref": r}) for r in refs],
        dependencies=[
            DependencyDraft.model_construct(task_ref=t, depends_on_ref=d) for t, d in deps
        ],
        risks=[],
        open_questions=[],
    )


@pytest.mark.unit
def test_stacked_dependencies_chain_tasks_after_their_declared_deps() -> None:
    from core.planning.task_plans.validation import stacked_dependencies

    # T1 depends on T3, so the chain runs T2 -> T3 -> T1 (plan order breaks ties).
    edges = stacked_dependencies(_plan(["T1", "T2", "T3"], [("T1", "T3")]))
    assert edges == [("T1", "T3"), ("T3", "T2")]
    assert stacked_dependencies(_plan(["T1"], [])) == []
    assert stacked_dependencies(_plan(["A", "B", "C"], [])) == [("B", "A"), ("C", "B")]
