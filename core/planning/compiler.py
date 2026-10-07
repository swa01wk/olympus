from __future__ import annotations

import uuid
from dataclasses import dataclass
from typing import Any, Literal

from core.domain.canonical_json import sha256_hex
from core.domain.enums import WorkType
from core.domain.task_contracts.schemas import TaskContractBody, VersionedRef
from core.planning.glob_scope import intersect_scopes
from core.planning.schemas import ArchitectureBody, ImplementationSpecBody, TaskDraft
from core.policy.policy_service import PolicyService
from core.runtime.agent_profiles import all_profiles


def _forge_allowed_actions() -> tuple[str, ...]:
    profile = all_profiles().get("forge.implementation")
    if profile:
        return profile.allowed_tools
    return _DEFAULT_FORGE_ACTIONS


_DEFAULT_FORGE_ACTIONS = (
    "repo.read",
    "repo.search",
    "repo.list",
    "repo.write",
    "shell.run",
    "test.run",
    "git.diff",
    "git.status",
    "git.commit",
    "olympus.ask_question",
    "olympus.submit_artifact",
)

_SIZE_TIMEOUTS = {"S": 900, "M": 1800, "L": 3600}
_PROHIBITED_DEFAULT = ("modify_ci_config", "write_protected_refs", "modify_auth")


@dataclass(frozen=True)
class CompilerInputs:
    task_draft: TaskDraft
    implementation_spec_id: uuid.UUID
    implementation_spec_version: int
    implementation_spec_lineage: str
    implementation_spec_body: ImplementationSpecBody
    feature_spec_id: uuid.UUID
    feature_spec_version: int
    feature_spec_lineage: str
    feature_spec_rules: list[str]
    architecture_id: uuid.UUID
    architecture_version: int
    architecture_body: ArchitectureBody
    ac_refs: list[tuple[uuid.UUID, int, str]]
    repository_id: uuid.UUID | None
    has_dependencies: bool
    policy: PolicyService
    impact_file_paths: frozenset[str] | None = None
    impacted_baseline_keys: tuple[str, ...] = ()
    new_acceptance_test_refs: tuple[str, ...] = ()
    extra_constraints: tuple[str, ...] = ()
    deny_scope_prefixes: tuple[str, ...] = ()


class TaskContractCompiler:
    def compile(self, inputs: CompilerInputs) -> tuple[TaskContractBody, str]:
        body, payload = self._build(inputs)
        inputs_hash = sha256_hex(payload)
        return body, inputs_hash

    def _build(self, inputs: CompilerInputs) -> tuple[TaskContractBody, dict[str, Any]]:
        draft = inputs.task_draft
        allowed = intersect_scopes(draft.allowed_scope, inputs.implementation_spec_body.file_scope)
        if inputs.impact_file_paths:
            impact_scope = sorted(inputs.impact_file_paths)
            allowed = intersect_scopes(allowed, impact_scope)
        if inputs.deny_scope_prefixes:
            allowed = [
                p
                for p in allowed
                if not any(p.startswith(prefix) for prefix in inputs.deny_scope_prefixes)
            ]
        if not allowed:
            allowed = ["**"]
        constraints = list(inputs.architecture_body.constraints)
        constraints.extend(inputs.extra_constraints)
        constraints.extend(inputs.architecture_body.dependency_rules)
        constraints.extend(draft.constraints)
        constraints.extend(inputs.feature_spec_rules)
        if inputs.impacted_baseline_keys:
            constraints.append(
                "preserve behavior of impacted baselines: "
                + ", ".join(inputs.impacted_baseline_keys)
            )

        versioned_inputs: list[VersionedRef] = [
            VersionedRef(
                ref_type="IMPLEMENTATION_SPEC",
                ref_id=inputs.implementation_spec_id,
                version=inputs.implementation_spec_version,
                key=inputs.implementation_spec_lineage,
            ),
            VersionedRef(
                ref_type="FEATURE_SPEC",
                ref_id=inputs.feature_spec_id,
                version=inputs.feature_spec_version,
                key=inputs.feature_spec_lineage,
            ),
            VersionedRef(
                ref_type="ARCHITECTURE",
                ref_id=inputs.architecture_id,
                version=inputs.architecture_version,
                key="ARCH",
            ),
        ]
        for ac_id, ac_ver, ac_key in inputs.ac_refs:
            versioned_inputs.append(
                VersionedRef(
                    ref_type="ACCEPTANCE_CRITERION",
                    ref_id=ac_id,
                    version=ac_ver,
                    key=ac_key,
                )
            )

        base_policy: Literal["CYCLE_BASE", "DEPENDENCY_INTEGRATION"] = (
            "DEPENDENCY_INTEGRATION" if inputs.has_dependencies else "CYCLE_BASE"
        )
        wall = _SIZE_TIMEOUTS.get(draft.estimated_size, 1800)
        allowed_actions = list(_forge_allowed_actions())

        body = TaskContractBody(
            objective=draft.objective,
            work_type=WorkType.CODE_CHANGE,
            inputs=sorted(versioned_inputs, key=lambda r: (r.ref_type, str(r.ref_id))),
            repository_id=inputs.repository_id,
            base_policy=base_policy,
            allowed_scope=allowed,
            constraints=sorted(set(constraints)),
            prohibited_operations=list(_PROHIBITED_DEFAULT),
            allowed_actions=allowed_actions,
            required_outputs=list(draft.required_outputs),
            verification_requirements=sorted(
                set(draft.verification_requirements)
                | set(inputs.impacted_baseline_keys)
                | set(inputs.new_acceptance_test_refs)
            ),
            escalation_rules={
                "architecture_change": "REQUIRE_APPROVAL",
                "ambiguous_requirement": "ASK_HUMAN",
            },
            agent_profile="forge.implementation",
            executor_kind="AGENT_RUNTIME",
            model_alias="implementation",
            timeouts={"wall_clock_s": wall},
            budgets={},
        )
        payload = {
            "draft": draft.model_dump(mode="json"),
            "implementation_spec_id": str(inputs.implementation_spec_id),
            "feature_spec_id": str(inputs.feature_spec_id),
            "architecture_id": str(inputs.architecture_id),
            "policy_hash": (
                inputs.policy.version_row.content_hash if inputs.policy.version_row else ""
            ),
            "has_dependencies": inputs.has_dependencies,
        }
        return body, payload
