# Phase 10 — Release Eligibility, Release Manifest and the Greenfield Journey (R1)

## 1. Objective

This phase introduces:

- deterministic **Release Eligibility** (ARCH §12);
- immutable **ReleaseManifest**, **Release** and the **DeliveryOutcome** bundle;
- explicit human **release approval**;
- a governed **RELEASE execution** that fast-forwards the Repository's default branch in the canonical RepositoryWorkspace and tags the exact verified integrated SHA, which is already the canonical revision (Phase 08). It then records the `RELEASED` revision (`Repository.released_commit`) through `RepositoryRevisionService.mark_released` (README §5.9.5).

**Stratos** is a deterministic release executor (no eligibility authority). The released index pointer becomes the project baseline.

Then it proves **Journey 1 — Greenfield Build** end to end with live LLM calls: SupportDesk PRD → ProductSource → Capabilities/Features/FeatureSpecs/ACs → scope approval → Architecture → ImplementationSpecs → Task DAG → TaskContracts → Forge Executions → candidate commits → IC → canonical index → Warden → Sentinel → evidence → gates → eligibility → approval → **Release R1**.

## 2. Architectural Context

- **Position:** Governance plane (Release Eligibility, Human Approval) → Stratos. Final stage of every delivery journey.
- **Upstream:** 09 (gates, coverage, findings) and transitively 00–08.
- **Downstream:** 11 (Brownfield onboarding of the R1 repo), 13 (released index as impact baseline), 14/15 (R2/R3), 16 (deployment connector), 17 (Release view), 19.
- **Lifecycle:** GREENFIELD ASSURANCE → RELEASE → COMPLETE. Release DRAFT → ELIGIBLE → APPROVED → EXECUTING → RELEASED.
- **Invariants:**
  - 24: release eligibility is deterministic.
  - 25: approvals explicit.
  - The release manifest references the exact verified integrated commit.
  - Release authority is outside implementation agents.
  - 37: lineage includes Release.
  - LLM policy: journey proof uses live LLM for every model-dependent stage.

## 3. Current Repository Assessment

Inspection on 2026-10-01: none of this exists.

### Existing
- (after 01–09) the full Greenfield pipeline up to gates — **RETAIN**.
- (after 04) `git_local.fast_forward_ref`, `create_tag` — **RETAIN**.
- (after 09) finalizer hook `recompute_release_eligibility` (no-op) — **REPLACE** with real logic.

### Partial
- Guard `release_executed` is a placeholder — **REPLACE**.

### Missing
- Eligibility, manifests, releases, outcomes, Stratos, the release policy and the Greenfield journey test — **ADD**.

### Refactor / Migration Required
- `repository_index_pointers.released_index_version_id` is populated on release — **EXTEND**.

## 4. Scope

1. Tables: `release_eligibility_evaluations`, `releases`, `release_manifests`, `delivery_outcomes`.
2. `ReleaseEligibilityService.evaluate(cycle)`: a pure decision over loaded inputs, persisted as an evaluation row with each condition's result and reasons:

```python
release_eligible = (
    manifest_valid  # manifest draft validates; references current IC + integrated_sha
    and integration_candidate_is_current  # IC READY, not SUPERSEDED, latest for cycle, and Repository.canonical_commit == ic.integrated_sha
    and required_gates_pass  # policy.required_gates[cycle.type] all PASS for this IC
    and required_approvals_exist  # scope/architecture/impl-spec/spec-delta/etc. per cycle type, subject hash valid
    and required_executions_not_stale  # no COMPLETED CODE_CHANGE task in STALE/REVALIDATION_REQUIRED; all IC commits' executions COMPLETED
    and blocking_findings == 0  # OPEN/IN_REMEDIATION blocking findings for cycle
    and mandatory_acceptance_criteria_have_evidence  # every mandatory AC obligation SATISFIED for IC
    and required_behavioral_baselines_pass  # hook: no-op TRUE until Phase 12 registers baseline condition
)
```

   Conditions are registered in a `EligibilityConditionRegistry`, so 12/13/15 add `required_behavioral_baselines_pass`, impact obligations and reproduction/regression without editing the core function. The registry is fail-closed: a cycle type requiring a condition that is not registered yields `NOT_ELIGIBLE`.
