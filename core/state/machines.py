from __future__ import annotations

from core.domain.enums import ActorKind, DeliveryCycleType, TaskStatus
from core.state.types import Edge, Machine


def _human_only(edge: Edge) -> Edge:
    return Edge(
        to=edge.to,
        guards=edge.guards,
        actor_kinds=(ActorKind.HUMAN,),
        effects=edge.effects,
    )


def _cancel_fail_edges(
    states: frozenset[str], terminal: frozenset[str]
) -> dict[tuple[str, str], Edge]:
    edges: dict[tuple[str, str], Edge] = {}
    for state in states:
        if state in terminal:
            continue
        edges[(state, "cancel")] = Edge(to="CANCELLED", actor_kinds=(ActorKind.HUMAN,))
        edges[(state, "fail")] = Edge(
            to="FAILED",
            actor_kinds=(ActorKind.SYSTEM,),
        )
    return edges


def _greenfield_planning_forward(
    *, include_revise_architecture: bool = True
) -> dict[tuple[str, str], Edge]:
    edges: dict[tuple[str, str], Edge] = {}
    if include_revise_architecture:
        edges[("PLANNING", "revise_architecture")] = _human_only(Edge(to="ARCHITECTURE"))
    edges.update(
        {
            (
                "PLANNING",
                "start_development",
            ): Edge(
                to="DEVELOPMENT",
                guards=(
                    "implementation_specs_approved",
                    "task_plan_accepted_contracts_issued",
                ),
            ),
            (
                "DEVELOPMENT",
                "start_integration",
            ): Edge(
                to="INTEGRATION",
                guards=("all_code_tasks_completed",),
                effects=("create_integration_candidate",),
            ),
            (
                "INTEGRATION",
                "start_assurance",
            ): Edge(
                to="ASSURANCE",
                guards=("ic_ready_and_canonical_index_current",),
            ),
            (
                "INTEGRATION",
                "return_to_development",
            ): Edge(to="DEVELOPMENT", guards=("remediation_tasks_exist",)),
            (
                "ASSURANCE",
                "return_to_development",
            ): Edge(to="DEVELOPMENT", guards=("remediation_tasks_exist",)),
            ("ASSURANCE", "start_release"): Edge(to="RELEASE", guards=("required_gates_pass",)),
            ("RELEASE", "complete"): Edge(to="COMPLETE", guards=("release_executed",)),
        }
    )
    return edges


TERMINAL_COMMON = frozenset({"CANCELLED", "FAILED"})

GREENFIELD_STATES = frozenset(
    {
        "DISCOVERY",
        "PRODUCT_MODEL",
        "ARCHITECTURE",
        "PLANNING",
        "DEVELOPMENT",
        "INTEGRATION",
        "ASSURANCE",
        "RELEASE",
        "COMPLETE",
        *TERMINAL_COMMON,
    }
)

GREENFIELD_TERMINAL = frozenset({"COMPLETE", *TERMINAL_COMMON})

GREENFIELD_MACHINE = Machine(
    name="GREENFIELD_BUILD",
    states=GREENFIELD_STATES,
    initial="DISCOVERY",
    terminal=GREENFIELD_TERMINAL,
    edges={
        **_cancel_fail_edges(GREENFIELD_STATES, GREENFIELD_TERMINAL),
        (
            "DISCOVERY",
            "start_product_modeling",
        ): Edge(to="PRODUCT_MODEL", guards=("product_source_ingested",)),
        ("PRODUCT_MODEL", "start_architecture"): Edge(
            to="ARCHITECTURE", guards=("scope_approved",)
        ),
        ("ARCHITECTURE", "revise_product_model"): _human_only(Edge(to="PRODUCT_MODEL")),
        (
            "ARCHITECTURE",
            "start_planning",
        ): Edge(
            to="PLANNING",
            guards=("architecture_approved", "repository_ready_with_canonical_commit"),
            effects=("pin_base_sha",),
        ),
        **_greenfield_planning_forward(include_revise_architecture=True),
    },
)

BROWNFIELD_STATES = frozenset(
    {
        "RECON",
        "CODE_INDEX",
        "RECOVERED_SPEC",
        "BASELINE",
        "READINESS",
        "REMEDIATION",
        "READY",
        *TERMINAL_COMMON,
    }
)
BROWNFIELD_TERMINAL = frozenset({"READY", *TERMINAL_COMMON})

