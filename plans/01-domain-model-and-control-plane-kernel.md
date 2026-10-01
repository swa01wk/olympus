# Phase 01 — Domain Model and Control Plane Kernel

## 1. Objective

Introduce Olympus's authoritative control-plane kernel:

- the persistent **Project** and its **Repository**, using one unified abstraction for `GREENFIELD_MANAGED` and `EXTERNAL_CLONE` repositories (README §5.9). The Control Plane owns repository identity, source type, provider, default branch, `credential_ref`, lifecycle status, the canonical **RepositoryWorkspace** identity (logical location only) and the append-only **RepositoryRevision** history behind `canonical_commit`. Git storage owns the source bytes. This phase performs **no** Git materialization (Phase 04);
- the bounded **DeliveryCycle**, with journey-specific state machines for GREENFIELD_BUILD, BROWNFIELD_ONBOARDING, FEATURE_CHANGE, BUG_FIX and REMEDIATION;
- **Task**, **TaskDependency** and versioned, immutable **TaskContract**;
- explicit human **Approval**;
- deterministic **Policy** versions;
- the **command bus** with idempotency;
- the **transition service** with a fail-closed guard registry;
- transactional **domain/audit events** with an outbox and SSE stream;
- authenticated **Actors**.

This phase implements ARCH's "control plane over agent framework" principle. Every later phase mutates canonical state only through the services created here.

## 2. Architectural Context

- **Position:** Governance / Delivery Control plane and Work plane (ARCH §3.1).
- **Upstream:** Phase 00 (DB, config, logging).
- **Downstream:** every phase. Phase 03 adds Execution states, Phases 05/06/08/09/10/12/13/14/15 register lifecycle guards, and Phase 17 consumes the APIs and SSE. Phase 04 materializes Repositories into their canonical RepositoryWorkspace. Phase 07 reads Git objects through the `WorkspaceLocator`. Phases 08/10/16 advance the canonical revision through `RepositoryRevisionService`.
- **Lifecycle stages:** all DeliveryCycle states (definitions only; most guards are registered later), Task states and TaskContract states.
- **Invariants:** 5, 6, 12 (groundwork), 13, 23–25 (approval/authority groundwork) and 36.
  - Project ≠ DeliveryCycle.
  - Task ≠ Execution (Execution arrives in Phase 03).
  - TaskContract is versioned and immutable once issued.
  - Approvals are explicit persisted objects.
  - State transition and audit commit in one transaction (TECH §5.3).
  - Runtime cannot mutate lifecycle state.

## 3. Current Repository Assessment

Inspection on 2026-10-01: no domain code exists. Expected state at phase start: the Phase 00 scaffold.

### Existing
- (after Phase 00) `core/db`, `core/config`, `core/observability`, `apps/control_api` — **RETAIN/EXTEND**.

### Partial
- None.

### Missing
- All domain entities, state machines, the command bus, policy, approvals, events, auth and APIs — **ADD**.

### Refactor / Migration Required
- None.

| Component | Classification |
|---|---|
| `core/domain/{actors,projects,repositories,delivery_cycles,tasks,task_contracts,approvals,policy,events,audit}` | ADD |
| `core/repositories/{service.py,revision.py,workspace_locator.py}` | ADD |
| `core/state/{machines.py,guards.py,transition_service.py}` | ADD |
| `core/commands/{bus.py,command_log.py,registry.py}` | ADD |
| `core/policy/{policy_service.py,models.py}` + `config/policy/default.yaml` | ADD |
| `core/observability/outbox.py`, `apps/control_api/sse.py` | ADD |
| `apps/control_api/auth.py`, `routers/*` | ADD (EXTEND app factory from Phase 00) |

## 4. Scope

1. Entities and migrations for: actors, api_tokens, projects, project_sequences, repositories, repository_workspaces, repository_revisions, delivery_cycles, tasks, task_dependencies, task_contracts, approvals, policy_versions, command_log, domain_events and audit_events.
2. The `olympus_forbid_mutation()` trigger function and the attachment helper `attach_immutability(table, when_sql)`.
3. State machine definitions for all DeliveryCycle types, Task and TaskContract. The transition service (lock, expected state, guards, persist, events, commit) and the fail-closed guard registry.
4. Command bus with registry, idempotency (`command_log`), actor authorization and correlation propagation.
5. `TaskContractBody` Pydantic schema, canonical JSON hashing and DRAFT → ISSUED → SUPERSEDED versioning.
6. Approval lifecycle, decided only by HUMAN actors with the `APPROVER` role and pinned to subject version and hash.
7. PolicyService loading `config/policy/default.yaml` into an immutable, hashed `policy_versions` row.
8. Outbox publisher plus SSE stream per delivery cycle. A read-only SQL view `delivery_cycle_events` (TECH §5.1 name) selects `domain_events` rows whose `delivery_cycle_id` is set, ordered by `sequence`. It is not a separate table (D-15).
9. Bearer-token auth for actors and an actor seeding CLI.
10. Repository metadata model (README §5.9). This is domain only: no clone, init, fetch or webhooks.
    - `register_repository` command: creates an `EXTERNAL_CLONE` Repository in `CLONING` plus its PENDING canonical RepositoryWorkspace. It validates `provider`, `remote_url` (no userinfo; `file://` for LOCAL) and the `credential_ref` shape.
    - `create_delivery_cycle(GREENFIELD_BUILD)` on a Project without a Repository **declares** a `GREENFIELD_MANAGED` Repository (`provider=LOCAL`, `PROVISIONING`) plus its PENDING workspace in the same transaction and binds `cycle.repository_id`.
    - `WorkspaceLocator` maps logical locations to physical paths under `OLYMPUS_WORKSPACE_ROOT`, with confinement.
    - `RepositoryRevisionService` is the single writer of `canonical_commit`, `released_commit` and `repository_revisions`.
    - `RepositoryService.record_materialization` (SYSTEM only) is the method Phase 04 calls to record `registered_sha`, revision #1 (`MATERIALIZED`) and READY.
    - A read-only `GitInspector` (`rev-parse`, `cat-file -e`, `merge-base --is-ancestor`) answers "does this SHA exist / is it an ancestor" against a canonical workspace.

## 5. Out of Scope

- Execution, snapshot, lease and scheduler (Phase 03).
- Product/spec entities (Phase 05) and ImplementationSpec (Phase 06). Tasks may carry an optional `governing_ref` until then.
- Production guards owned by later phases. They are declared here as `RequiredGuard` placeholders that **fail closed**.
- Inbound event envelope (Phase 05), webhooks (Phase 16) and the dashboard (Phase 17).
- Git materialization (Greenfield provisioning, clone/fetch), credential resolution and `execution_workspaces` (Phase 04). Remote providers and sync (Phase 16). Canonical-revision advancement causes other than `MATERIALIZED` (Phases 08/10/16).

### Do Not Change
- No endpoint may set `state` or `status` directly (README §8.1).
- Do not let AGENT actors decide approvals or invoke lifecycle commands.
- No domain row or API payload may contain a credential value or a physical filesystem path (README §8.14).

## 6. Domain / Data Model Changes

Migrations: `0001_p01_actors_projects_repositories_cycles.py`, `0002_p01_tasks_dependencies_contracts.py`, `0003_p01_approvals_policy_command_log.py`, `0004_p01_domain_audit_events_immutability.py`. These map to TECH §30 migrations 001, 005 (partial), 011 (partial) and 013.