3. Recompute triggers (deterministic, SYSTEM): `gate.finalized`, `finding.*`, `approval.decided`, `integration.*` and `task.stale`.
4. Release flow:
   1. `create_release(cycle)` → Release DRAFT with key `R<n>` (project sequence) + manifest draft.
   2. On ELIGIBLE → Release ELIGIBLE + Approval(RELEASE) requested (subject = manifest hash).
   3. HUMAN APPROVED → Release APPROVED.
   4. `execute_release` → RELEASE Task (CONTROL_PLANE, DETERMINISTIC executor `stratos.release`) → ToolGateway system actions in the canonical RepositoryWorkspace:
      - `git_local.fast_forward_ref refs/heads/<repository.default_branch> → integrated_sha`. This is ff-only: the current default-branch head must be an ancestor of `integrated_sha`, otherwise the release is FAILED + Finding;
      - `git_local.create_tag olympus/release/R1 integrated_sha`.
   5. In one transaction:
      - `RepositoryRevisionService.mark_released(repository_id, integrated_sha, release_id)` appends a `RELEASED` revision and sets `released_commit = integrated_sha`, which already equals `canonical_commit`;
      - the released index pointer is set;
      - Release → RELEASED;
      - the DeliveryOutcome is persisted;
      - the cycle → COMPLETE.
      If the transaction fails after the Git ref moves, the RELEASE execution is retried. The ff and tag actions are idempotent (already at target), so the retry converges.
5. Release eligibility is re-checked **inside** the RELEASE execution immediately before the ref update (TOCTOU guard). If no longer eligible, the release FAILS and the reasons are recorded.
6. ReleaseManifest content (immutable, hashed): project, cycle, IC key/SHA, repository (`{repository_id, name, source_type, provider, remote_url, default_branch, canonical_commit, canonical_revision_sequence}`; `canonical_commit == integrated_sha` is validated; no credential data and no filesystem path), canonical index version, FeatureSpec/ImplementationSpec versions, AC → evidence map, gates, approvals, findings summary (waived list), executions/candidate commits and policy version.
7. DeliveryOutcome bundle (ARCH §12.1) persisted at completion.
8. Lineage hop Release ← IC, and lineage queries now reach Release.
9. Stratos agent folder `agents/stratos/`: a deterministic executor profile (no LLM). Its deployment action is a no-op in this phase (deployment connector in 16; TECH §19 "Stratos deployment is optional for MVP proof").
10. Greenfield guards final check: no placeholders remain for GREENFIELD edges.
11. Journey test harness:
    - `tests/journey/conftest.py`: fresh DB, storage root and `OLYMPUS_WORKSPACE_ROOT`; seeded HUMAN approver actor; workers started in-process (`asyncio` tasks) or as subprocesses.
    - `tests/journey/helpers.py`: the API client, `wait_for(predicate, timeout)` and `assert_live_llm_proof(cycle_id, stages)` (README §6.3).
    - `tests/journey/test_greenfield_supportdesk.py`.

## 5. Out of Scope

- Remote deployment (Stratos deploy connector, 16).
- Baseline release conditions (12), impact obligations (13) and reproduction/regression (15). They are registered later.
- The UI (17).

### Do Not Change
- No agent can compute or override eligibility, approve releases or execute RELEASE actions (Forge policy denial from 04 remains).
- The default branch moves only via a `stratos.release` fast-forward to a verified integrated SHA (or a Phase 16 governed external adoption). `released_commit` changes only through `RepositoryRevisionService.mark_released`.

## 6. Domain / Data Model Changes

Migration `0020_p10_releases_manifests_outcomes.py` (TECH 011 completion).