BROWNFIELD_MACHINE = Machine(
    name="BROWNFIELD_ONBOARDING",
    states=BROWNFIELD_STATES,
    initial="RECON",
    terminal=BROWNFIELD_TERMINAL,
    edges={
        **_cancel_fail_edges(BROWNFIELD_STATES, BROWNFIELD_TERMINAL),
        (
            "RECON",
            "start_code_index",
        ): Edge(
            to="CODE_INDEX",
            guards=("repository_ready_with_canonical_commit",),
            effects=("pin_base_sha", "brownfield_code_index_stage"),
        ),
        (
            "CODE_INDEX",
            "start_spec_recovery",
        ): Edge(
            to="RECOVERED_SPEC",
            guards=("canonical_repository_index_ready",),
            effects=("brownfield_spec_recovery_stage",),
        ),
        (
            "RECOVERED_SPEC",
            "retry_spec_recovery",
        ): Edge(
            to="RECOVERED_SPEC",
            guards=("recovery_proposal_rejected",),
            effects=("brownfield_spec_recovery_retry",),
        ),
        (
            "RECOVERED_SPEC",
            "start_baseline",
        ): Edge(
            to="BASELINE",
            guards=("recovery_proposal_persisted",),
            effects=("brownfield_baseline_stage",),
        ),
        (
            "BASELINE",
            "start_readiness",
        ): Edge(
            to="READINESS",
            guards=("baseline_review_complete",),
            effects=("brownfield_readiness_assess",),
        ),
        (
            "READINESS",
            "start_remediation",
        ): Edge(
            to="REMEDIATION",
            guards=("readiness_failed_remediable",),
            effects=("brownfield_remediation_draft",),
        ),
        (
            "REMEDIATION",
            "reassess_readiness",
        ): Edge(
            to="READINESS",
            guards=("remediation_integrated_and_reindexed",),
            effects=("brownfield_remediation_reassess",),
        ),
        (
            "READINESS",
            "declare_ready",
        ): Edge(
            to="READY",
            guards=("readiness_assessment_ready",),
            effects=("declare_ready_project",),
        ),
    },
)

FEATURE_STATES = frozenset(
    {
        "INTAKE",
        "SPEC_DELTA",
        "IMPACT_ANALYSIS",
        "PLANNING",
        "DEVELOPMENT",
        "INTEGRATION",
        "ASSURANCE",
        "RELEASE",
        "COMPLETE",
        *TERMINAL_COMMON,
    }
)
FEATURE_TERMINAL = GREENFIELD_TERMINAL

FEATURE_MACHINE = Machine(
    name="FEATURE_CHANGE",
    states=FEATURE_STATES,
    initial="INTAKE",
    terminal=FEATURE_TERMINAL,
    edges={
        **_cancel_fail_edges(FEATURE_STATES, FEATURE_TERMINAL),
        (
            "INTAKE",
            "start_spec_delta",
        ): Edge(
            to="SPEC_DELTA",
            guards=("change_request_linked", "project_change_ready"),
            effects=("feature_change_schedule_interpret",),
        ),
        (
            "SPEC_DELTA",
            "start_impact_analysis",
        ): Edge(
            to="IMPACT_ANALYSIS",
            guards=("spec_delta_approved", "repository_ready_with_canonical_commit"),
            effects=("pin_base_sha", "feature_change_run_impact"),
        ),
        ("IMPACT_ANALYSIS", "revise_spec_delta"): _human_only(Edge(to="SPEC_DELTA")),
        (
            "IMPACT_ANALYSIS",
            "start_planning",
        ): Edge(
            to="PLANNING",
            guards=("impact_assessment_complete", "architecture_delta_resolved"),
            effects=("feature_change_schedule_impl_spec_delta",),
        ),
        **_greenfield_planning_forward(include_revise_architecture=False),
    },
)

BUGFIX_STATES = frozenset(
    {
        "TRIAGE",
        "REPRODUCTION",
        "EXPECTED_BEHAVIOR",
        "ROOT_CAUSE",
        "DEVELOPMENT",
        "INTEGRATION",
        "REGRESSION",
        "ASSURANCE",
        "RELEASE",
        "COMPLETE",
        *TERMINAL_COMMON,
    }
)
BUGFIX_TERMINAL = GREENFIELD_TERMINAL