### Enums

```python
class ActorKind(StrEnum):
    HUMAN = "HUMAN"
    AGENT = "AGENT"
    SYSTEM = "SYSTEM"
    INTEGRATION = "INTEGRATION"


class ActorRole(StrEnum):
    OPERATOR = "OPERATOR"
    APPROVER = "APPROVER"
    VIEWER = "VIEWER"
    SYSTEM = "SYSTEM"
    INTEGRATION = "INTEGRATION"


class DeliveryCycleType(StrEnum):
    GREENFIELD_BUILD = "GREENFIELD_BUILD"
    BROWNFIELD_ONBOARDING = "BROWNFIELD_ONBOARDING"
    FEATURE_CHANGE = "FEATURE_CHANGE"
    BUG_FIX = "BUG_FIX"
    REMEDIATION = "REMEDIATION"


class ProjectReadiness(StrEnum):
    UNKNOWN = "UNKNOWN"
    ONBOARDING = "ONBOARDING"
    READY_FOR_CHANGE = "READY_FOR_CHANGE"


class WorkType(StrEnum):
    ANALYSIS = "ANALYSIS"
    CODE_CHANGE = "CODE_CHANGE"
    VERIFICATION = "VERIFICATION"
    INTEGRATION = "INTEGRATION"
    RELEASE = "RELEASE"


class TaskOrigin(StrEnum):
    IMPLEMENTATION_PLAN = "IMPLEMENTATION_PLAN"
    REMEDIATION = "REMEDIATION"
    REPAIR = "REPAIR"
    CONTROL_PLANE = "CONTROL_PLANE"


class TaskStatus(StrEnum):
    DRAFT = "DRAFT"
    BLOCKED = "BLOCKED"
    READY = "READY"
    QUEUED = "QUEUED"
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"
    STALE = "STALE"
    REVALIDATION_REQUIRED = "REVALIDATION_REQUIRED"


class TaskContractStatus(StrEnum):
    DRAFT = "DRAFT"
    ISSUED = "ISSUED"
    SUPERSEDED = "SUPERSEDED"


class ApprovalType(StrEnum):
    SCOPE = "SCOPE"
    ARCHITECTURE = "ARCHITECTURE"
    ARCHITECTURE_DELTA = "ARCHITECTURE_DELTA"
    IMPLEMENTATION_SPEC = "IMPLEMENTATION_SPEC"
    SPEC_DELTA = "SPEC_DELTA"
    SPEC_DECISION = "SPEC_DECISION"
    REPAIR_SPEC = "REPAIR_SPEC"
    PROMOTION = "PROMOTION"
    FINDING_WAIVER = "FINDING_WAIVER"
    ACTION = "ACTION"
    RELEASE = "RELEASE"
    READINESS = "READINESS"


class ApprovalStatus(StrEnum):
    PENDING = "PENDING"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    CHANGES_REQUESTED = "CHANGES_REQUESTED"
    EXPIRED = "EXPIRED"
    CANCELLED = "CANCELLED"
```

### Core tables (SQLAlchemy shapes)

```python
class Project(Base, UUIDPkMixin, TimestampMixin):
    __tablename__ = "projects"
    key: Mapped[str] = mapped_column(String(64), unique=True)
    name: Mapped[str]
    description: Mapped[str | None]
    readiness_state: Mapped[ProjectReadiness] = mapped_column(default=ProjectReadiness.UNKNOWN)


class RepositorySourceType(StrEnum):
    GREENFIELD_MANAGED = "GREENFIELD_MANAGED"
    EXTERNAL_CLONE = "EXTERNAL_CLONE"


class RepositoryProvider(StrEnum):
    LOCAL = "LOCAL"
    GITHUB = "GITHUB"
    GITEA = "GITEA"
    GITLAB = "GITLAB"
    BITBUCKET = "BITBUCKET"  # reserved extension points: registration -> 422 PROVIDER_NOT_SUPPORTED


class RepositoryStatus(StrEnum):
    PROVISIONING = "PROVISIONING"
    CLONING = "CLONING"
    READY = "READY"
    SYNCING = "SYNCING"
    ERROR = "ERROR"


class WorkspaceState(StrEnum):
    PENDING = "PENDING"
    MATERIALIZING = "MATERIALIZING"
    READY = "READY"
    REFRESHING = "REFRESHING"
    MISSING = "MISSING"
    ERROR = "ERROR"


class RevisionCause(StrEnum):
    MATERIALIZED = "MATERIALIZED"
    INTEGRATION_READY = "INTEGRATION_READY"
    RELEASED = "RELEASED"
    EXTERNAL_SYNC = "EXTERNAL_SYNC"
    REVERTED = "REVERTED"


class Repository(
    Base, UUIDPkMixin, TimestampMixin
):  # metadata only — source bytes live in Git (README §5.9.1)
    __tablename__ = "repositories"
    project_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("projects.id"), unique=True
    )  # one per Project in the MVP (Q-11)
    name: Mapped[str]
    source_type: Mapped[RepositorySourceType]
    provider: Mapped[RepositoryProvider]
    remote_url: Mapped[
        str | None
    ]  # no userinfo (CHECK); file:// for LOCAL external; null for unattached GREENFIELD_MANAGED
    default_branch: Mapped[str] = mapped_column(
        default="main"
    )  # EXTERNAL_CLONE: resolved at clone if not supplied
    registered_sha: Mapped[
        str | None
    ]  # immutable once set: Greenfield baseline commit / Brownfield cloned HEAD
    canonical_commit: Mapped[
        str | None
    ]  # authoritative project revision; written ONLY by RepositoryRevisionService
    released_commit: Mapped[
        str | None
    ]  # default-branch release line; written ONLY by RepositoryRevisionService
    status: Mapped[RepositoryStatus]
    status_reason: Mapped[str | None]  # error class / message on ERROR (never contains secrets)
    workspace_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("repository_workspaces.id", use_alter=True)
    )
    credential_ref: Mapped[str] = mapped_column(
        default="none:"
    )  # "<scheme>:<name>", scheme in none|env|file|secret; NEVER a value
    state_version: Mapped[int] = mapped_column(default=0)
    __table_args__ = (
        CheckConstraint(
            "credential_ref ~ '^(none|env|file|secret):[A-Za-z0-9_./-]*$'",
            name="ck_repositories_credential_ref",
        ),
        CheckConstraint(
            "remote_url IS NULL OR remote_url !~ '^[a-z+]+://[^/@]*@'",
            name="ck_repositories_remote_url_no_userinfo",
        ),
        CheckConstraint(
            "status <> 'READY' OR canonical_commit IS NOT NULL",
            name="ck_repositories_ready_has_commit",
        ),
    )


class RepositoryWorkspace(
    Base, UUIDPkMixin, TimestampMixin
):  # canonical Git storage location (bare repo, Q-13)
    __tablename__ = "repository_workspaces"
    repository_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("repositories.id"), index=True)
    workspace_type: Mapped[str] = mapped_column(default="CANONICAL")  # CANONICAL only in the MVP
    storage_backend: Mapped[str] = mapped_column(default="LOCAL_FILESYSTEM")
    logical_location: Mapped[str]  # "projects/<project_id>/repo" — relative, never a host path
    materialized_commit: Mapped[str | None]  # last SHA materialized/fetched and verified
    state: Mapped[WorkspaceState] = mapped_column(default=WorkspaceState.PENDING)
    __table_args__ = (
        UniqueConstraint("repository_id", "workspace_type"),
        UniqueConstraint("storage_backend", "logical_location"),
        CheckConstraint(
            "logical_location !~ '(^/|^[A-Za-z]:|\\.\\.)'", name="ck_repository_workspaces_logical"
        ),
    )


class RepositoryRevision(Base, UUIDPkMixin):  # append-only history of canonical_commit (immutable)
    __tablename__ = "repository_revisions"
    repository_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("repositories.id"), index=True)
    sequence: Mapped[int]
    commit_sha: Mapped[str]
    cause: Mapped[RevisionCause]
    integration_candidate_id: Mapped[uuid.UUID | None]  # FK added in Phase 08
    release_id: Mapped[uuid.UUID | None]  # FK added in Phase 10
    repository_event_id: Mapped[uuid.UUID | None]  # FK added in Phase 16
    reverts_revision_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("repository_revisions.id")
    )
    canonical_index_version_id: Mapped[uuid.UUID | None]  # FK added in Phase 07
    delivery_cycle_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("delivery_cycles.id"))
    actor_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("actors.id"))
    correlation_id: Mapped[str]
    created_at: Mapped[datetime]
    __table_args__ = (UniqueConstraint("repository_id", "sequence"),)


class DeliveryCycle(Base, UUIDPkMixin, TimestampMixin):
    __tablename__ = "delivery_cycles"
    project_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("projects.id"), index=True)
    key: Mapped[str]
    type: Mapped[DeliveryCycleType]
    objective: Mapped[str]
    state: Mapped[str]  # validated against machine for `type`
    state_version: Mapped[int] = mapped_column(default=0)  # optimistic concurrency
    repository_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("repositories.id"))
    base_sha: Mapped[
        str | None
    ]  # pinned from Repository.canonical_commit by the first code-needing transition (§7)
    terminal_reason: Mapped[str | None]
    closed_at: Mapped[datetime | None]
    opened_by_actor_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("actors.id"))
    __table_args__ = (UniqueConstraint("project_id", "key"),)


class Task(Base, UUIDPkMixin, TimestampMixin):
    __tablename__ = "tasks"
    delivery_cycle_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("delivery_cycles.id"), index=True
    )
    key: Mapped[str]
    title: Mapped[str]
    work_type: Mapped[WorkType]
    origin: Mapped[TaskOrigin]
    status: Mapped[TaskStatus] = mapped_column(default=TaskStatus.DRAFT, index=True)
    priority: Mapped[int] = mapped_column(default=100)
    governing_ref_type: Mapped[str | None]
    governing_ref_id: Mapped[uuid.UUID | None]  # e.g. PRODUCT_SOURCE_VERSION
    current_contract_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("task_contracts.id", use_alter=True)
    )
    allow_parallel_executions: Mapped[bool] = mapped_column(default=False)
    max_attempts: Mapped[int] = mapped_column(default=3)
    blocked_reason: Mapped[str | None]
    __table_args__ = (Index("ix_tasks_ready", "status", "priority", "created_at"),)


class TaskDependency(Base):
    __tablename__ = "task_dependencies"
    task_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("tasks.id"), primary_key=True)
    depends_on_task_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("tasks.id"), primary_key=True)
    kind: Mapped[str] = mapped_column(default="FINISH_TO_START")
    __table_args__ = (CheckConstraint("task_id <> depends_on_task_id"),)


class TaskContract(Base, UUIDPkMixin, TimestampMixin):
    __tablename__ = "task_contracts"
    task_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("tasks.id"), index=True)
    key: Mapped[str]
    version: Mapped[int]
    status: Mapped[TaskContractStatus]
    body: Mapped[dict] = mapped_column(JSONB)  # TaskContractBody
    content_hash: Mapped[str | None]  # sha256 canonical JSON; set at ISSUE
    compiled_by: Mapped[str]  # "manual" | "compiler:<version>"
    compiler_inputs_hash: Mapped[str | None]
    issued_at: Mapped[datetime | None]
    __table_args__ = (UniqueConstraint("task_id", "version"),)
```