```python
class ReleaseStatus(StrEnum):
    DRAFT = "DRAFT"
    ELIGIBLE = "ELIGIBLE"
    NOT_ELIGIBLE = "NOT_ELIGIBLE"
    APPROVED = "APPROVED"
    EXECUTING = "EXECUTING"
    RELEASED = "RELEASED"
    FAILED = "FAILED"
    SUPERSEDED = "SUPERSEDED"


class Release(Base, UUIDPkMixin, TimestampMixin):
    __tablename__ = "releases"
    key: Mapped[str]
    project_id: Mapped[uuid.UUID]
    delivery_cycle_id: Mapped[uuid.UUID]
    integration_candidate_id: Mapped[uuid.UUID]
    integrated_sha: Mapped[str]
    status: Mapped[ReleaseStatus]
    manifest_id: Mapped[uuid.UUID | None]
    approval_id: Mapped[uuid.UUID | None]
    release_execution_id: Mapped[uuid.UUID | None]
    tag: Mapped[str | None]
    released_at: Mapped[datetime | None]
    latest_eligibility_id: Mapped[uuid.UUID | None]
    __table_args__ = (UniqueConstraint("project_id", "key"),)


class ReleaseManifest(Base, UUIDPkMixin, TimestampMixin):
    __tablename__ = "release_manifests"
    release_id: Mapped[uuid.UUID]
    content: Mapped[dict] = mapped_column(JSONB)
    content_hash: Mapped[str]  # immutable


class ReleaseEligibilityEvaluation(Base, UUIDPkMixin, TimestampMixin):
    __tablename__ = "release_eligibility_evaluations"
    delivery_cycle_id: Mapped[uuid.UUID]
    integration_candidate_id: Mapped[uuid.UUID | None]
    eligible: Mapped[bool]
    conditions: Mapped[list] = mapped_column(JSONB)  # [{name, ok, reasons, inputs_hash}]
    policy_version_id: Mapped[uuid.UUID]
    trigger_event_id: Mapped[uuid.UUID | None]  # immutable


class DeliveryOutcome(Base, UUIDPkMixin, TimestampMixin):
    __tablename__ = "delivery_outcomes"
    delivery_cycle_id: Mapped[uuid.UUID] = mapped_column(unique=True)
    content: Mapped[dict] = mapped_column(JSONB)  # ARCH §12.1 shape
    result: Mapped[str]  # RELEASED | READY_FOR_CHANGE (Phase 12) | CANCELLED | FAILED
```

Manifest content (Pydantic `ReleaseManifestContent`, `extra="forbid"`):

```python
class ReleaseManifestContent(BaseModel):
    release_key: str
    project_key: str
    delivery_cycle_key: str
    cycle_type: str
    repository: dict
    integration_candidate: dict  # {key, integrated_sha, base_sha}
    canonical_index_version_id: uuid.UUID
    canonical_index_hash: str
    feature_specs: list[VersionedRef]
    implementation_specs: list[VersionedRef]
    architecture: VersionedRef | None
    acceptance: list[dict]  # [{ac_key, version, mandatory, evidence: [EV keys], status}]
    baselines: list[dict] = []  # Phase 12
    gates: dict[str, str]  # {WARDEN: PASS, SENTINEL: PASS, ...}
    approvals: list[str]
    waived_findings: list[str]
    blocking_findings: int
    executions: list[str]
    candidate_commits: list[str]
    policy_version: str
```

## 7. State / Lifecycle Changes

Release machine (owner `ReleaseService`):

| From | To | Trigger | Guard |
|---|---|---|---|
| (new) | DRAFT | `create_release` | cycle in RELEASE or ASSURANCE with current IC |
| DRAFT/NOT_ELIGIBLE | ELIGIBLE | eligibility recompute | `eligible == true` |
| DRAFT/ELIGIBLE | NOT_ELIGIBLE | eligibility recompute | `eligible == false` |
| ELIGIBLE | APPROVED | Approval(RELEASE) APPROVED | approval subject hash == manifest hash |
| APPROVED | EXECUTING | `execute_release` | still eligible |
| EXECUTING | RELEASED | `stratos.release` success | ff + tag succeeded; eligibility re-check passed; `RELEASED` revision recorded (`released_commit == canonical_commit == integrated_sha`) |
| EXECUTING | FAILED | non-ff / eligibility lost / connector failure | Finding created |
| any non-terminal | SUPERSEDED | new IC for cycle | — |