BUGFIX_MACHINE = Machine(
    name="BUG_FIX",
    states=BUGFIX_STATES,
    initial="TRIAGE",
    terminal=BUGFIX_TERMINAL,
    edges={
        **_cancel_fail_edges(BUGFIX_STATES, BUGFIX_TERMINAL),
        (
            "TRIAGE",
            "start_reproduction",
        ): Edge(
            to="REPRODUCTION",
            guards=("defect_triaged", "repository_ready_with_canonical_commit"),
            effects=("pin_base_sha", "bug_fix_schedule_reproduce"),
        ),
        (
            "REPRODUCTION",
            "resolve_expected_behavior",
        ): Edge(
            to="EXPECTED_BEHAVIOR",
            guards=("reproduction_recorded",),
            effects=("bug_fix_schedule_expected_behavior",),
        ),
        (
            "EXPECTED_BEHAVIOR",
            "start_root_cause",
        ): Edge(
            to="ROOT_CAUSE",
            guards=("expected_behavior_resolved",),
            effects=("bug_fix_schedule_root_cause",),
        ),
        (
            "ROOT_CAUSE",
            "start_development",
        ): Edge(
            to="DEVELOPMENT",
            guards=("repair_spec_approved_contracts_issued",),
        ),
        (
            "DEVELOPMENT",
            "start_integration",
        ): Edge(
            to="INTEGRATION",
            guards=("all_code_tasks_completed",),
            effects=("create_integration_candidate",),
        ),
        (
            "INTEGRATION",
            "start_regression",
        ): Edge(
            to="REGRESSION",
            guards=("ic_ready_and_canonical_index_current",),
            effects=("bug_fix_run_regression_stage",),
        ),
        (
            "INTEGRATION",
            "return_to_development",
        ): Edge(to="DEVELOPMENT", guards=("remediation_tasks_exist",)),
        (
            "REGRESSION",
            "return_to_development",
        ): Edge(to="DEVELOPMENT", guards=("remediation_tasks_exist",)),
        (
            "ASSURANCE",
            "return_to_development",
        ): Edge(to="DEVELOPMENT", guards=("remediation_tasks_exist",)),
        (
            "REGRESSION",
            "start_assurance",
        ): Edge(
            to="ASSURANCE",
            guards=("reproduction_and_regression_pass",),
        ),
        ("ASSURANCE", "start_release"): Edge(to="RELEASE", guards=("required_gates_pass",)),
        ("RELEASE", "complete"): Edge(to="COMPLETE", guards=("release_executed",)),
    },
)

REMEDIATION_STATES = frozenset(
    {
        "INTAKE",
        "PLANNING",
        "DEVELOPMENT",
        "INTEGRATION",
        "ASSURANCE",
        "RELEASE",
        "COMPLETE",
        *TERMINAL_COMMON,
    }
)
REMEDIATION_TERMINAL = GREENFIELD_TERMINAL

REMEDIATION_MACHINE = Machine(
    name="REMEDIATION",
    states=REMEDIATION_STATES,
    initial="INTAKE",
    terminal=REMEDIATION_TERMINAL,
    edges={
        **_cancel_fail_edges(REMEDIATION_STATES, REMEDIATION_TERMINAL),
        (
            "INTAKE",
            "start_planning",
        ): Edge(
            to="PLANNING",
            guards=("remediation_scope_approved", "repository_ready_with_canonical_commit"),
            effects=("pin_base_sha",),
        ),
        **_greenfield_planning_forward(include_revise_architecture=False),
    },
)

DELIVERY_CYCLE_MACHINES: dict[DeliveryCycleType, Machine] = {
    DeliveryCycleType.GREENFIELD_BUILD: GREENFIELD_MACHINE,
    DeliveryCycleType.BROWNFIELD_ONBOARDING: BROWNFIELD_MACHINE,
    DeliveryCycleType.FEATURE_CHANGE: FEATURE_MACHINE,
    DeliveryCycleType.BUG_FIX: BUGFIX_MACHINE,
    DeliveryCycleType.REMEDIATION: REMEDIATION_MACHINE,
}

for _machine in DELIVERY_CYCLE_MACHINES.values():
    _machine.validate()


TASK_STATES = frozenset({s.value for s in TaskStatus})
TASK_TERMINAL = frozenset({"CANCELLED"})