Additional tables:
- `approvals`: id, key, project_id, delivery_cycle_id?, approval_type, subject_type, subject_id, subject_version, subject_hash, status, requested_by_actor_id, decided_by_actor_id?, decision_note, decided_at, policy_version_id.
- `policy_versions`: id, name, version, content JSONB, content_hash (unique), created_at. Immutable.
- `actors`: id, kind, name, roles text[], active. `api_tokens`: id, actor_id, token_hash (sha256), created_at, revoked_at.
- `project_sequences`: project_id, sequence_name, next_value (PK project_id + sequence_name).
- `command_log`: id, command_name, target_type, target_id, actor_id, idempotency_key, request_hash, status (ACCEPTED|REJECTED), result JSONB, error JSONB, correlation_id, created_at. `UNIQUE(actor_id, idempotency_key)`.
- `domain_events`: id, sequence BIGSERIAL, aggregate_type, aggregate_id, project_id, delivery_cycle_id?, event_type, payload JSONB, correlation_id, causation_id, actor_id, occurred_at, published_at?. Index on `(delivery_cycle_id, sequence)`.
- `audit_events`: id, actor_id, actor_kind, action, target_type, target_id, before JSONB, after JSONB, correlation_id, command_log_id?, occurred_at. Immutable.

### TaskContractBody (Pydantic; ARCH §5.1)

```python
class VersionedRef(BaseModel):
    ref_type: str  # FEATURE_SPEC | ACCEPTANCE_CRITERION | IMPLEMENTATION_SPEC | ARCHITECTURE | ARTIFACT | PRODUCT_SOURCE | ...
    ref_id: uuid.UUID
    version: int | None = None
    key: str | None = None


class TaskContractBody(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    objective: str
    work_type: WorkType
    inputs: list[VersionedRef]
    repository_id: uuid.UUID | None = None
    base_policy: Literal["CYCLE_BASE", "DEPENDENCY_INTEGRATION", "EXPLICIT_SHA", "NONE"] = "NONE"
    base_commit: str | None = None  # only when base_policy == EXPLICIT_SHA
    allowed_scope: list[str] = []  # repo-relative glob patterns
    constraints: list[str] = []
    prohibited_operations: list[str] = []
    allowed_actions: list[str] = []  # tool catalog names (Phase 04)
    required_outputs: list[
        str
    ] = []  # e.g. candidate_commit, changed_files, test_results, artifact:<kind>
    verification_requirements: list[str] = []
    escalation_rules: dict[str, Literal["REQUIRE_APPROVAL", "ASK_HUMAN", "FAIL"]] = {}
    required_approvals: list[uuid.UUID] = []
    agent_profile: str | None = None  # e.g. "forge", "kira.decompose"
    executor_kind: Literal["AGENT_RUNTIME", "DETERMINISTIC"]
    deterministic_executor: str | None = None  # e.g. "integration.merge"
    model_alias: str | None = None
    timeouts: dict[str, int] = {"wall_clock_s": 1800}
    budgets: dict[str, float] = {}  # tokens / usd
```

`canonical_json(obj)` = `json.dumps(obj, sort_keys=True, separators=(",",":"), default=str)` and `content_hash = sha256(canonical_json(body))`. The same function is reused by snapshots (Phase 03).

