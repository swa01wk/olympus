from core.planning.schemas import (
    ImplementationSpecBody,
    ImplementationSpecDraft,
    TaskDraft,
    TaskPlan,
)
from core.product_model.defects.repair import RepairSpecValidator


def test_repair_spec_file_limit() -> None:
    body = ImplementationSpecBody(
        summary="fix",
        components=["svc"],
        file_scope=["app/a.py", "app/b.py", "app/c.py", "app/d.py"],
        required_tests=[
            {
                "kind": "api",
                "ac_keys": ["AC-X"],
                "description": "regression tests/test_x.py",
            }
        ],
    )
    ok, errors = RepairSpecValidator().validate_implementation_spec(
        ImplementationSpecDraft(body=body)
    )
    assert not ok
    assert any("max_repair_files" in e for e in errors)


def test_task_plan_requires_regression_output() -> None:
    plan = TaskPlan(
        tasks=[
            TaskDraft(
                ref="t1",
                title="fix",
                objective="fix",
                implementation_spec_ref="SPEC-1",
                ac_refs=["AC-X"],
                allowed_scope=["app/**"],
                required_outputs=["app/x.py"],
                verification_requirements=[],
                estimated_size="S",
            )
        ]
    )
    ok, errors = RepairSpecValidator().validate_task_plan(plan)
    assert not ok