Rules:
- Approval REJECTED → Release stays ELIGIBLE (no auto re-request). The cycle can return to development through remediation.
- DeliveryCycle GREENFIELD:
  - ASSURANCE → RELEASE (`required_gates_pass`) is triggered by SYSTEM once gates PASS.
  - RELEASE → COMPLETE (`release_executed`: Release RELEASED for the current IC) is triggered by SYSTEM.

## 8. API / Contract Changes

| Method | Path | Notes |
|---|---|---|
| GET | `/delivery-cycles/{id}/release-eligibility` | latest evaluation with per-condition reasons; `?recompute=true` (SYSTEM/HUMAN) |
| POST | `/delivery-cycles/{id}/release` | create release (ARCH §20) |
| GET | `/releases/{id}`, `/projects/{id}/releases` | |
| GET | `/releases/{id}/manifest` | content + hash |
| POST | `/releases/{id}/approve` | HUMAN APPROVER; creates/decides Approval(RELEASE) (TECH §23) |
| POST | `/releases/{id}/execute` | HUMAN/SYSTEM; schedules RELEASE task |
| GET | `/delivery-cycles/{id}/outcome` | DeliveryOutcome |

Events: `release.created`, `release.eligible`, `release.blocked`, `release.approved`, `release.executing`, `release.executed`, `release.failed`, `delivery_outcome.recorded`.

## 9. Services / Modules

| Path | Responsibility |
|---|---|
| `core/release/eligibility.py` | pure decision + condition registry + persistence |
| `core/release/service.py` | Release lifecycle, approval wiring |
| `core/release/manifest.py` | manifest builder + validation |
| `core/release/outcome.py` | DeliveryOutcome builder |
| `core/release/triggers.py` | event subscriptions → recompute |
| `core/release/guards.py` | `release_executed` |
| `agents/stratos/{profile.py,executor.py}` | deterministic `stratos.release` executor |
| `core/assurance/gates.py` | EXTEND: hook calls `eligibility.recompute` |
| `core/intelligence/code_index/canonical.py` | EXTEND: set `released_index_version_id` |
| `apps/control_api/routers/releases.py` | REST |
| `tests/journey/{conftest,helpers}.py`, `tests/journey/test_greenfield_supportdesk.py` | journey |

## 10. Development Tasks