### Invariants and indexes
- Immutability trigger on `task_contracts`: when `OLD.status = 'ISSUED'`, only the change of `status` to `SUPERSEDED` is permitted. Any change to `body` or `content_hash`, and any DELETE, raises an error.
- `audit_events`, `policy_versions`: no UPDATE or DELETE. `domain_events`: only `published_at` may change.
- Partial unique index: at most one ISSUED contract per task (`UNIQUE(task_id) WHERE status='ISSUED'`).
- `UNIQUE(project_id, key)` on all keyed tables.
- `repository_revisions`: no UPDATE or DELETE (`olympus_forbid_mutation()`).
- Trigger `olympus_repository_revision_guard` (BEFORE UPDATE on `repositories`):
  - `registered_sha` is immutable once non-null.
  - A change to `canonical_commit` requires that the repository's highest-`sequence` revision row has `commit_sha = NEW.canonical_commit`.
  - A change to `released_commit` requires that row to have `cause = 'RELEASED'` and `commit_sha = NEW.released_commit`.
  - Raw SQL therefore cannot move the canonical revision without a revision record. `RepositoryRevisionService` inserts the revision row first and then updates the repository, in one transaction.
- Neither `repositories` nor `repository_workspaces` has a column that can hold a physical path or a credential value. The CHECKs above reject absolute/parent-relative logical locations, `credential_ref` values outside the reference grammar, and `remote_url` values with userinfo. The API layer additionally rejects secret-shaped `credential_ref` names (token prefixes such as `ghp_`/`glpat-`, PEM headers, ≥ 32-char high-entropy strings) with 422 `CREDENTIAL_VALUE_REJECTED`.

## 7. State / Lifecycle Changes

All machines live in `core/state/machines.py` as data: `Machine(name, states, initial, terminal, edges: dict[(from, command) → Edge(to, guards: list[GuardId], actor_kinds, effects: list[EffectId])])`. The transition service is the **only** writer of `delivery_cycles.state`, `tasks.status`, `task_contracts.status` and `repositories.status`. `RepositoryRevisionService` is the only writer of `repositories.canonical_commit` / `released_commit`.

### DeliveryCycle machines

Common edges on every type: `cancel` (any non-terminal → CANCELLED; HUMAN) and `fail` (any non-terminal → FAILED; SYSTEM, requires reason).

| Type | Edge (command) | From → To | Guard(s) (owning phase) |
|---|---|---|---|
| GREENFIELD_BUILD | start_product_modeling | DISCOVERY → PRODUCT_MODEL | `product_source_ingested` (05) |
| | start_architecture | PRODUCT_MODEL → ARCHITECTURE | `scope_approved` (05) |
| | revise_product_model | ARCHITECTURE → PRODUCT_MODEL | HUMAN only |
| | start_planning | ARCHITECTURE → PLANNING | `architecture_approved` (06), `repository_ready_with_canonical_commit` (**01**); effect `pin_base_sha` |
| | revise_architecture | PLANNING → ARCHITECTURE | HUMAN only |
| | start_development | PLANNING → DEVELOPMENT | `implementation_specs_approved`, `task_plan_accepted_contracts_issued` (06) |
| | start_integration | DEVELOPMENT → INTEGRATION | `all_code_tasks_completed` (08) |
| | start_assurance | INTEGRATION → ASSURANCE | `ic_ready_and_canonical_index_current` (08) |
| | return_to_development | INTEGRATION → DEVELOPMENT, ASSURANCE → DEVELOPMENT | `remediation_tasks_exist` (08/09) |
| | start_release | ASSURANCE → RELEASE | `required_gates_pass` (09) |
| | complete | RELEASE → COMPLETE | `release_executed` (10) |
| BROWNFIELD_ONBOARDING | start_code_index | RECON → CODE_INDEX | `repository_ready_with_canonical_commit` (**01**); effect `pin_base_sha` |
| | start_spec_recovery | CODE_INDEX → RECOVERED_SPEC | `canonical_repository_index_ready` (11) |
| | start_baseline | RECOVERED_SPEC → BASELINE | `recovery_proposal_persisted` (11) |
| | start_readiness | BASELINE → READINESS | `baseline_review_complete` (12) |
| | start_remediation | READINESS → REMEDIATION | `readiness_failed_remediable` (12) |
| | reassess_readiness | REMEDIATION → READINESS | `remediation_integrated_and_reindexed` (12) |
| | declare_ready | READINESS → READY | `readiness_assessment_ready` (12) |
| FEATURE_CHANGE | start_spec_delta | INTAKE → SPEC_DELTA | `change_request_linked`, `project_change_ready` (14) |
| | start_impact_analysis | SPEC_DELTA → IMPACT_ANALYSIS | `spec_delta_approved` (14), `repository_ready_with_canonical_commit` (**01**); effect `pin_base_sha` |
| | revise_spec_delta | IMPACT_ANALYSIS → SPEC_DELTA | HUMAN only |
| | start_planning | IMPACT_ANALYSIS → PLANNING | `impact_assessment_complete`, `architecture_delta_resolved` (13/14) |
| | start_development … complete | as GREENFIELD from PLANNING onward | same guards |
| BUG_FIX | start_reproduction | TRIAGE → REPRODUCTION | `defect_triaged` (15), `repository_ready_with_canonical_commit` (**01**); effect `pin_base_sha` |
| | resolve_expected_behavior | REPRODUCTION → EXPECTED_BEHAVIOR | `reproduction_recorded` (15) |
| | start_root_cause | EXPECTED_BEHAVIOR → ROOT_CAUSE | `expected_behavior_resolved` (15) |
| | start_development | ROOT_CAUSE → DEVELOPMENT | `repair_spec_approved_contracts_issued` (15) |
| | start_integration | DEVELOPMENT → INTEGRATION | `all_code_tasks_completed` (08) |
| | start_regression | INTEGRATION → REGRESSION | `ic_ready_and_canonical_index_current` (08) |
| | return_to_development | INTEGRATION/REGRESSION/ASSURANCE → DEVELOPMENT | `remediation_tasks_exist` |
| | start_assurance | REGRESSION → ASSURANCE | `reproduction_and_regression_pass` (15) |
| | start_release, complete | as GREENFIELD | same |
| REMEDIATION | INTAKE → PLANNING → DEVELOPMENT → INTEGRATION → ASSURANCE → RELEASE → COMPLETE | | `remediation_scope_approved` (09) and `repository_ready_with_canonical_commit` (**01**; effect `pin_base_sha`) on INTAKE → PLANNING; remaining edges as GREENFIELD |

Initial states: GREENFIELD_BUILD=DISCOVERY, BROWNFIELD_ONBOARDING=RECON, FEATURE_CHANGE=INTAKE, BUG_FIX=TRIAGE, REMEDIATION=INTAKE. Terminal states: COMPLETE, READY (Brownfield), CANCELLED, FAILED.

Brownfield `declare_ready` also sets `Project.readiness_state = READY_FOR_CHANGE` in the same transaction.