TASK_MACHINE = Machine(
    name="task",
    states=TASK_STATES,
    initial="DRAFT",
    terminal=TASK_TERMINAL,
    edges={
        ("DRAFT", "mark_ready"): Edge(to="READY"),  # resolved by service to BLOCKED
        ("DRAFT", "mark_blocked"): Edge(to="BLOCKED"),
        ("BLOCKED", "unblock"): Edge(to="READY"),
        ("BLOCKED", "resume_execution"): Edge(to="RUNNING", actor_kinds=(ActorKind.SYSTEM,)),
        ("READY", "enqueue"): Edge(to="QUEUED", actor_kinds=(ActorKind.SYSTEM,)),
        ("QUEUED", "start_execution"): Edge(to="RUNNING", actor_kinds=(ActorKind.SYSTEM,)),
        ("RUNNING", "complete"): Edge(to="COMPLETED", actor_kinds=(ActorKind.SYSTEM,)),
        ("RUNNING", "fail_retry"): Edge(to="READY", actor_kinds=(ActorKind.SYSTEM,)),
        ("RUNNING", "fail_terminal"): Edge(to="FAILED", actor_kinds=(ActorKind.SYSTEM,)),
        ("RUNNING", "checkpoint_blocked"): Edge(to="BLOCKED", actor_kinds=(ActorKind.SYSTEM,)),
        ("FAILED", "retry_task"): Edge(to="READY", actor_kinds=(ActorKind.HUMAN,)),
        ("COMPLETED", "mark_stale"): Edge(to="STALE", actor_kinds=(ActorKind.SYSTEM,)),
        ("COMPLETED", "mark_revalidation"): Edge(
            to="REVALIDATION_REQUIRED", actor_kinds=(ActorKind.SYSTEM,)
        ),
        ("STALE", "reissue_ready"): Edge(to="READY", actor_kinds=(ActorKind.SYSTEM,)),
        ("REVALIDATION_REQUIRED", "reissue_ready"): Edge(
            to="READY", actor_kinds=(ActorKind.SYSTEM,)
        ),
        **{
            (state, "cancel_task"): Edge(to="CANCELLED", actor_kinds=(ActorKind.HUMAN,))
            for state in TASK_STATES
            if state not in TASK_TERMINAL
        },
    },
)
TASK_MACHINE.validate()

CONTRACT_MACHINE = Machine(
    name="task_contract",
    states=frozenset({"DRAFT", "ISSUED", "SUPERSEDED"}),
    initial="DRAFT",
    terminal=frozenset({"SUPERSEDED"}),
    edges={
        ("DRAFT", "issue_contract"): Edge(to="ISSUED"),
        ("ISSUED", "supersede"): Edge(
            to="SUPERSEDED",
            actor_kinds=(ActorKind.SYSTEM, ActorKind.HUMAN),
        ),
    },
)
CONTRACT_MACHINE.validate()

REPO_STATES = frozenset(
    {
        "PROVISIONING",
        "CLONING",
        "READY",
        "SYNCING",
        "ERROR",
    }
)

REPOSITORY_MACHINE = Machine(
    name="repository",
    states=REPO_STATES,
    initial="PROVISIONING",
    terminal=frozenset(),
    edges={
        ("PROVISIONING", "materialization_failed"): Edge(
            to="ERROR", actor_kinds=(ActorKind.SYSTEM,)
        ),
        ("CLONING", "materialization_failed"): Edge(to="ERROR", actor_kinds=(ActorKind.SYSTEM,)),
        (
            "PROVISIONING",
            "record_materialization",
        ): Edge(to="READY", actor_kinds=(ActorKind.SYSTEM,)),
        (
            "CLONING",
            "record_materialization",
        ): Edge(to="READY", actor_kinds=(ActorKind.SYSTEM,)),
        ("READY", "sync_started"): Edge(to="SYNCING", actor_kinds=(ActorKind.SYSTEM,)),
        ("SYNCING", "sync_completed"): Edge(to="READY", actor_kinds=(ActorKind.SYSTEM,)),
        ("SYNCING", "sync_failed"): Edge(to="ERROR", actor_kinds=(ActorKind.SYSTEM,)),
        (
            "ERROR",
            "retry_materialization",
        ): Edge(to="PROVISIONING", actor_kinds=(ActorKind.HUMAN, ActorKind.SYSTEM)),
        ("ERROR", "retry_sync"): Edge(
            to="SYNCING", actor_kinds=(ActorKind.HUMAN, ActorKind.SYSTEM)
        ),
    },
)
REPOSITORY_MACHINE.validate()

