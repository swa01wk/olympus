import uuid

import pytest
from core.planning.compiler import CompilerInputs, TaskContractCompiler
from core.planning.schemas import ArchitectureBody, ImplementationSpecBody, TaskDraft
from core.policy.policy_service import PolicyService
from tests.fixtures.planning_harness import supportdesk_architecture_proposal

pytestmark = pytest.mark.unit

_FIXED = uuid.UUID("00000000-0000-4000-8000-000000000001")
_FIXED2 = uuid.UUID("00000000-0000-4000-8000-000000000002")
_FIXED3 = uuid.UUID("00000000-0000-4000-8000-000000000003")


def _arch_body() -> ArchitectureBody:
    return supportdesk_architecture_proposal().body


def _inputs(**overrides: object) -> CompilerInputs:
    draft = TaskDraft(
        ref="T-1",
        title="t",
        objective="obj",
        implementation_spec_ref="SPEC-IMPL-1",
        ac_refs=["AC-1"],
        allowed_scope=["app/api/**"],
        required_outputs=["candidate_commit", "changed_files", "test_results"],
        verification_requirements=["tests pass"],
        estimated_size="S",
    )
    base = CompilerInputs(
        task_draft=draft,
        implementation_spec_id=_FIXED,
        implementation_spec_version=1,
        implementation_spec_lineage="SPEC-IMPL-1",
        implementation_spec_body=ImplementationSpecBody(
            summary="s",
            components=["api"],
            file_scope=["app/api/**", "tests/**"],
        ),
        feature_spec_id=_FIXED2,
        feature_spec_version=1,
        feature_spec_lineage="SPEC-FEAT-1",
        feature_spec_rules=["rule-a"],
        architecture_id=_FIXED3,
        architecture_version=1,
        architecture_body=_arch_body(),
        ac_refs=[],
        repository_id=_FIXED,
        has_dependencies=False,
        policy=PolicyService({}),
    )
    for k, v in overrides.items():
        object.__setattr__(base, k, v)
    return base


def test_compiler_deterministic_hash() -> None:
    compiler = TaskContractCompiler()
    body1, h1 = compiler.compile(_inputs())
    body2, h2 = compiler.compile(_inputs())
    assert h1 == h2
    assert body1.model_dump() == body2.model_dump()


def test_compiler_hash_changes_with_input() -> None:
    compiler = TaskContractCompiler()
    _, h1 = compiler.compile(_inputs())
    _, h2 = compiler.compile(_inputs(has_dependencies=True))
    assert h1 != h2


def test_compiler_scope_intersection() -> None:
    compiler = TaskContractCompiler()
    body, _ = compiler.compile(_inputs())
    assert body.allowed_scope == ["app/api/**"]
    assert "Use async SQLAlchemy where applicable" in body.constraints