Guard semantics:
- A `GuardRegistry` maps `GuardId → async callable(session, cycle, command_ctx) → GuardResult(ok, reasons[])`.
- An **unregistered guard fails closed** with reason `GUARD_NOT_IMPLEMENTED:<id>`.
- Phase 01 registers `repository_ready_with_canonical_commit`. It passes only when the cycle's Repository has `status = READY`, its canonical RepositoryWorkspace has `state = READY`, and `canonical_commit` is set. Otherwise it fails with `REPOSITORY_NOT_BOUND`, `REPOSITORY_NOT_READY:<status>` or `WORKSPACE_NOT_READY:<state>`.
- Effect `pin_base_sha` runs inside the same transaction after the guards pass. It sets `delivery_cycles.base_sha := repositories.canonical_commit` (re-pinned on re-entry, e.g. after `revise_spec_delta`) and records the pinned SHA in the transition's domain event and audit row. This is the one way a cycle obtains its base revision (README §5.9.4).
- Tests use the `guard_override` fixture. Production code must never call that override.

Cycle ↔ repository binding:
- `create_delivery_cycle` binds `repository_id` to the Project's Repository when it is omitted (one per Project, Q-11).
- `GREENFIELD_BUILD` on a Project without a Repository declares one: `source_type=GREENFIELD_MANAGED`, `provider=LOCAL`, `status=PROVISIONING`, plus a PENDING canonical RepositoryWorkspace at `projects/<project_id>/repo`. This happens in the same transaction and emits `repository.declared`, which Phase 04's materializer consumes.
- `GREENFIELD_BUILD` on a Project whose Repository has a `released_commit`, or is `EXTERNAL_CLONE`, is rejected with 409 `GREENFIELD_REQUIRES_UNRELEASED_MANAGED_REPOSITORY`. Every other cycle type requires a bound Repository and otherwise returns 422 `REPOSITORY_REQUIRED`.

### Repository machine