APPROVAL_MACHINE = Machine(
    name="approval",
    states=frozenset(
        {
            "PENDING",
            "APPROVED",
            "REJECTED",
            "CHANGES_REQUESTED",
            "EXPIRED",
            "CANCELLED",
        }
    ),
    initial="PENDING",
    terminal=frozenset({"APPROVED", "REJECTED", "CHANGES_REQUESTED", "EXPIRED", "CANCELLED"}),
    edges={
        ("PENDING", "approve"): Edge(to="APPROVED", actor_kinds=(ActorKind.HUMAN,)),
        ("PENDING", "reject"): Edge(to="REJECTED", actor_kinds=(ActorKind.HUMAN,)),
        ("PENDING", "request_changes"): Edge(
            to="CHANGES_REQUESTED", actor_kinds=(ActorKind.HUMAN,)
        ),
        ("PENDING", "expire"): Edge(to="EXPIRED", actor_kinds=(ActorKind.SYSTEM,)),
        ("PENDING", "cancel"): Edge(to="CANCELLED", actor_kinds=(ActorKind.SYSTEM,)),
    },
)
APPROVAL_MACHINE.validate()

EXECUTION_ACTIVE = frozenset(
    {
        "QUEUED",
        "LEASED",
        "STARTED",
        "CHECKPOINTED",
        "OUTPUT_PRODUCED",
        "VALIDATING",
        "COMMITTED",
    }
)
EXECUTION_TERMINAL = frozenset({"COMPLETED", "FAILED", "TIMED_OUT", "CANCELLED", "STALE"})
EXECUTION_STATES = frozenset({*EXECUTION_ACTIVE, *EXECUTION_TERMINAL})

EXECUTION_MACHINE = Machine(
    name="execution",
    states=EXECUTION_STATES,
    initial="QUEUED",
    terminal=EXECUTION_TERMINAL,
    edges={
        ("QUEUED", "lease"): Edge(to="LEASED", actor_kinds=(ActorKind.SYSTEM,)),
        ("LEASED", "start"): Edge(to="STARTED", actor_kinds=(ActorKind.SYSTEM,)),
        ("LEASED", "requeue"): Edge(to="QUEUED", actor_kinds=(ActorKind.SYSTEM,)),
        ("LEASED", "stale"): Edge(to="STALE", actor_kinds=(ActorKind.SYSTEM,)),
        ("STARTED", "checkpoint"): Edge(to="CHECKPOINTED", actor_kinds=(ActorKind.SYSTEM,)),
        ("CHECKPOINTED", "resume"): Edge(to="STARTED", actor_kinds=(ActorKind.SYSTEM,)),
        ("CHECKPOINTED", "stale"): Edge(to="STALE", actor_kinds=(ActorKind.SYSTEM,)),
        ("STARTED", "output_produced"): Edge(to="OUTPUT_PRODUCED", actor_kinds=(ActorKind.SYSTEM,)),
        ("OUTPUT_PRODUCED", "validate"): Edge(to="VALIDATING", actor_kinds=(ActorKind.SYSTEM,)),
        ("VALIDATING", "commit"): Edge(to="COMMITTED", actor_kinds=(ActorKind.SYSTEM,)),
        ("VALIDATING", "complete"): Edge(to="COMPLETED", actor_kinds=(ActorKind.SYSTEM,)),
        ("COMMITTED", "complete"): Edge(to="COMPLETED", actor_kinds=(ActorKind.SYSTEM,)),
        ("STARTED", "fail"): Edge(to="FAILED", actor_kinds=(ActorKind.SYSTEM,)),
        ("OUTPUT_PRODUCED", "fail"): Edge(to="FAILED", actor_kinds=(ActorKind.SYSTEM,)),
        ("VALIDATING", "fail"): Edge(to="FAILED", actor_kinds=(ActorKind.SYSTEM,)),
        ("COMMITTED", "fail"): Edge(to="FAILED", actor_kinds=(ActorKind.SYSTEM,)),
        ("STARTED", "timeout"): Edge(to="TIMED_OUT", actor_kinds=(ActorKind.SYSTEM,)),
        **{
            (state, "cancel"): Edge(to="CANCELLED", actor_kinds=(ActorKind.HUMAN,))
            for state in EXECUTION_STATES
            if state not in EXECUTION_TERMINAL
        },
        ("QUEUED", "stale"): Edge(to="STALE", actor_kinds=(ActorKind.SYSTEM,)),
    },
)
EXECUTION_MACHINE.validate()