- [ ] 10.1 Add migration `0020` and the models, with immutability triggers on manifests, evaluations and outcomes.
- [ ] 10.2 Implement `EligibilityConditionRegistry` and the eight core conditions (the baseline condition is registered as an explicit TRUE stub labeled `NOT_APPLICABLE_UNTIL_PHASE_12` for GREENFIELD; Phase 12 replaces it for all cycle types that have baselines).
- [ ] 10.3 Implement eligibility persistence and the recompute triggers.
- [ ] 10.4 Implement the manifest builder and validator (`manifest_valid`).
- [ ] 10.5 Implement the Release lifecycle and Approval(RELEASE) pinned to the manifest hash.
- [ ] 10.6 Implement the `stratos.release` deterministic executor (eligibility re-check, ff-only of the Repository's default branch in the canonical RepositoryWorkspace, tag, `mark_released` revision, idempotent retry) via ToolGateway system actions under the `release` resource policy.
- [ ] 10.7 Set the released index pointer, write the DeliveryOutcome and run the cycle COMPLETE transition.
- [ ] 10.8 Replace the `release_executed` guard placeholder, and audit that no GREENFIELD guard placeholders remain.
- [ ] 10.9 Register the lineage hop Release.
- [ ] 10.10 Implement the journey harness and `assert_live_llm_proof`.
- [ ] 10.11 Write `test_greenfield_supportdesk.py` (§12).
- [ ] 10.12 Write the Greenfield run script `scripts/demo/greenfield.py` (drives the same API steps for manual demos; uses the HUMAN token for approvals).

## 11. LLM-Dependent Tasks

No new agent profiles. This phase **exercises** all Greenfield LLM-dependent stages live:

| Stage | Profile | Alias |
|---|---|---|
| Product decomposition | `kira.decompose` | `product_decomposition` |
| Architecture | `atlas.propose_architecture` | `architecture` |
| ImplementationSpecs | `kira.implementation_spec` | `planning` |
| Task plan | `kira.task_plan` | `planning` |
| Implementation | `forge` | `implementation` |
| Review | `warden.review` | `review` |
| Verification planning | `sentinel.plan` (+ `sentinel.summarize`) | `verification_planning` |

Eligibility, manifest and release are deterministic (no LLM). Cost: the journey test enforces `LLM_TEST_BUDGET_USD` (recommended ≥ $15 for the full journey; document the observed cost in `STATUS.md`).

## 12. Testing Strategy

### Unit Tests
- Eligibility truth table, one failing condition at a time. An unregistered required condition is NOT_ELIGIBLE.
- Manifest validation: wrong SHA, missing AC evidence and a superseded IC all fail.

### Persistence Tests
- Manifest, evaluation and outcome immutability.
- Approval(RELEASE) bound to a manifest hash. A changed manifest invalidates the approval.

### Git / Worktree Tests
- `stratos.release`:
  - ff-only success moves the default branch to `integrated_sha`, creates the tag `olympus/release/R1`, appends a `RELEASED` revision and sets `released_commit`;
  - when the default branch has diverged (an external commit is injected into the canonical workspace by the test), the release is FAILED with a Finding, and the default branch and `released_commit` are unchanged;
  - a crash after the ref move but before the DB commit: the retried execution converges with no duplicate revision row.
- An eligibility change between approval and execution causes the release to FAIL (TOCTOU test).

### Security Tests
- A Forge/AGENT token attempting `release` resource actions is DENIED.
- An AGENT token on `/releases/{id}/approve` gets 403.

### E2E / Journey Tests (`journey`, live, `--live-required`)
`test_greenfield_supportdesk.py` (single test, staged with explicit assertions):
1. Create Project `SUPPORTDESK`. Create GREENFIELD cycle DC-001. This declares the `GREENFIELD_MANAGED` Repository, which the materialization loop provisions: wait for READY and record `baseline_sha = registered_sha`. Upload `PRD.md`. `start_product_modeling`.
2. Decompose (live). Answer any blocking clarifications with deterministic scripted answers from `tests/fixtures/supportdesk/clarification_answers.yaml` (keyword-matched; a human-style input, not model output). Request and approve scope. `start_architecture`.
3. Atlas (live), then approve. `start_planning` (guard: repository READY; `base_sha` pinned to `baseline_sha`). ImplementationSpecs (live), then approve all. TaskPlan (live), then accept. `start_development`.
4. Wait for all tasks COMPLETED (live Forge; retries allowed within policy). `start_integration`, then IC READY and canonical index at integrated SHA.
5. Assurance: Warden (live), Sentinel plan (live) and execute, gates finalized. If blocking findings arise, the remediation loop runs (live) until PASS or the budget/attempt limit is hit (test fails with a diagnostic report).
6. Release: eligibility ELIGIBLE, approve (HUMAN), execute, RELEASED. Cycle COMPLETE.
7. Assertions:
   - `assert_live_llm_proof(DC-001, [decompose, architecture, implementation_spec, task_plan, forge, warden, sentinel_plan])`;
   - manifest `integrated_sha ==` default-branch HEAD `==` tag `==` released index pointer SHA `== Repository.canonical_commit == Repository.released_commit`;
   - the Repository was READY with `registered_sha = baseline_sha` before the first implementation Execution was created (`repository.materialized` event sequence < the first Forge `execution.created`), and every Forge snapshot's `base_commit` descends from `baseline_sha`;
   - the revision history is exactly `MATERIALIZED(baseline_sha)` → `INTEGRATION_READY(integrated_sha)` [→ further `INTEGRATION_READY` rows only for superseding remediation ICs] → `RELEASED(integrated_sha)`, and no candidate commit SHA appears in it;
   - every ExecutionWorkspace of a Forge execution is a distinct logical location under `projects/<project_id>/worktrees/`, and none equals the canonical location;
   - generated code is held in Git, not in the DB: three distinctive source lines from the generated `app/` files (read with `git show integrated_sha:<path>`) appear in no control-plane table, in a `pg_dump --data-only` grep that excludes the `model_calls` request/response audit columns and content-addressed artifact rows (evidence copies; README §5.9.1);
   - every mandatory AC has ≥1 allowed PASS evidence at that SHA;
   - `blocking_findings == 0`;
   - lineage forward from each Feature reaches Task → Execution → candidate commit → IC → principal code entity → test → Evidence → Release R1;
   - reverse lineage from a route handler reaches its ProductSource;
   - canonical/released index SHA == integrated SHA.
8. Restart check: stop and restart workers and the API, then re-query outcome, lineage and eligibility. The results are unchanged.

### Failure / Recovery Tests
- Kill the execution worker mid-Forge during the journey (opt-in env `JOURNEY_CHAOS=1`). The journey still completes with an additional FAILED execution in history.

### Commands
```
make check
LLM_LIVE_TESTS=1 uv run pytest -m journey --live-required tests/journey/test_greenfield_supportdesk.py -s
```

## 13. Milestone

**Journey 1 complete.** An uploaded SupportDesk PRD is transformed through the real control plane, with live LLM calls at every model-dependent stage, into approved FeatureSpecs, an approved Architecture and ImplementationSpecs, a compiled Task DAG, isolated Forge executions, an IntegrationCandidate with a canonical index, independent Warden/Sentinel assurance with evidence and deterministic gates, and a deterministically eligible, human-approved **Release R1**. Its manifest references the exact verified integrated SHA, and its lineage is queryable from PRD to code to evidence to release.

## 14. Acceptance Criteria

- [ ] Release eligibility is computed deterministically and persisted with per-condition reasons.
- [ ] A release cannot become eligible when mandatory evidence is missing, a gate is not PASS, a blocking finding exists, an approval is missing or the IC is not current.
- [ ] Release approval is an explicit HUMAN Approval pinned to the manifest hash.
- [ ] The release manifest references the exact verified `integrated_sha` and the repository's canonical revision. After release, the default branch, the release tag, `Repository.canonical_commit` and `Repository.released_commit` all point to it, and a `RELEASED` revision is recorded.
- [ ] In the Greenfield journey, the `GREENFIELD_MANAGED` repository is provisioned and its baseline SHA recorded before any implementation Execution. All Forge work happens in isolated ExecutionWorkspaces, and generated code is persisted only in Git, not as control-plane state.
- [ ] Eligibility is re-checked at execution time (TOCTOU protection).
- [ ] The released index pointer equals the release SHA.
- [ ] The DeliveryOutcome bundle is persisted with result RELEASED.
- [ ] The Greenfield journey test passes live, with `assert_live_llm_proof` covering all seven model-dependent stages.
- [ ] Forward and reverse lineage queries include Release R1.
- [ ] After a full restart, outcome, lineage and eligibility queries return identical results.

## 15. Exit Criteria

- §14 green. The journey test run ID, cost and duration are recorded in `STATUS.md`.
- Journey Readiness → Greenfield = COMPLETE (pending final re-run in 19).
- No guard placeholders remain for GREENFIELD_BUILD.
- `STATUS.md`: invariants "release eligibility is deterministic", "mocked LLM output is not used as journey proof" (Greenfield) and "Git/repository storage owns source-code bytes" checked; Greenfield Repository tracker and Assurance/Release revision binding tracker updated.

## 16. Dependencies

### Depends On
- 09.

### Blocks
- 11 (vertical-slice rule, ARCH §2: complete one journey before expanding breadth; the R1 repo is the Brownfield input in the chained demo).

### Can Run In Parallel With
- None.

## 17. Risks / Implementation Notes

- **Journey flakiness from model variance:** mitigate with retries within policy, remediation loops, small PRD scope and generous but bounded budgets. Never mitigate by canning outputs.
- **Clarification answers in the journey:** scripted human answers are inputs, not model outputs, so they are acceptable. Keep them generic (keyword → answer), and fall back to the "accept the default assumption" answer.
- **Cost and time:** a full live Greenfield run may take 20–60 minutes. Run it in the gated `live` CI job only.
- **Deferred:** the deployment action (16).

## 18. Deliverables

- Code: `core/release/*`, `agents/stratos/*`, hook wiring.
- Migration: `0020`.
- APIs/events: §8.
- Tests: unit, persistence, git, security and the Greenfield journey.
- Fixtures: `clarification_answers.yaml`.
- Scripts: `scripts/demo/greenfield.py`.