| From | To | Command / trigger | Authority |
|---|---|---|---|
| — | PROVISIONING | `create_delivery_cycle(GREENFIELD_BUILD)` declaration | SYSTEM (inside the command) |
| — | CLONING | `register_repository` (EXTERNAL_CLONE) | HUMAN (OPERATOR) / INTEGRATION |
| PROVISIONING / CLONING | READY | `record_materialization` (registered_sha, canonical_commit, revision #1 `MATERIALIZED`) | SYSTEM (Phase 04 materializer; test helper before 04) |
| PROVISIONING / CLONING | ERROR | `materialization_failed` (reason) | SYSTEM |
| READY | SYNCING | `sync_started` | SYSTEM (Phase 16) |
| SYNCING | READY / ERROR | `sync_completed` / `sync_failed` | SYSTEM (Phase 16) |
| ERROR | PROVISIONING / CLONING | `retry_materialization` (when `registered_sha` is null, by `source_type`) | HUMAN (OPERATOR) / SYSTEM |
| ERROR | SYNCING | `retry_sync` (when `registered_sha` is set) | HUMAN (OPERATOR) / SYSTEM |

No state other than READY satisfies a code-needing guard. `canonical_commit` never changes through this machine. It changes only through `RepositoryRevisionService`, which requires `status ∈ {READY, SYNCING}` for every cause except `MATERIALIZED`.

### Task machine (Phase 01 defines; later phases call)

| From | To | Command / trigger | Authority |
|---|---|---|---|
| DRAFT | READY | `mark_ready` (issued contract, deps complete, required approvals approved) | TaskService (SYSTEM/HUMAN) |
| DRAFT | BLOCKED | `mark_ready` when deps or approvals are incomplete | TaskService |
| BLOCKED | READY | `unblock` (dependency completed / approval decided / clarification answered) | TaskService (SYSTEM) |
| READY | QUEUED | scheduler admission | Scheduler (Phase 03) only |
| QUEUED | RUNNING | execution started | ExecutionService (Phase 03) |
| RUNNING | COMPLETED | execution completed with validated outputs | ExecutionService |
| RUNNING | READY | retriable execution failure, attempts < max | ExecutionService |
| RUNNING | FAILED | attempts exhausted / non-retriable | ExecutionService |
| RUNNING | BLOCKED | execution checkpointed | ExecutionService |
| FAILED | READY | `retry_task` | HUMAN |
| COMPLETED | STALE / REVALIDATION_REQUIRED | inputs superseded | StalenessService (Phase 13) |
| STALE / REVALIDATION_REQUIRED | READY | new contract version issued | TaskService |
| any non-terminal | CANCELLED | `cancel_task` | HUMAN |

Illegal transitions include DRAFT→RUNNING, READY→COMPLETED, COMPLETED→RUNNING, any AGENT-actor command and any edge not listed. All are rejected with `409 IllegalTransition` and an audit record of the rejection (`audit_events.action = "transition.rejected"`).

### TaskContract machine
DRAFT → ISSUED (`issue_contract`: validates the body, computes the hash, supersedes the previous ISSUED version) → SUPERSEDED (on the next issue). A DRAFT may be edited (`PUT` body) only while DRAFT. ISSUED is immutable.

### Approval machine
PENDING → APPROVED | REJECTED | CHANGES_REQUESTED (HUMAN with APPROVER role only). PENDING → EXPIRED | CANCELLED (SYSTEM). A consumer guard must verify that `approval.subject_hash` equals the current subject hash. If it differs, the approval is treated as missing.

### Transition service (TECH §7.1)

```python
async def transition(
    session,
    aggregate: Literal["delivery_cycle", "task", "task_contract", "repository"],
    id,
    expected_state,
    command,
    ctx: CommandContext,
) -> TransitionResult:
    row = await lock_for_update(session, aggregate, id)  # SELECT ... FOR UPDATE
    if row.state != expected_state:
        raise StateConflict(current=row.state)
    edge = machine_for(row).edge(row.state, command)  # IllegalTransition if None
    authorize(edge, ctx.actor)  # Unauthorized if actor kind not allowed
    results = [await registry.evaluate(g, session, row, ctx) for g in edge.guards]
    if any(not r.ok for r in results):
        raise GuardFailed(reasons=...)
    before = snapshot_fields(row)
    apply(row, edge.to)
    row.state_version += 1
    for effect in edge.effects:
        await effects.run(effect, session, row, ctx)  # e.g. pin_base_sha
    append_domain_event(session, ...)
    append_audit(session, before, after, ctx)
    # commit by caller's unit of work; outbox publishes after commit
```

## 8. API / Contract Changes

Auth: `Authorization: Bearer <token>` on every endpoint except `/health` and `/ready`. Mutations accept the `Idempotency-Key` header.

| Method | Path | Notes |
|---|---|---|
| POST | `/projects` | `{key,name,description}` |
| GET | `/projects`, `/projects/{id}` | |
| POST | `/projects/{id}/repositories` | Register an external repository: `{name, source_type: "EXTERNAL_CLONE", provider, remote_url, default_branch?, credential_ref?}` → 201 Repository in `CLONING` + PENDING workspace. In Phase 01 only `provider=LOCAL` with a `file://` URL is accepted. Phase 16 enables `GITHUB`/`GITEA`. `GITLAB`/`BITBUCKET` → 422 `PROVIDER_NOT_SUPPORTED`. 409 if the Project already has a Repository (Q-11). `GREENFIELD_MANAGED` cannot be registered (it is only declared by a GREENFIELD cycle). |
| GET | `/projects/{id}/repositories`, `/repositories/{id}` | Repository metadata + `workspace {id, workspace_type, storage_backend, logical_location, materialized_commit, state}` + `credential_ref` + `credential_status`. Never a physical path or a credential value. |
| GET | `/repositories/{id}/revisions` | Append-only canonical revision history (`sequence, commit_sha, cause, integration_candidate_id?, release_id?, repository_event_id?, canonical_index_version_id?, created_at`) |
| POST | `/projects/{id}/delivery-cycles` | `{type, objective, repository_id?}` → initial state |
| GET | `/projects/{id}/delivery-cycles`, `/delivery-cycles/{id}` | includes `allowed_commands` with guard evaluation preview |
| POST | `/delivery-cycles/{id}/commands/{command}` | `{expected_state, payload?}` → 200 / 409 (state conflict or illegal) / 422 (guard failed with reasons) / 403 |
| POST | `/delivery-cycles/{id}/tasks` | create Task (DRAFT); `origin=CONTROL_PLANE` allowed for HUMAN/SYSTEM |
| GET | `/delivery-cycles/{id}/tasks`, `/tasks/{id}` | |
| POST | `/tasks/{id}/dependencies` | `{depends_on_task_id}`; rejects cycles (DFS) |
| POST | `/tasks/{id}/commands/{command}` | `mark_ready`, `cancel_task`, `retry_task` |
| POST | `/tasks/{id}/contracts` | create DRAFT contract (manual; Phase 06 adds compiler) |
| PUT | `/task-contracts/{id}` | edit DRAFT only |
| POST | `/task-contracts/{id}/commands/issue` | DRAFT → ISSUED |
| GET | `/tasks/{id}/contract`, `/tasks/{id}/contracts` | current issued version / history |
| POST | `/delivery-cycles/{id}/approvals` | request approval `{approval_type, subject_type, subject_id, subject_version}` |
| GET | `/approvals?status=PENDING`, `/approvals/pending`, `/approvals/{id}` | |
| POST | `/approvals/{id}/decision` | `{decision: APPROVED|REJECTED|CHANGES_REQUESTED, note}`; HUMAN+APPROVER |
| GET | `/delivery-cycles/{id}/events` | paginated by `sequence` |
| GET | `/delivery-cycles/{id}/events/stream` | SSE; `Last-Event-ID` resume by sequence |
| GET | `/audit?target_type=&target_id=` | |
| GET | `/policy/current` | active policy version |

Domain events introduced: `project.created`, `repository.registered`, `repository.declared`, `repository.status_changed`, `repository.canonical_advanced` (`{from_sha, to_sha, cause, sequence, refs}`), `repository.canonical_reverted`, `delivery_cycle.created`, `delivery_cycle.transitioned`, `task.created`, `task.ready`, `task.blocked`, `task.cancelled`, `task_contract.issued`, `task_contract.superseded`, `approval.requested`, `approval.decided`, `command.rejected`.

Internal service interfaces (used by later phases):

```python
class CommandBus:   async def dispatch(self, cmd: Command, ctx: CommandContext) -> CommandResult
class TransitionService: async def transition(...)  # above
class TaskService:  async def create_task(...); async def mark_ready(...); async def on_dependency_completed(task_id)
class ContractService: async def create_draft(task_id, body, compiled_by, inputs_hash=None); async def issue(contract_id, ctx)
class ApprovalService: async def request(...); async def decide(...); async def is_satisfied(approval_type, subject_type, subject_id, subject_hash) -> bool
class PolicyService: def current() -> PolicyVersion; def approval_required(approval_type, context) -> bool; def get(path, default)
class GuardRegistry: def register(guard_id, fn); async def evaluate(guard_id, ...)

class RepositoryService:
    async def register_external(project_id, name, provider, remote_url, default_branch, credential_ref, ctx) -> Repository
    async def declare_managed(project_id, ctx) -> Repository                          # called by create_delivery_cycle(GREENFIELD_BUILD)
    async def record_materialization(repository_id, sha, default_branch, ctx) -> RepositoryRevision   # SYSTEM; once per repository
    async def get_view(repository_id) -> RepositoryView                               # no paths, no secret values

class RepositoryRevisionService:                       # single writer of canonical_commit / released_commit (README §5.9.5)
    async def advance(repository_id, to_sha, cause: RevisionCause, refs: RevisionRefs,
                      expected_current: str | None, ctx) -> RepositoryRevision        # StateConflict if canonical_commit != expected_current
    async def mark_released(repository_id, sha, release_id, ctx) -> RepositoryRevision  # requires sha == canonical_commit; sets released_commit
    async def revert(repository_id, to_sha, reverts_revision_id, reason, ctx) -> RepositoryRevision  # cause REVERTED

class WorkspaceLocator:                                # the only logical→physical mapping (README §5.7)
    def canonical_location(project_id) -> str          # "projects/<project_id>/repo"
    def execution_location(project_id, execution_key) -> str   # "projects/<project_id>/worktrees/<EX-key>"
    def resolve(backend: str, logical_location: str) -> Path   # confinement: result must stay under the configured root (realpath)

class GitInspector:                                    # read-only; runs against a resolved canonical workspace
    def commit_exists(path, sha) -> bool; def is_ancestor(path, a, b) -> bool; def resolve_ref(path, ref) -> str
```

## 9. Services / Modules

| Path | Responsibility |
|---|---|
| `core/domain/<aggregate>/models.py` | SQLAlchemy models (one package per aggregate: `actors`, `projects`, `repositories`, `delivery_cycles`, `tasks`, `approvals`, `policy`, `events`) |
| `core/domain/<aggregate>/schemas.py` | Pydantic API/domain schemas |
| `core/domain/<aggregate>/repository.py` | data access; enforces the immutability guard |
| `core/domain/events.py` | event type registry + `append_domain_event` |
| `core/domain/audit.py` | `append_audit` |
| `core/domain/sequences.py` | per-project key generator |
| `core/domain/canonical_json.py` | canonical JSON + sha256 |
| `core/repositories/service.py` | `RepositoryService` (register external, declare managed, record materialization, credential_ref/remote_url validation, views) |
| `core/repositories/revision.py` | `RepositoryRevisionService`, emits `repository.canonical_advanced` / `.canonical_reverted` |
| `core/repositories/workspace_locator.py` | `WorkspaceLocator` (`OLYMPUS_WORKSPACE_ROOT` / `OLYMPUS_WORKTREE_ROOT`, confinement) |
| `core/repositories/git_inspect.py` | read-only `GitInspector` (Phase 04 builds the full Git wrapper beside it) |
| `core/state/machines.py`, `guards.py`, `transition_service.py` | machines, registry, transitions |
| `core/commands/bus.py`, `registry.py`, `command_log.py`, `context.py` | command dispatch, idempotency, `CommandContext(actor, correlation_id, idempotency_key)` |
| `core/policy/policy_service.py`, `config/policy/default.yaml` | policy load + hash + version persistence |
| `core/observability/outbox.py` | post-commit publisher (polling `published_at IS NULL` + in-process notify) |
| `apps/control_api/auth.py` | bearer token → Actor |
| `apps/control_api/routers/{projects,repositories,delivery_cycles,tasks,contracts,approvals,events,audit,policy}.py` | REST |
| `apps/control_api/sse.py` | SSE endpoint |
| `apps/control_api/cli/seed_actor.py` | `python -m apps.control_api.cli.seed_actor --kind HUMAN --name lead --roles OPERATOR,APPROVER` prints a token |

`config/policy/default.yaml` (initial):

```yaml
version: 1
approvals_required: {SCOPE: true, ARCHITECTURE: true, ARCHITECTURE_DELTA: true, IMPLEMENTATION_SPEC: true,
  SPEC_DELTA: true, SPEC_DECISION: true, REPAIR_SPEC: true, PROMOTION: true, FINDING_WAIVER: true, RELEASE: true, READINESS: false}
execution: {max_attempts: 3, lease_ttl_s: 120, heartbeat_s: 30}
risk_tiers: {R0: {}, R1: {}, R2: {require_action_approval: [repository.merge_candidate]}, R3: {require_action_approval: ["*mutating*"]}}
repository:
  canonical_advance_on: INTEGRATION_READY     # only supported value in the MVP (README §5.9.5)
  materialization: {max_size_mb: 512, submodules: DENY, lfs: DENY, max_attempts: 3}
  external_sync: {adopt_fast_forward: true, rewrite: REQUIRE_HUMAN_ACK}   # consumed in Phase 16 (Q-10)
```

## 10. Development Tasks

- [ ] 01.1 Implement `canonical_json` + `sha256_hex` with unit tests (key order, unicode, datetime/UUID handling).
- [ ] 01.2 Add the actors/api_tokens models, token hashing and the `seed_actor` CLI.
- [ ] 01.3 Add the projects, project_sequences, repositories, repository_workspaces and repository_revisions models plus migration `0001`, with the CHECK constraints from §6 and `UNIQUE(project_id)` on repositories.
- [ ] 01.4 Implement the per-project sequence generator (row lock on `project_sequences`).
- [ ] 01.5 Add the delivery_cycles model (state validated against the machine for its type).
- [ ] 01.6 Add the tasks, task_dependencies and task_contracts models plus migration `0002`, including the partial unique index for ISSUED.
- [ ] 01.7 Add the approvals, policy_versions and command_log models plus migration `0003`.
- [ ] 01.8 Add domain_events, audit_events and the `olympus_forbid_mutation()` trigger function, and attach it to audit_events, policy_versions, domain_events (all columns except `published_at`), repository_revisions and ISSUED task_contracts. Add `olympus_repository_revision_guard` on repositories. Create the `delivery_cycle_events` view. Migration `0004`.
- [ ] 01.9 Encode every machine in §7 as data in `core/state/machines.py`, with a self-check that every edge's `to` is a declared state and that terminal states have no outgoing edges.
- [ ] 01.10 Implement the `GuardRegistry` (fail-closed), the `RequiredGuard` placeholders for every guard ID in §7, the guard `repository_ready_with_canonical_commit` and the effect `pin_base_sha`.
- [ ] 01.11 Implement the `TransitionService` with row locking, expected-state check, actor authorization, guards, events and audit in the caller's transaction. Rejected transitions write a `transition.rejected` audit row in a **separate** short transaction.
- [ ] 01.12 Implement the `CommandBus` with registry, `command_log` idempotency (replay returns the stored result; the same key with a different request hash returns 422) and correlation propagation.
- [ ] 01.13 Implement `TaskService`: create, dependency add with cycle detection, `mark_ready` (computes READY vs BLOCKED), `on_dependency_completed` and cancel/retry.
- [ ] 01.14 Implement `ContractService`: draft create/edit, `issue` (validate `TaskContractBody`, hash, supersede previous, set `task.current_contract_id`).
- [ ] 01.15 Implement `ApprovalService`: request, decide (HUMAN+APPROVER only, otherwise 403 + audit), `is_satisfied` with subject-hash check, and events.
- [ ] 01.16 Implement `PolicyService`: load YAML, persist a `policy_versions` row when the hash is new, `current()`.
- [ ] 01.17 Implement the outbox publisher and the SSE endpoint, with resume support via `Last-Event-ID`.
- [ ] 01.18 Implement bearer auth and actor resolution, then add every router in §8 using command semantics only.
- [ ] 01.19 Implement the repository metadata services in `core/repositories/`:
  - `RepositoryService`: external registration with provider, `remote_url` and `credential_ref` validation; Greenfield declaration from `create_delivery_cycle`; `record_materialization`; views that never contain paths or secret values.
  - `RepositoryRevisionService`: advance, mark_released and revert with an `expected_current` check under `SELECT … FOR UPDATE`. It inserts the revision before the repository update and emits events.
  - The Repository machine in `core/state/machines.py`.
  No Git process is started by this task.
- [ ] 01.20 Implement `WorkspaceLocator` (root from settings, optional worktree-root override, realpath confinement) and the read-only `GitInspector` in `core/repositories/git_inspect.py`. Add the test helper `tests/fixtures/repositories.py::materialize_fixture_repository(session, project, fixture_dir) -> (Repository, sha)`. It commits the fixture into a temp **origin**, registers it as `EXTERNAL_CLONE`/`LOCAL`/`file://`, runs `git clone --bare` into the locator-resolved canonical location from the test process, and calls `record_materialization`. Phase 04 swaps the test-side clone for `RepositoryMaterializationService` and keeps the signature.
- [ ] 01.21 Write the tests in §12.

## 11. LLM-Dependent Tasks

No LLM dependency in this phase.

## 12. Testing Strategy

### Unit Tests
- `tests/unit/state/test_machines.py`: every listed edge is accepted, and every other (state, command) pair is rejected, enumerated exhaustively from the machine definitions.
- `test_guard_registry.py`: an unregistered guard fails closed with `GUARD_NOT_IMPLEMENTED`.
- `test_task_contract_body.py`: `extra="forbid"`, frozen, and canonical hash stability across key order.
- `test_dependency_cycles.py`: A→B→C→A is rejected.
- `tests/unit/repositories/test_workspace_locator.py`:
  - logical locations for canonical and execution workspaces;
  - `..`, absolute paths, drive letters and symlink escapes are rejected;
  - `OLYMPUS_WORKTREE_ROOT` override mapping;
  - the same logical location resolves under two different roots, proving there is no host path in the domain.
- `test_repository_validation.py`:
  - every `credential_ref` scheme is accepted;
  - secret-shaped values are rejected with `CREDENTIAL_VALUE_REJECTED` (`ghp_…`, `glpat-…`, a PEM block, a 40-char random string, `https://user:pw@host/x.git` as `remote_url`);
  - `GITLAB`/`BITBUCKET` → `PROVIDER_NOT_SUPPORTED`.

### Persistence Tests
- `test_transition_atomicity.py`: inject an exception after the state update but before commit. The DB then has no state change, no domain event and no audit row.
- `test_concurrent_transition.py`: two sessions run the same transition concurrently. Exactly one succeeds and the other gets `StateConflict`.
- `test_contract_immutability.py`: a raw SQL `UPDATE task_contracts SET body=...` on an ISSUED row raises from the trigger, while ISSUED → SUPERSEDED is allowed.
- `test_audit_immutable.py`: UPDATE/DELETE on `audit_events` raises.
- `test_idempotency.py`: the same `Idempotency-Key` creates one DeliveryCycle. The same key with a different body returns 422.
- `test_sequences.py`: concurrent key generation has no duplicates.
- `test_repository_revision_integrity.py`:
  - a raw `UPDATE repositories SET canonical_commit=…` without a matching latest revision raises;
  - UPDATE/DELETE on `repository_revisions` raises;
  - `registered_sha` cannot change once set;
  - an absolute `logical_location` violates the CHECK;
  - a second Repository for the same Project violates `UNIQUE(project_id)`;
  - `status='READY'` with a null `canonical_commit` violates the CHECK.
- `test_revision_service.py`:
  - `advance` with a stale `expected_current` raises `StateConflict`;
  - two concurrent advances from the same revision result in exactly one success;
  - `mark_released` with a SHA ≠ `canonical_commit` is rejected;
  - sequence numbers are gap-free.

### Integration Tests (API)
- Create project → create GREENFIELD cycle (state DISCOVERY). The same transaction declares Repository `GREENFIELD_MANAGED`/`LOCAL`/`PROVISIONING` with a PENDING workspace at `projects/<project_id>/repo`. `start_product_modeling` then returns 422 `GUARD_NOT_IMPLEMENTED:product_source_ingested` (fail-closed proof).
- Register an external repo (`EXTERNAL_CLONE`, `file://` temp origin) → `CLONING`. A BROWNFIELD cycle's `start_code_index` returns 422 `REPOSITORY_NOT_READY:CLONING`. After `materialize_fixture_repository`, it returns 200, and the cycle's `base_sha` equals `canonical_commit` equals the origin HEAD.
- `GET /repositories/{id}` and `/revisions`:
  - no value in any response contains the resolved workspace root, an absolute path or the test credential value;
  - `credential_ref` is returned as the reference name only.
- Approval decision by a VIEWER or AGENT token returns 403 plus an audit row. Decision by an APPROVER returns 200 and emits `approval.decided`.
- SSE receives `delivery_cycle.transitioned` after commit, and resumes from `Last-Event-ID`.

### Security Tests
- Unauthenticated → 401. Revoked token → 401.
- No route accepts a `state` or `status` field in a request body. A schema introspection test over the OpenAPI document asserts this.

### Commands
```
make migrate && make lint && make typecheck
uv run pytest -m "unit or persistence or integration" tests/unit/state tests/integration/control_plane
```

## 13. Milestone

Through the authenticated REST command API, an operator creates a Project, registers an external repository (or has a GREENFIELD cycle declare a managed one) as control-plane metadata with a logical canonical workspace and a guarded, append-only canonical revision history, opens DeliveryCycles of each type, drives permitted transitions and creates Tasks with immutable, versioned TaskContracts. Illegal, unauthorized and unguarded transitions are rejected. Every accepted transition commits atomically with its domain and audit events, and duplicate idempotent commands never duplicate state.

## 14. Acceptance Criteria

- [ ] All five DeliveryCycle types start in their defined initial state, and exhaustive tests prove that only listed edges are accepted.
- [ ] An illegal lifecycle transition is rejected with 409 and audited as `transition.rejected`.
- [ ] A guard that is not yet implemented fails closed (422 `GUARD_NOT_IMPLEMENTED`).
- [ ] A state change, its domain event and its audit event commit in one transaction (failure injection proves all-or-nothing).
- [ ] Concurrent identical transitions result in exactly one success.
- [ ] An ISSUED TaskContract cannot be modified (application guard **and** DB trigger). A new version supersedes it, and history is retained.
- [ ] Task dependency cycles are rejected.
- [ ] Approvals can be decided only by HUMAN actors with the APPROVER role, and are pinned to subject version and hash.
- [ ] A duplicate `Idempotency-Key` does not create a duplicate DeliveryCycle, Task or transition.
- [ ] No API accepts a direct lifecycle `state`/`status` field (OpenAPI assertion).
- [ ] The SSE stream delivers post-commit events and resumes by sequence.
- [ ] Project and DeliveryCycle are distinct tables, and a Project holds multiple cycles.
- [ ] Repository is a single entity for both `GREENFIELD_MANAGED` (declared by a GREENFIELD cycle) and `EXTERNAL_CLONE` (registered) sources. It records provider, remote_url, default_branch, status, `credential_ref`, `registered_sha` and `canonical_commit`, and it is bound to exactly one Project.
- [ ] The canonical RepositoryWorkspace is persisted with a logical location only. `WorkspaceLocator` resolves it under the configured `OLYMPUS_WORKSPACE_ROOT`, and no repository or workspace row or API response contains a physical path.
- [ ] Only `credential_ref` is persisted. Secret-shaped values and `remote_url` userinfo are rejected, and no API returns a credential value.
- [ ] `canonical_commit` changes only through `RepositoryRevisionService`. Every change appends an immutable `repository_revisions` row, and a raw SQL update without one is rejected by the DB.
- [ ] Code-needing cycle transitions fail with `REPOSITORY_NOT_READY` until the Repository is READY. On success, they pin `delivery_cycles.base_sha` to `canonical_commit`.

## 15. Exit Criteria

- All §14 criteria pass in CI, and migrations 0001–0004 upgrade and downgrade cleanly.
- `TransitionService`, `CommandBus`, `TaskService`, `ContractService`, `ApprovalService`, `PolicyService`, `GuardRegistry`, `RepositoryService`, `RepositoryRevisionService` and `WorkspaceLocator` interfaces are stable and documented in module docstrings, because later phases depend on them.
- `STATUS.md` is updated (Phase 01 COMPLETE, invariants "Project and DeliveryCycle are distinct" and "TaskContract is versioned" checked).

## 16. Dependencies

### Depends On
- 00: DB, config and harness.

### Blocks
- 02 (ModelCall correlation to tasks/contract schema), 03, 04 (Repository/RepositoryWorkspace to materialize), 07 (Repository entity, `WorkspaceLocator`, fixture materialization helper) and all later phases.

### Can Run In Parallel With
- None.

## 17. Risks / Implementation Notes

- **Trigger and ORM interplay:** SQLAlchemy may emit UPDATEs for unchanged columns. Use `passive_updates` and only flush changed attributes. Test with raw SQL as well as the ORM.
- **Guard placeholders:** later phases must register real guards and delete the placeholder entries. Phase exit checklists include "no `RequiredGuard` remains for this phase's guard IDs".
- **REMEDIATION cycle type:** included because the prompt lists it "where applicable". No MVP journey requires a standalone remediation cycle (Q-07).
- **Outbox polling:** acceptable for the MVP. Use `LISTEN/NOTIFY` as an optimization only.
- **Repository before materialization:** between Phase 01 and Phase 04, Repositories stay in `PROVISIONING`/`CLONING` unless the test helper materializes them. This is intended: it proves the guards fail closed. The helper's test-side `git clone --bare` is test code only and must not be imported by production modules (import-linter contract `tests` → `core` only).
- **One Repository per Project** (`UNIQUE(project_id)`) is an MVP restriction (Q-11). Relaxing it later requires a cycle-level repository selection and per-repository base pins, but no change to the entity shape.
- **`remote_url` for LOCAL external sources** is a user-supplied `file://` identity of the *external* source, not an Olympus storage location. It is never resolved by `WorkspaceLocator`, and it is never written to.
- **Deferred:** run-scoped worker tokens (Phase 04) and webhook auth (Phases 05/16).

## 18. Deliverables

- Code: `core/domain/*`, `core/state/*`, `core/commands/*`, `core/policy/*`, `core/repositories/{service,revision,workspace_locator,git_inspect}.py`, `core/observability/outbox.py`, `apps/control_api/{auth.py,sse.py,routers/*,cli/seed_actor.py}`; test helper `tests/fixtures/repositories.py`.
- Migrations: `0001`–`0004`.
- APIs: §8 endpoints. Events: §8 list.
- Config: `config/policy/default.yaml`.
- Tests: §12 suites.
- Docs: module docstrings for the public service interfaces.
