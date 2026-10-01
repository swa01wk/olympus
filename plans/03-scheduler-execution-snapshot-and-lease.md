# Phase 03 — Scheduler, Execution, Snapshot, Lease and Execution Worker

## 1. Objective

Implement the deterministic execution spine from ARCH §7 and TECH §8.3/§9:

- **scheduler eligibility** (a pure function) and **atomic admission** (`FOR UPDATE SKIP LOCKED`);
- **Execution** records with the full Execution state machine;
- immutable, hashed **ExecutionSnapshots**;
- single-owner **Leases** with heartbeat and expiry recovery;
- the **execution worker** flow with `AGENT_RUNTIME` and `DETERMINISTIC` executors;
- typed, content-addressed **Artifacts**;
- **Checkpoint / Clarification / Resume** built from a durable continuation package;
- **retry-as-new-Execution** semantics.

The milestone runs a READY ANALYSIS Task through a live AgentRuntime, survives worker restart, and keeps failed attempts as immutable history.

## 2. Architectural Context

- **Position:** Execution plane (Scheduler → Execution Worker → Agent Runtime).
- **Upstream:** 01 (Task, TaskContract, policy, approvals, transition service) and 02 (AgentRuntime, ModelRouter).
- **Downstream:** 04 (worktrees and ToolGateway bind to Execution + Lease), 05/06/09/11/12/15 (agent work runs as Executions), 08 (INTEGRATION deterministic executor) and 10 (RELEASE executor).
- **Lifecycle:** Task READY → QUEUED → RUNNING → COMPLETED/FAILED/BLOCKED. Execution QUEUED → LEASED → STARTED → CHECKPOINTED? → OUTPUT_PRODUCED → VALIDATING → COMMITTED → COMPLETED, with FAILED / TIMED_OUT / CANCELLED / STALE.
- **Invariants:** 7–10 (Execution = one attempt; retry → new Execution; failed history immutable; immutable snapshot), 12–13 (deterministic eligibility; the agent doesn't authorize itself), 36 (restart keeps canonical state) and the D-12 Task-origin rule.

## 3. Current Repository Assessment

Inspection on 2026-10-01: none of this exists.

### Existing
- (after 01/02) Task/TaskContract/Approval/Policy services and AgentRuntime — **RETAIN/EXTEND**. The Task machine edges for QUEUED/RUNNING are defined in 01 and now get their authoritative callers.

### Partial
- `apps/scheduler_worker`, `apps/execution_worker` loop skeletons (Phase 00) — **EXTEND**.

### Missing
- Executions, snapshots, leases, artifacts, checkpoints, clarifications, eligibility, admission, worker flow, executors and recovery — **ADD**.

### Refactor / Migration Required
- `model_calls.execution_id` gets an FK to `executions.id` (migration `0006`) — **EXTEND**.

## 4. Scope

1. Tables: executions, execution_snapshots, execution_leases, artifacts, checkpoints, clarifications and execution_events.
2. `eligibility.evaluate(task, ctx) → EligibilityResult(eligible, reasons[])` implementing ARCH §7.1 exactly:
   - `task.status == READY`;
   - dependencies COMPLETED;
   - required artifacts exist;
   - the contract version matches;
   - required approvals exist;
   - no blocking policy;
   - no conflicting execution.
3. Admission service: `SELECT … FOR UPDATE SKIP LOCKED LIMIT :batch`, then evaluate, then in the same transaction create the Execution (QUEUED, pinned `task_contract_id`), set Task → QUEUED and emit events.
4. `RefResolver` registry, so "required artifacts exist" and "contract version matches" are checkable for each `VersionedRef.ref_type`. Phase 03 registers ARTIFACT and TASK_CONTRACT. Later phases register spec types.
5. Snapshot builder: deterministic canonical JSON from ARCH §7.2 (base commit, spec/AC versions, architecture/contract versions, artifact versions, policy version, risk, baseline versions, TaskContract version, canonical index version) plus a sha256 `snapshot_hash`. The base commit resolver honours `base_policy` (D-14).
6. Lease manager: claim (`SKIP LOCKED` on QUEUED executions), heartbeat, release, expiry sweeper and a recovery policy.
7. Worker flow (TECH §9.1), with executor selection by `contract.executor_kind`.
8. `AgentRuntimeExecutor`: builds the `AgentRunRequest` from contract + snapshot + context, invokes the runtime and maps the result to Execution transitions.
9. `DeterministicExecutor` registry (`register_deterministic_executor(name, fn)`). Phase 03 ships `noop.verify_artifact` for tests.
10. Output validation: each `required_outputs` entry is checked by a registered validator, for example `artifact:<kind>` requires an Artifact of that kind with a schema-valid body.
11. Artifact store: content-addressed files under `$OLYMPUS_STORAGE_ROOT/artifacts/sha256/..` plus an `artifacts` row (kind, schema name/version, hash, size, execution_id, inline small JSON).
12. Checkpoint, Clarification and Continuation:
    - `CHECKPOINT_REQUESTED` → persist the Checkpoint, Clarification or Approval request and the produced artifacts → Execution CHECKPOINTED → Task BLOCKED → release the lease and runtime compute.
    - On resolution, apply the resume policy: **same Execution resumes** if the snapshot inputs are unchanged, or a **new Execution** with a new snapshot if authoritative inputs changed (ARCH §7.3).
    - The continuation package is built only from durable state.
13. Retry: a failed or timed-out Execution stays immutable. If `attempts < max_attempts` and the failure is retriable, Task → READY and the scheduler creates a new Execution.
14. Cancellation: `POST /executions/{id}/cancel` → runtime `cancel` → CANCELLED → Task CANCELLED or READY per the command option.
15. Execution APIs and SSE events.

## 5. Out of Scope

- Worktrees, the Git wrapper, ToolGateway and candidate commits (Phase 04). The `COMMITTED` state is defined here but used only by CODE_CHANGE in Phase 04.
- Spec/architecture `RefResolver`s (Phases 05/06).
- Dependency-integration base resolution for multi-dependency tasks. Phase 03 supports `NONE`, `EXPLICIT_SHA`, `CYCLE_BASE` and a single dependency's candidate commit. Multi-dependency is rejected as ineligible with reason `BASE_RESOLVER_UNAVAILABLE` until Phase 08.

### Do Not Change
- No LLM may participate in eligibility or admission.
- Never UPDATE a terminal Execution's status or a snapshot row.
- A retry must never reuse an existing Execution record.

## 6. Domain / Data Model Changes

Migration `0006_p03_executions_snapshots_leases_artifacts.py`:

```python
class ExecutionStatus(StrEnum):
    QUEUED = "QUEUED"
    LEASED = "LEASED"
    STARTED = "STARTED"
    CHECKPOINTED = "CHECKPOINTED"
    OUTPUT_PRODUCED = "OUTPUT_PRODUCED"
    VALIDATING = "VALIDATING"
    COMMITTED = "COMMITTED"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    TIMED_OUT = "TIMED_OUT"
    CANCELLED = "CANCELLED"
    STALE = "STALE"


class Execution(Base, UUIDPkMixin, TimestampMixin):
    __tablename__ = "executions"
    key: Mapped[str]  # EX-001
    task_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("tasks.id"), index=True)
    delivery_cycle_id: Mapped[uuid.UUID] = mapped_column(index=True)
    task_contract_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("task_contracts.id")
    )  # pinned ISSUED version
    attempt_number: Mapped[int]
    status: Mapped[ExecutionStatus]
    executor_kind: Mapped[str]
    agent_profile: Mapped[str | None]
    snapshot_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("execution_snapshots.id"))
    previous_execution_id: Mapped[uuid.UUID | None]  # retry / resume lineage
    failure_class: Mapped[
        str | None
    ]  # LEASE_EXPIRED | RUNTIME_ERROR | VALIDATION_FAILED | TIMEOUT | BUDGET | POLICY_DENIED ...
    failure_detail: Mapped[dict | None] = mapped_column(JSONB)
    retriable: Mapped[bool | None]
    output: Mapped[dict | None] = mapped_column(
        JSONB
    )  # validated structured output reference/summary
    runtime_metadata: Mapped[dict | None] = mapped_column(
        JSONB
    )  # NON-AUTHORITATIVE (langgraph ids)
    started_at: Mapped[datetime | None]
    finished_at: Mapped[datetime | None]
    __table_args__ = (
        UniqueConstraint("task_id", "attempt_number"),
        Index(
            "uq_one_active_exec_per_task",
            "task_id",
            unique=True,
            postgresql_where=text(
                "status IN ('QUEUED','LEASED','STARTED','OUTPUT_PRODUCED','VALIDATING','COMMITTED')"
            ),
        ),
    )


class ExecutionSnapshot(Base, UUIDPkMixin, TimestampMixin):
    __tablename__ = "execution_snapshots"
    execution_id: Mapped[uuid.UUID] = mapped_column(unique=True)
    task_contract_id: Mapped[uuid.UUID]
    task_contract_version: Mapped[int]
    task_contract_hash: Mapped[str]
    base_commit: Mapped[str | None]
    repository_id: Mapped[uuid.UUID | None]
    policy_version_id: Mapped[uuid.UUID]
    risk_tier: Mapped[str]
    content: Mapped[dict] = mapped_column(JSONB)  # SnapshotContent (below)
    snapshot_hash: Mapped[str] = mapped_column(index=True)


class SnapshotContent(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    task: dict  # id, key, work_type, origin
    task_contract: dict  # id, key, version, content_hash
    base_commit: str | None
    base_resolution: dict  # policy + inputs used
    spec_versions: list[VersionedRef] = []  # FeatureSpec/Req/AC (Phase 05+)
    architecture_versions: list[VersionedRef] = []
    implementation_spec_versions: list[VersionedRef] = []
    artifact_versions: list[VersionedRef] = []
    baseline_versions: list[VersionedRef] = []  # Phase 12+
    canonical_index_version_id: uuid.UUID | None = None  # Phase 07/08+
    repository: dict | None = (
        None  # {repository_id, workspace_id, canonical_commit, revision_sequence} at snapshot time (README §5.9)
    )
    policy_version: dict
    risk_tier: str
    approvals: list[dict] = []  # approval id, type, subject hash
```

Other tables:
- `execution_leases`: id, execution_id, worker_id, acquired_at, heartbeat_at, expires_at, released_at, state (ACTIVE|RELEASED|EXPIRED). Partial unique index on `execution_id WHERE state='ACTIVE'`.
- `artifacts`: id, key, project_id, delivery_cycle_id?, execution_id?, kind, schema_name, schema_version, content_hash, size_bytes, storage_ref, inline JSONB?, created_by_actor_id. `UNIQUE(content_hash, execution_id, kind)`. Immutable.
- `checkpoints`: id, execution_id, reason (CLARIFICATION|APPROVAL|EXTERNAL_DEPENDENCY|RECONCILIATION), pending_ref_type, pending_ref_id, continuation JSONB (`ContinuationPackage`), runtime_checkpoint_ref (non-authoritative), created_at, resolved_at, resolution (RESUME_SAME|NEW_EXECUTION|CANCELLED).
- `clarifications`: id, key, project_id, delivery_cycle_id, execution_id?, question, context JSONB, options JSONB, blocking bool, status (OPEN|ANSWERED|CANCELLED), answer, answered_by_actor_id, answered_at.
- `execution_events`: id, execution_id, seq, type, payload JSONB, at. This persists `AgentEvent`s for observability; it is not authoritative.

Immutability triggers:
- `execution_snapshots`: all columns.
- `artifacts`: all columns.
- `executions`: once `status ∈ {COMPLETED, FAILED, TIMED_OUT, CANCELLED, STALE}`, no column may change.

`ContinuationPackage` (built from durable state only):

```python
class ContinuationPackage(BaseModel):
    execution_id: uuid.UUID
    task_contract_ref: VersionedRef
    snapshot_hash: str
    produced_artifacts: list[VersionedRef]
    progress_summary: str  # summary produced by runtime, stored as artifact
    pending: dict  # question/approval ref
    resolution: dict | None  # answer / decision once resolved
    decisions: list[VersionedRef] = []  # KnowledgeItem DECISION refs (Phase 05+)
    candidate_state: dict | None = None  # worktree branch/HEAD (Phase 04)
```

## 7. State / Lifecycle Changes

Execution machine (owner: `ExecutionService`, used by the scheduler and worker only):

| From | To | Trigger | Guard |
|---|---|---|---|
| (new) | QUEUED | admission | eligibility OK, contract ISSUED, no active execution for task (unless `allow_parallel_executions`) |
| QUEUED | LEASED | worker claim | lease acquired |
| LEASED | STARTED | snapshot + workspace ready | snapshot persisted; Task → RUNNING |
| LEASED | QUEUED | lease expired before start | requeue same execution (no work started); `lease_attempts += 1` |
| STARTED | CHECKPOINTED | runtime `CHECKPOINT_REQUESTED` | checkpoint + pending record persisted; Task → BLOCKED; lease released |
| CHECKPOINTED | STARTED | resume (inputs unchanged) | resolution present; new lease |
| CHECKPOINTED | STALE | resume with changed inputs | a **new** Execution is created with a new snapshot (`previous_execution_id` set) |
| STARTED | OUTPUT_PRODUCED | runtime output | output schema-valid |
| OUTPUT_PRODUCED | VALIDATING | worker | — |
| VALIDATING | COMMITTED | writable work type only (Phase 04) | candidate commit persisted |
| VALIDATING / COMMITTED | COMPLETED | all `required_outputs` validators pass | Task → COMPLETED; dependents unblocked |
| STARTED / OUTPUT_PRODUCED / VALIDATING | FAILED | runtime error / validation failure / lease expiry after start | failure_class set; Task → READY (retriable, attempts < max) or FAILED |
| STARTED | TIMED_OUT | wall-clock timeout | runtime cancelled |
| any non-terminal | CANCELLED | cancel command (HUMAN) | runtime cancelled |
| QUEUED / LEASED | STALE | contract superseded before start | new contract required |

Rules:
- Illegal examples: COMPLETED→anything, FAILED→STARTED (retry must be a new Execution) and an AGENT actor triggering any edge.
- Lease rules: only the lease holder's `worker_id` may advance the execution. Every worker transition includes `lease_id` and checks it is ACTIVE and unexpired inside the transaction.

## 8. API / Contract Changes

| Method | Path | Notes |
|---|---|---|
| POST | `/tasks/{id}/executions` | **request scheduling**: runs the same admission service for this task; 201 with Execution or 409 with eligibility reasons (ARCH §20 endpoint, semantics kept deterministic) |
| GET | `/tasks/{id}/executions` | attempts history |
| GET | `/tasks/{id}/eligibility` | explain eligibility (reasons) |
| GET | `/executions/{id}` | includes snapshot hash, contract version, lease, status history |
| GET | `/executions/{id}/snapshot` | snapshot content + hash |
| GET | `/executions/{id}/events` | execution_events (SSE variant `/stream`) |
| GET | `/executions/{id}/artifacts`, `/artifacts/{id}`, `/artifacts/{id}/content` | |
| GET | `/executions/{id}/model-calls` | |
| POST | `/executions/{id}/cancel` | `{then: "CANCEL_TASK"|"RETURN_TO_READY"}` HUMAN |
| GET | `/clarifications?status=OPEN`, `/clarifications/{id}` | |
| POST | `/clarifications/{id}/answer` | HUMAN; records answer; triggers resume evaluation |

Events: `task.queued`, `execution.created`, `execution.leased`, `execution.started`, `execution.checkpointed`, `execution.output_produced`, `execution.completed`, `execution.failed`, `execution.timed_out`, `execution.cancelled`, `execution.stale`, `lease.expired`, `artifact.created`, `clarification.requested`, `clarification.answered`.

Internal interfaces:

```python
def evaluate(task: TaskView, ctx: EligibilityContext) -> EligibilityResult   # pure, no I/O; ctx preloaded
class AdmissionService:  async def admit_batch(limit: int) -> list[uuid.UUID]; async def admit_task(task_id) -> Execution
class SnapshotBuilder:   async def build(execution) -> ExecutionSnapshot     # deterministic
class BaseCommitResolver(Protocol): async def resolve(contract, task, session) -> BaseResolution
class LeaseManager:      async def claim(worker_id) -> Lease | None; async def heartbeat(lease); async def release(lease); async def sweep_expired()
class Executor(Protocol): async def execute(ctx: ExecutionContext) -> ExecutorOutcome
class OutputValidatorRegistry: def register(output_name_pattern, fn)
class ArtifactStore:     async def put(kind, schema, content: bytes|dict, execution_id) -> Artifact
class ResumeService:     async def on_resolution(checkpoint_id) -> ResumeDecision
class RefResolver(Protocol): async def exists(ref: VersionedRef) -> bool; async def is_current(ref) -> bool
```

## 9. Services / Modules

| Path | Responsibility |
|---|---|
| `core/domain/executions/{models,schemas,repository}.py` | Execution, lease, checkpoint, clarification, events |
| `core/domain/artifacts/{models,repository}.py` + `core/execution/artifacts.py` | artifact rows + content-addressed store |
| `core/scheduler/eligibility.py`, `admission.py`, `refs.py` | pure eligibility; admission; RefResolver registry |
| `core/execution/service.py` | Execution state machine (data in `core/state/machines.py`, extended) |
| `core/execution/snapshots/builder.py`, `base_commit.py` | snapshot + base resolution (D-14) |
| `core/execution/leases/manager.py`, `sweeper.py` | lease claim/heartbeat/expiry |
| `core/execution/worker.py` | flow orchestration |
| `core/execution/executors/{base,agent_runtime_executor,deterministic,registry}.py` | executors |
| `core/execution/validation.py` | required-output validators |
| `core/execution/checkpoints.py`, `continuation.py`, `resume.py` | checkpoint/resume |
| `apps/scheduler_worker/main.py` | loop: `admit_batch` every `poll_interval`; `sweep_expired` |
| `apps/execution_worker/main.py` | loop: claim → run → heartbeat task (asyncio) |
| `apps/control_api/routers/{executions,clarifications,artifacts}.py` | REST |

## 10. Development Tasks

- [ ] 03.1 Add the models and migration `0006`, the triggers and the FK on `model_calls.execution_id`.
- [ ] 03.2 Add the Execution machine to `core/state/machines.py` and the `ExecutionService` transitions with lease checks.
- [ ] 03.3 Implement the `RefResolver` registry with ARTIFACT and TASK_CONTRACT resolvers.
- [ ] 03.4 Implement the pure `eligibility.evaluate` with explicit reason codes (`NOT_READY`, `DEPENDENCY_INCOMPLETE:<key>`, `ARTIFACT_MISSING:<ref>`, `CONTRACT_VERSION_MISMATCH`, `APPROVAL_MISSING:<id>`, `POLICY_BLOCKED:<rule>`, `CONFLICTING_EXECUTION:<key>`, `BASE_RESOLVER_UNAVAILABLE`, `REPOSITORY_NOT_READY:<status>`, `BASE_COMMIT_UNAVAILABLE:<sha>`). The two repository reasons are part of the "required artifacts exist" condition: a task with `repository_id` needs its Repository READY and its resolved base commit present in the canonical workspace. They do not add an eighth condition.
- [ ] 03.5 Implement `AdmissionService.admit_batch` (`SKIP LOCKED`) and `admit_task`, atomically creating the Execution and moving Task → QUEUED.
- [ ] 03.6 Implement the `BaseCommitResolver` for NONE, EXPLICIT_SHA, CYCLE_BASE and a single dependency:
  - `CYCLE_BASE` resolves to `delivery_cycles.base_sha`, which is pinned from `Repository.canonical_commit` by Phase 01's `pin_base_sha` effect;
  - a null `base_sha`, or a Repository that is not READY, produces `REPOSITORY_NOT_READY`;
  - a SHA missing from the canonical workspace (checked with Phase 01's `GitInspector.commit_exists`) produces `BASE_COMMIT_UNAVAILABLE`;
  - the snapshot records `repository {repository_id, workspace_id, canonical_commit, revision_sequence}`.
  Candidate commits of other tasks are never a base, except through the single-dependency rule. Multi-dependency bases come from an IntegrationCandidate in Phase 08.
- [ ] 03.7 Implement `SnapshotBuilder` (canonical JSON; the same inputs give the same hash) and persist it at LEASED → STARTED.
- [ ] 03.8 Implement `LeaseManager` (claim with `SKIP LOCKED` on QUEUED, heartbeat, release) and the sweeper applying the §7 recovery rules.
- [ ] 03.9 Implement `ArtifactStore` and the artifact repository.
- [ ] 03.10 Implement the executor registry, `AgentRuntimeExecutor` and the `DeterministicExecutor` with `noop.verify_artifact`.
- [ ] 03.11 Implement the output validator registry and the `artifact:<kind>` validator.
- [ ] 03.12 Implement the worker flow with a heartbeat coroutine, wall-clock timeout, cancellation propagation and graceful shutdown that leaves the lease to expire so a restart recovers.
- [ ] 03.13 Implement checkpoints, clarifications, the continuation builder and the `ResumeService` (same vs new Execution).
- [ ] 03.14 Implement retry handling (Task → READY or FAILED) and dependent-task unblocking on COMPLETED (`TaskService.on_dependency_completed`).
- [ ] 03.15 Add the APIs and events.
- [ ] 03.16 Write the tests in §12, including a live diagnostic run.

## 11. LLM-Dependent Tasks

| Item | Detail |
|---|---|
| Why | Proves the worker → AgentRuntime → ModelRouter path inside a governed Execution |
| Task | `origin=CONTROL_PLANE`, `work_type=ANALYSIS`, `agent_profile=diagnostic.structured_echo`, `required_outputs=["artifact:DIAGNOSTIC_SUMMARY"]`, input `VersionedRef(ARTIFACT)` holding fixture text |
| Context source | the artifact referenced in the contract, resolved through the snapshot |
| Output schema | `DiagnosticSummary` (Phase 02) |
| Runtime / alias | `LangGraphRuntime` / `verification_planning` |
| Validation | schema + `artifact:DIAGNOSTIC_SUMMARY` validator |
| Retries | ModelRouter retries; execution-level retry creates a new Execution |
| Failure handling | Execution FAILED with `failure_class=RUNTIME_ERROR` or `VALIDATION_FAILED`; Task READY/FAILED per attempts |
| Cost logging | `model_calls.execution_id` set |
| Live test | `tests/integration/live_llm/test_execution_spine_live.py` |
| Clarification live test | profile `diagnostic.ask_question`: the prompt instructs the model to return `CHECKPOINT_REQUESTED` with a question when the input is marked ambiguous. Validates the checkpoint → answer → resume path with a real model. |

## 12. Testing Strategy

### Unit Tests
- Eligibility: one test per reason code, including `REPOSITORY_NOT_READY` (Repository CLONING) and `BASE_COMMIT_UNAVAILABLE` (a fixture canonical workspace without the SHA, via `materialize_fixture_repository`). Every reason path is deterministic (property test: same input, same output).
- Snapshot hash stability: shuffled input order gives the same hash, and a changed AC version gives a different hash.
- Execution machine: exhaustive allowed and illegal pairs.

### Persistence Tests
- Admission concurrency: two schedulers admit the same READY task simultaneously, producing exactly one Execution (`SKIP LOCKED` plus the partial unique index).
- Lease exclusivity: two workers claim simultaneously, and one wins.
- Snapshot immutability: UPDATE raises from the trigger.
- Terminal Execution immutability: UPDATE of a FAILED row raises.
- Retry: after a failure, a new Execution with `attempt_number=2` and `previous_execution_id` exists, and attempt 1 is unchanged.

### Workflow Tests (deterministic executor)
- A blocked Task (incomplete dependency) is never admitted. When the dependency completes, it is unblocked and admitted.
- A Task requiring an approval is ineligible until it is APPROVED. A REJECTED approval keeps it ineligible.
- Cancellation mid-run produces CANCELLED, and the Task follows the requested option.

### Failure / Recovery Tests (`recovery`)
- Kill the worker (task cancellation without lease release) after LEASED, before STARTED. The sweeper requeues the same Execution, and a new worker completes it.
- Kill the worker after STARTED. The lease expires, the Execution is FAILED(`LEASE_EXPIRED`), and a new Execution completes. Both rows are queryable.
- Restart the control-api and workers mid-cycle. Task, Execution, Snapshot and Artifact rows are intact, and the scheduler resumes.
- Wall-clock timeout produces TIMED_OUT.

### Runtime / Live-LLM Tests
- The diagnostic ANALYSIS task runs end to end live: Execution COMPLETED, Artifact `DIAGNOSTIC_SUMMARY` present, and a `model_calls` row linked.
- The clarification path runs live: CHECKPOINTED → `/clarifications/{id}/answer` → resumed and COMPLETED. The same Execution is used when inputs are unchanged.
- Truncating the `langgraph_runtime` schema while CHECKPOINTED still lets resume complete from the continuation package.

### Commands
```
make check
uv run pytest -m "workflow or recovery" tests/workflow/execution
LLM_LIVE_TESTS=1 uv run pytest -m live_llm --live-required tests/integration/live_llm/test_execution_spine_live.py
```

## 13. Milestone

A READY ANALYSIS Task with an ISSUED TaskContract is deterministically admitted. It receives an immutable, hashed ExecutionSnapshot and a single-owner lease, and runs through `LangGraphRuntime → ModelRouter` against a live provider to produce a validated, content-addressed Artifact. Worker kill or restart, lease expiry, retry, cancellation and clarification checkpoint/resume all preserve complete immutable execution history.

## 14. Acceptance Criteria

- [ ] Eligibility is a pure deterministic function implementing all seven ARCH §7.1 conditions with explicit reasons.
- [ ] A blocked Task cannot execute.
- [ ] Concurrent schedulers create at most one active Execution per Task.
- [ ] Only one worker holds a lease at a time, workers heartbeat, and expired leases are recovered per the §7 rules.
- [ ] Every Execution has exactly one immutable snapshot whose hash is reproducible from its content.
- [ ] Retry produces a new Execution, and the failed Execution remains immutable and queryable.
- [ ] A checkpoint persists the pending question and continuation. Resume works without LangGraph checkpoint data.
- [ ] Resume with changed authoritative inputs creates a new Execution with a new snapshot.
- [ ] Restarting workers or the API does not lose Task, Execution, Snapshot, Artifact or Clarification state.
- [ ] A live provider is used for the milestone run (a `model_calls` row with `provider_request_id`).
- [ ] No LLM is invoked during eligibility or admission (asserted: no `model_calls` rows created by the scheduler process).
- [ ] A Task bound to a repository is ineligible (`REPOSITORY_NOT_READY` / `BASE_COMMIT_UNAVAILABLE`) until its Repository is READY and the resolved base commit exists in the canonical RepositoryWorkspace. Its snapshot records the repository identity and the canonical revision it was resolved against.

## 15. Exit Criteria

- §14 is green in deterministic CI and the live suite has passed (evidence recorded).
- The `RefResolver`, `BaseCommitResolver`, executor registry and output-validator registry extension points are documented, because Phases 04–15 register into them.
- `STATUS.md` invariants "Task and Execution are distinct", "ExecutionSnapshot is immutable" and "runtime restart retains canonical state" (partial) are updated.

## 16. Dependencies

### Depends On
- 01: Task, TaskContract, Approval, Policy, transitions.
- 02: AgentRuntime, ModelRouter.

### Blocks
- 04, 05 and, transitively, everything downstream.

### Can Run In Parallel With
- 07 (Code Intelligence Index) only.

## 17. Risks / Implementation Notes

- **Concurrency risk:** combine `SKIP LOCKED` with the partial unique index. Never rely on one alone.
- **Clock skew:** compute lease expiry with DB `now()`, not worker clocks.
- **Long-running runtime calls:** the heartbeat must run concurrently. If a heartbeat fails (lease lost), the worker must cancel the runtime and stop writing.
- **Resume semantics:** "inputs unchanged" means a recomputed snapshot hash for the same contract equals the original. Otherwise a new Execution is created.
- **Deferred:** multi-dependency base resolution (Phase 08) and STALE marking due to spec changes (Phase 13).

## 18. Deliverables

- Code: `core/scheduler/*`, `core/execution/{service,worker,validation,artifacts,checkpoints,continuation,resume}.py`, `core/execution/{snapshots,leases,executors}/*`, `core/domain/{executions,artifacts}/*`, worker apps.
- Migration: `0006`.
- APIs/events: §8.
- Profiles: `diagnostic.ask_question`.
- Tests: unit, persistence, workflow, recovery, live suites.
