# Phase 08 — IntegrationCandidate, Canonical Index Promotion and Product-to-Code Traceability

## 1. Objective

Converge candidate commits into one canonical **IntegrationCandidate** (IC) with an exact **integrated SHA** (ARCH §11.1, TECH §17). Then:

- advance the **canonical repository revision** (`Repository.canonical_commit`) to that SHA through `RepositoryRevisionService`. This is the only way development work changes the project's canonical code state (README §5.9.5);
- build the **canonical Code Intelligence Index** for that SHA;
- keep execution and candidate indexes **provisional and disposable**;
- record which code entities each execution changed (`changed_by`);
- materialize authoritative **SpecCodeLinks** (`origin=GENERATED_LINEAGE`) from Task → Execution → Commit lineage, following the principal-symbol granularity rule (ARCH §14.8);
- expose forward and reverse **lineage queries** (ARCH §13, §14.4–14.5; TECH §14).

Merge conflicts become **Findings** with remediation work, never silent autonomous resolution. This phase also provides the **dependency-integration base resolver** that dependent tasks need (D-14).

## 2. Architectural Context

- **Position:** Execution plane (Integration Candidate), Intelligence plane (canonical index) and Traceability.
- **Upstream:**
  - 04: candidate commits, `git_local.merge_candidates`, deterministic executor path.
  - 06: Task → ImplementationSpec lineage, task_spec_refs.
  - 07: indexer and stable keys.
  - 01: `RepositoryRevisionService`, `repository_revisions`.
- **Downstream:**
  - 09: assurance targets IC SHA, which equals the canonical revision.
  - 10: release references IC.
  - 11: Brownfield canonical index of a repository snapshot uses `CanonicalIndexService`.
  - 13: incremental re-index and link refresh.
  - 14/15: re-index after integration.
- **Lifecycle:** Greenfield/Feature/Bug DEVELOPMENT → INTEGRATION → ASSURANCE (or REGRESSION). IC states CREATED → INTEGRATING → VALIDATING → READY, plus CONFLICT / FAILED / SUPERSEDED.
- **Invariants:**
  - 15–17: candidate commits converge and do not independently become release candidates. Assurance targets the exact IC SHA.
  - 18–19: canonical index is tied to the integrated SHA. Candidate indexes are distinguishable and provisional.
  - Candidate commits do not change the canonical project revision. The canonical revision changes only through this governed integration flow (or the 10/16 causes in README §5.9.5).
  - 37: lineage is queryable.
  - SpecCodeLink origin and confidence distinguish authoritative lineage from discovered mappings.

## 3. Current Repository Assessment

Inspection on 2026-10-01: none of this exists.

### Existing
- (after 03) `BaseCommitResolver` without multi-dependency support — **EXTEND**.
- (after 04) `candidate_commits`, `git_local` — **EXTEND** (`merge_candidates`, `prepare_dependency_base`).
- (after 07) `CodeIndexer` — **RETAIN**, used by `CanonicalIndexService`.

### Partial
- Guards `all_code_tasks_completed`, `ic_ready_and_canonical_index_current` and `remediation_tasks_exist` (INTEGRATION side) are placeholders — **REPLACE**.

### Missing
- IntegrationCandidate, integration executor, findings (minimal), canonical pointers, entity changes, SpecCodeLinks and the lineage service — **ADD**.

### Refactor / Migration Required
- None.

## 4. Scope

1. Tables: `integration_candidates`, `integration_candidate_commits`, `findings` (base schema; Phase 09 extends usage), `repository_index_pointers`, `code_entity_changes`, `spec_code_links`.
2. IC creation:
   - The command `create_integration_candidate(cycle_id)` (SYSTEM after the `start_integration` transition, or HUMAN via API) selects the latest COMPLETED candidate commit of every CODE_CHANGE task in the cycle. It ignores superseded ones and leaf-only commits where ancestry already includes upstream.
   - It records a deterministic ordering (topological order of the Task DAG, tie-broken by task key) and creates an INTEGRATION Task (CONTROL_PLANE, `executor_kind=DETERMINISTIC`, `deterministic_executor=integration.merge`) plus its contract and admission.
   - **Integration base:** `ic.base_sha := Repository.canonical_commit` at creation. It equals `cycle.base_sha` unless the canonical revision advanced meanwhile (for example an adopted external fast-forward, Phase 16). `cycle.base_sha` must be an ancestor of or equal to it, otherwise the IC is FAILED with `BASE_NOT_ANCESTOR_OF_CANONICAL` plus a Finding. Integrating onto the current canonical revision ensures that advancing to `integrated_sha` never drops canonical history.
   - **Canonical revision lock (Q-12):** creation is rejected with 409 `CANONICAL_REVISION_HELD` while another cycle holds an unreleased canonical revision. "Held" means the repository's latest revision has cause `INTEGRATION_READY`, with an IC from a different cycle that is neither released nor reverted. A new IC in the **same** cycle (after remediation) is allowed and supersedes the previous one.
3. `integration.merge` deterministic executor:
   1. Validate that all commits descend from `cycle.base_sha`, and that `cycle.base_sha` is an ancestor of `ic.base_sha` (`git merge-base --is-ancestor`).
   2. Create a branch `olympus/integration/<IC-key>` from `ic.base_sha` in a SYSTEM ExecutionWorkspace (`projects/<project_id>/worktrees/<integration EX-key>`).
   3. Merge each candidate in order (`git merge --no-ff --no-edit`; commits that are already ancestors are skipped).
   4. On conflict: abort, IC → CONFLICT, and create a Finding(`source=INTEGRATION`, `category=MERGE_CONFLICT`, conflicting files + task keys) plus a remediation Task (origin REMEDIATION referencing the Finding and the original ImplementationSpecs; contract compiled with `allowed_scope` = conflicting files ∪ original scopes; base = partial integration head). No autonomous conflict resolution.
   5. Run integration checks via `test.run`: `python -m compileall`, `pytest --collect-only` and the full `pytest -q`. Results are stored as an artifact. Failing checks → IC FAILED + Finding(`category=INTEGRATION_CHECK_FAILED`).
   6. Persist `integrated_sha` and set IC → VALIDATING.
4. Canonical index promotion (`CanonicalIndexService.promote_ic`):
   1. Build a CANONICAL index (`source=INTEGRATION_CANDIDATE`, `scope_ref=IC-key`) at `integrated_sha`.
   2. Compute `code_entity_changes`.
   3. Materialize SpecCodeLinks.
   4. Move `repository_index_pointers.canonical_index_version_id` to the new version (previous → SUPERSEDED for canonical role only if it was an IC index not released).
   5. Advance the canonical repository revision: `RepositoryRevisionService.advance(repository_id, to_sha=integrated_sha, cause=INTEGRATION_READY, refs={integration_candidate_id, canonical_index_version_id, delivery_cycle_id}, expected_current=ic.base_sha)`. This requires policy `repository.canonical_advance_on == INTEGRATION_READY`. It sets `Repository.canonical_commit = integrated_sha` and appends a `repository_revisions` row.
   6. IC → READY.
   7. Emit `code_index.updated`, `repository.canonical_advanced` and `integration.ready`.
   Steps 3–7 run in **one transaction** after the index build. If index building fails, the IC stays VALIDATING with a Finding. If the canonical revision moved after IC creation (`StateConflict` on `expected_current`), the transaction rolls back and the IC → SUPERSEDED with a Finding `CANONICAL_MOVED_DURING_INTEGRATION`. A new IC is then created from the new canonical revision.

   Worked example (README §5.9.5): EX-221 → AAA, EX-222 → BBB and EX-223 → CCC are candidate commits on `olympus/EX-22x`. None of them is canonical, appears in `repository_revisions`, or is pointed to by `repository_index_pointers`. IC-003 merges them on `olympus/integration/IC-003` and produces `integrated_sha = DEF`. Only at IC-003 READY does `canonical_commit` become DEF (revision cause `INTEGRATION_READY`, `integration_candidate_id = IC-003`). The canonical index pointer then references the CANONICAL index at DEF, Warden/Sentinel (09) target DEF, and Release R2 (10) references IC-003 / DEF.
4a. **Canonical revision revert:** when a cycle becomes CANCELLED or FAILED while its IC holds an unreleased canonical revision, `CanonicalRevisionGuardian` (subscribed to `delivery_cycle.transitioned`) runs `RepositoryRevisionService.revert` back to the repository's default-branch head. That head is the last `MATERIALIZED`/`RELEASED`/`EXTERNAL_SYNC` revision, because only those causes move the default branch. The guardian also restores `repository_index_pointers.canonical_index_version_id` to the latest READY CANONICAL index version at that SHA (or clears it if none exists, e.g. a Greenfield baseline) and sets the IC → SUPERSEDED, all in one transaction, emitting `repository.canonical_reverted`. The integration branch is retained for audit.
5. Candidate (provisional) indexes: `CanonicalIndexService.build_candidate(execution)` builds a CANDIDATE index (`source=EXECUTION`, `scope_ref=EX-key`) of the candidate commit plus its base index (cached). Both are read from Git objects in the canonical object store, never from the ExecutionWorkspace's working tree. These are used to compute per-execution changed entities. After IC READY, candidate indexes for that IC's executions are set to DISCARDED, and their rows are deleted by a retention sweeper after N days, keeping the `code_entity_changes` derived from them.
6. `code_entity_changes`: for each candidate commit, diff the candidate index against its base index by `stable_key` (ADDED / MODIFIED by content_hash / DELETED) → rows `(stable_key, change_kind, execution_id, task_id, candidate_commit_sha, ic_id, integrated_sha)`. Entities in the canonical index whose stable_key appears inherit execution lineage.
7. SpecCodeLink materialization (ARCH §14.4, §14.8; TECH §14.1):
   - **Principal symbols** = changed entities of type ROUTE, CLASS, ORM_MODEL, SCHEMA, TABLE and public top-level FUNCTION, plus public METHODs of classes that Forge declared in `ImplementationResult.principal_symbols`. Private helpers (`_x`) and non-declared methods are excluded; they inherit context structurally.
   - For each principal symbol changed by task T: create a link `IMPLEMENTS` from T's ImplementationSpec version **and** its FeatureSpec version, with `origin=GENERATED_LINEAGE`, `confidence=1.0`, and the task_id, execution_id, commit_sha and evidence refs.
   - For each TEST entity changed by T and mapped in `ImplementationResult.ac_test_mapping` (validated: the test must exist in the canonical index): create a `VERIFIES` link from the AC version to the test entity.
   - A declared principal symbol that is absent from the canonical index creates a Finding (`LINEAGE_DECLARATION_MISMATCH`, MINOR).
8. `DependencyBaseResolver` (D-14): for tasks with multiple completed dependencies, deterministically merge their candidate commits into an ephemeral `olympus/depbase/<task-key>-<n>` branch (via `git_local`, SYSTEM). The SHA is recorded in the snapshot's `base_resolution`. A conflict makes the task ineligible with `DEPENDENCY_BASE_CONFLICT` and creates a Finding.
9. Lineage service and APIs: forward (Feature → … → code entities/tests) and reverse (code entity → specs → feature → capability → product source; plus `changed_by` executions/commits). Evidence and release hops are added by 09/10 via extension hooks.
10. Guards:
    - `all_code_tasks_completed`: every IMPLEMENTATION_PLAN/REMEDIATION/REPAIR CODE_CHANGE task is COMPLETED or CANCELLED with an approval.
    - `ic_ready_and_canonical_index_current`: latest IC READY, the canonical pointer's `commit_sha == ic.integrated_sha`, **and** `Repository.canonical_commit == ic.integrated_sha`.
    - `remediation_tasks_exist` (INTEGRATION → DEVELOPMENT): an open INTEGRATION Finding has ≥1 READY/QUEUED remediation task.
11. Context enrichment for the compiler (06 extension): for CODE_CHANGE tasks in non-greenfield cycles, or when a canonical index exists, add `inputs` refs to the canonical index version and a bounded list of relevant entity stable keys (from the ImplementationSpec's `file_scope`), so Forge gets structural context through `repo.read`.

## 5. Out of Scope

- Warden/Sentinel, evidence and gates (09).
- Incremental re-index and link refresh across versions (13). This phase does full builds.
- DISCOVERED links (11) and HUMAN_CONFIRMED promotion (12).
- Remote push/PR of the integration branch (16).

### Do Not Change
- Never auto-resolve merge conflicts with an LLM or with `-X ours/theirs`.
- Never mark an IC READY before the canonical index at `integrated_sha` is READY, the pointer has moved, and the canonical revision has advanced. All three happen in one transaction.
- Candidate indexes must never be referenced by `repository_index_pointers`.
- Candidate commits never appear in `repository_revisions` and never move `canonical_commit`. Integration never moves the default branch or tags; Stratos does that at release (Phase 10).
- Invariant: whenever `repository_index_pointers.canonical_index_version_id` is set, its `commit_sha == repositories.canonical_commit` at every commit boundary.

## 6. Domain / Data Model Changes

Migration `0017_p08_integration_candidates_findings.py` (TECH 007), `0018_p08_canonical_pointers_entity_changes_spec_code_links.py` (TECH 008 completion).

```python
class ICStatus(StrEnum):
    CREATED = "CREATED"
    INTEGRATING = "INTEGRATING"
    VALIDATING = "VALIDATING"
    READY = "READY"
    CONFLICT = "CONFLICT"
    FAILED = "FAILED"
    SUPERSEDED = "SUPERSEDED"


class IntegrationCandidate(Base, UUIDPkMixin, TimestampMixin):
    __tablename__ = "integration_candidates"
    key: Mapped[str]
    delivery_cycle_id: Mapped[uuid.UUID]
    repository_id: Mapped[uuid.UUID]
    base_sha: Mapped[str]
    integration_branch: Mapped[str]
    integrated_sha: Mapped[str | None]
    status: Mapped[ICStatus]
    ordering: Mapped[list] = mapped_column(
        JSONB
    )  # [{task_key, candidate_commit_sha, position, reason}]
    integration_execution_id: Mapped[uuid.UUID | None]
    checks_artifact_id: Mapped[uuid.UUID | None]
    canonical_index_version_id: Mapped[uuid.UUID | None]
    canonical_revision_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("repository_revisions.id")
    )  # set at READY
    supersedes_id: Mapped[uuid.UUID | None]
    # integrated_sha immutable once set (trigger); base_sha = Repository.canonical_commit at creation


class Finding(Base, UUIDPkMixin, TimestampMixin):
    __tablename__ = "findings"
    key: Mapped[str]
    project_id: Mapped[uuid.UUID]
    delivery_cycle_id: Mapped[uuid.UUID]
    integration_candidate_id: Mapped[uuid.UUID | None]
    commit_sha: Mapped[str | None]
    source: Mapped[str]  # INTEGRATION | WARDEN | SENTINEL | SYSTEM | READINESS | LINEAGE
    category: Mapped[str]
    severity: Mapped[str]  # BLOCKER | MAJOR | MINOR | INFO
    blocking: Mapped[bool]  # computed by policy from severity/category — never by agent
    title: Mapped[str]
    detail: Mapped[dict] = mapped_column(JSONB)
    code_refs: Mapped[list] = mapped_column(JSONB)
    spec_refs: Mapped[list] = mapped_column(JSONB)
    status: Mapped[str]  # OPEN | IN_REMEDIATION | RESOLVED | WAIVED | SUPERSEDED
    remediation_task_id: Mapped[uuid.UUID | None]
    waiver_approval_id: Mapped[uuid.UUID | None]
    resolved_by_ic_id: Mapped[uuid.UUID | None]
    producer_execution_id: Mapped[uuid.UUID | None]


class SpecCodeLink(Base, UUIDPkMixin, TimestampMixin):
    __tablename__ = "spec_code_links"
    project_id: Mapped[uuid.UUID]
    repository_id: Mapped[uuid.UUID]
    spec_type: Mapped[str]  # FEATURE_SPEC | IMPLEMENTATION_SPEC | ACCEPTANCE_CRITERION
    spec_id: Mapped[uuid.UUID]  # exact version row
    spec_lineage_key: Mapped[str]
    code_stable_key: Mapped[str]
    relation: Mapped[str]  # IMPLEMENTS | VERIFIES
    origin: Mapped[str]  # GENERATED_LINEAGE | DISCOVERED | HUMAN_CONFIRMED   (D-07)
    confidence: Mapped[float]
    task_id: Mapped[uuid.UUID | None]
    execution_id: Mapped[uuid.UUID | None]
    commit_sha: Mapped[str | None]
    evidence_refs: Mapped[list] = mapped_column(JSONB)
    established_index_version_id: Mapped[uuid.UUID]
    last_confirmed_index_version_id: Mapped[uuid.UUID]
    status: Mapped[str]  # ACTIVE | STALE | RETIRED
    promoted_from_link_id: Mapped[uuid.UUID | None]  # Phase 12
    __table_args__ = (
        Index("ix_scl_spec", "spec_lineage_key", "status"),
        Index("ix_scl_code", "repository_id", "code_stable_key", "status"),
    )
```

Other tables:
- `integration_candidate_commits`: ic_id, candidate_commit_id, position, included (bool), skip_reason.
- `repository_index_pointers`: repository_id (PK), canonical_index_version_id (current IC/assurance target or latest release), released_index_version_id (latest release; Phase 10), updated_at, updated_by_event_id. Updated only by `CanonicalIndexService`.
- `code_entity_changes`: id, repository_id, stable_key, change_kind, execution_id, task_id, candidate_commit_sha, integration_candidate_id, integrated_sha, created_at. Index `(repository_id, stable_key)`.
- FKs added to Phase 01's `repository_revisions`: `integration_candidate_id → integration_candidates.id`, `canonical_index_version_id → code_index_versions.id`.

## 7. State / Lifecycle Changes

IC machine (owner `IntegrationService`; deterministic executor transitions):

| From | To | Trigger / Guard |
|---|---|---|
| (new) | CREATED | `create_integration_candidate`: ≥1 eligible candidate commit; Repository READY; no `CANONICAL_REVISION_HELD` by another cycle; `ic.base_sha := canonical_commit`; any prior non-terminal IC for the cycle → SUPERSEDED |
| CREATED | INTEGRATING | integration execution STARTED |
| INTEGRATING | CONFLICT | merge conflict (Finding + remediation task created) |
| INTEGRATING | FAILED | ancestry invalid or integration checks failed (Finding) |
| INTEGRATING | VALIDATING | integrated SHA persisted |
| VALIDATING | READY | canonical index READY at `integrated_sha` + pointer moved + links materialized + canonical revision advanced (`INTEGRATION_READY`) |
| VALIDATING | SUPERSEDED | `CANONICAL_MOVED_DURING_INTEGRATION` (Finding; a new IC is created from the new canonical revision) |
| CREATED / INTEGRATING / VALIDATING / READY / CONFLICT / FAILED | SUPERSEDED | a newer IC is created for the cycle, or the cycle is CANCELLED/FAILED (READY: canonical revision reverted, §4.4a) |

DeliveryCycle:
- DEVELOPMENT → INTEGRATION (`all_code_tasks_completed`). Side effect: create IC.
- INTEGRATION → ASSURANCE/REGRESSION (`ic_ready_and_canonical_index_current`).
- INTEGRATION → DEVELOPMENT (`remediation_tasks_exist`).
- any → CANCELLED / FAILED while holding an unreleased canonical revision: side effect is a canonical revision revert (§4.4a).

Repository canonical revision (Phase 01 `repository_revisions`): `INTEGRATION_READY` (this phase, at IC READY) and `REVERTED` (this phase, on abandonment).

Finding (base): OPEN → IN_REMEDIATION (remediation task created) → RESOLVED (remediation's IC READY and the condition no longer reproduces) | WAIVED (Approval FINDING_WAIVER). `blocking` is computed by `FindingPolicy` (config), never by agents.

## 8. API / Contract Changes

| Method | Path | Notes |
|---|---|---|
| POST | `/delivery-cycles/{id}/integration-candidates` | create IC (HUMAN/SYSTEM) |
| GET | `/delivery-cycles/{id}/integration-candidates`, `/integration-candidates/{id}` | ordering, status, integrated SHA, checks, canonical index version |
| GET | `/delivery-cycles/{id}/findings`, `/findings/{id}` | (extended in 09) |
| GET | `/repositories/{id}/code-index/canonical` | pointer + version + `canonical_commit` (equal by invariant) |
| GET | `/features/{id}/implementation` | forward lineage tree |
| GET | `/features/{id}/code` | principal entities (canonical index) |
| GET | `/specs/{id}/code-links` | links with origin/confidence/evidence |
| GET | `/specs/{id}/lineage` | spec → impl spec → tasks → executions → commits → IC → entities → tests |
| GET | `/code/entities/{id}/lineage` | reverse: entity → links → ImplementationSpec → FeatureSpec → Feature → Capability → ProductSource; `changed_by` |
| GET | `/tasks/{id}/lineage`, `/executions/{id}/lineage` | |

```python
class IntegrationService:
    async def create(self, cycle_id, ctx) -> IntegrationCandidate
class CanonicalIndexService:
    async def build_candidate(self, execution_id) -> CodeIndexVersion            # provisional
    async def promote_ic(self, ic_id) -> CodeIndexVersion                       # canonical index + pointer + canonical revision advance, one tx
    async def promote_repository_snapshot(self, repository_id, sha) -> CodeIndexVersion   # used by Phase 11/16; requires sha == canonical_commit
class CanonicalRevisionGuardian:
    async def on_cycle_terminal(self, cycle_id) -> RepositoryRevision | None    # revert held canonical revision (§4.4a)
    async def current(self, repository_id) -> CodeIndexVersion | None
class SpecCodeLinkService:
    async def materialize_generated(self, ic_id) -> list[SpecCodeLink]
    async def links_for_spec(self, lineage_key, status="ACTIVE"); async def links_for_entity(self, repository_id, stable_key)
class LineageService:
    async def forward(self, root_type, root_id) -> LineageGraph; async def reverse(self, code_entity_id) -> LineageGraph
    def register_hop(self, hop: LineageHop)     # extension point (09 evidence, 10 release)
```

`LineageGraph` = `{nodes: [{type, id, key, version, label, origin?, confidence?}], edges: [{from, to, relation, origin, confidence}]}`.

Events: `integration.created`, `integration.conflict`, `integration.failed`, `integration.ready`, `code_index.updated`, `spec_code_link.created`, `finding.created`.

## 9. Services / Modules

| Path | Responsibility |
|---|---|
| `core/integration/{service,ordering,merge_executor,checks}.py` | IC lifecycle, ordering, deterministic merge executor, integration checks |
| `core/integration/dependency_base.py` | `DependencyBaseResolver` (registers into Phase 03 base resolver) |
| `core/intelligence/code_index/canonical.py` | `CanonicalIndexService`, pointer management, candidate retention sweeper |
| `core/integration/canonical_revision.py` | revision lock check, `CanonicalRevisionGuardian` (revert on abandonment) |
| `core/intelligence/code_index/changes.py` | entity diff → `code_entity_changes` |
| `core/traceability/spec_code_links/{service,principal}.py` | link materialization + principal-symbol rule |
| `core/traceability/lineage/{service,hops}.py` | lineage graph composition |
| `core/assurance/findings.py` | Finding model service + `FindingPolicy` (base; extended in 09) |
| `core/integration/guards.py` | guards |
| `core/planning/compiler.py` | EXTEND: canonical index context refs |
| `apps/control_api/routers/{integration,lineage,findings}.py` | REST |

## 10. Development Tasks

- [ ] 08.1 Add migrations `0017`–`0018` and the models, including the immutable `integrated_sha` trigger.
- [ ] 08.2 Implement the IC ordering algorithm (topological + key tie-break; skip ancestors) with unit tests.
- [ ] 08.3 Implement `IntegrationService.create`: supersede the prior IC; `ic.base_sha := canonical_commit` with the ancestry check; the `CANONICAL_REVISION_HELD` lock; create the INTEGRATION task + contract; admit.
- [ ] 08.4 Implement the `integration.merge` deterministic executor (SYSTEM ExecutionWorkspace, ancestry check, merges onto `ic.base_sha`, checks via ToolGateway `handle_system`).
- [ ] 08.5 Implement conflict handling: Finding + remediation Task (compiled contract, origin REMEDIATION).
- [ ] 08.6 Implement `FindingPolicy` (`config/policy/default.yaml: findings:` severity → blocking map).
- [ ] 08.7 Implement candidate index build for executions, the entity diff, `code_entity_changes` and the retention sweeper.
- [ ] 08.8 Implement `CanonicalIndexService.promote_ic` with an atomic pointer move + canonical revision advance (`INTEGRATION_READY`, `expected_current = ic.base_sha`) + IC READY, including the `CANONICAL_MOVED_DURING_INTEGRATION` path. Implement `CanonicalRevisionGuardian` (revert on cycle CANCELLED/FAILED, with pointer restore) and the `repository_revisions` FKs.
- [ ] 08.9 Implement the principal-symbol rule and `SpecCodeLinkService.materialize_generated` (IMPLEMENTS and VERIFIES).
- [ ] 08.10 Implement `DependencyBaseResolver` and register it, removing `BASE_RESOLVER_UNAVAILABLE` for multi-dependency tasks.
- [ ] 08.11 Implement `LineageService` forward/reverse with the hop registry.
- [ ] 08.12 Replace guard placeholders `all_code_tasks_completed`, `ic_ready_and_canonical_index_current` and `remediation_tasks_exist` (integration side).
- [ ] 08.13 Extend the compiler with canonical-index context refs.
- [ ] 08.14 Add the REST routes and events.
- [ ] 08.15 Write the tests in §12.

## 11. LLM-Dependent Tasks

No new LLM dependency in this phase. Integration, indexing, change computation and link materialization are deterministic. Forge's declared `principal_symbols` / `ac_test_mapping` (Phase 04 output) are **inputs** validated against the deterministic index.

## 12. Testing Strategy

### Unit Tests
- Ordering: diamond DAG, chain, independent tasks, already-ancestor skip.
- Principal-symbol rule: private helpers are excluded, routes/models are included and declared methods are included.
- Entity diff: added/modified/deleted by stable key and content hash.

### Persistence Tests
- `integrated_sha` is immutable once set.
- The pointer, `Repository.canonical_commit`, the new `repository_revisions` row and IC READY change atomically (failure injection after the revision insert: none of them change).
- `advance` with a stale `expected_current` (canonical moved by a simulated EXTERNAL_SYNC during VALIDATING) → IC SUPERSEDED + Finding `CANONICAL_MOVED_DURING_INTEGRATION`. Canonical stays at the externally adopted SHA.
- SpecCodeLinks with origin GENERATED_LINEAGE have task, execution and commit set (CHECK constraint when the origin is GENERATED_LINEAGE).

### Git / Worktree Tests (deterministic, no LLM; candidate commits created by test helpers)
- Three non-conflicting candidate commits produce IC READY with integrated SHA, and the canonical index exists at that SHA.
- Two conflicting candidates produce IC CONFLICT, a Finding with conflicting files and a remediation task. No merge commit exists on any protected ref.
- A candidate not descending from the base produces IC FAILED (ancestry).
- A multi-dependency task gets a depbase branch, and the snapshot records it.
- The default branch and tags in the canonical RepositoryWorkspace are unchanged by integration (integration happens on `olympus/integration/*`).
- `test_canonical_revision_rule.py` (the README §5.9.5 example):
  - EX-221/222/223 produce candidate commits AAA/BBB/CCC. Before IC READY, `canonical_commit == cycle.base_sha` and `repository_revisions` has no row for AAA/BBB/CCC.
  - After IC-003 READY: `canonical_commit == DEF == ic.integrated_sha == pointer.commit_sha`, the latest revision is `INTEGRATION_READY` with `integration_candidate_id = IC-003`, and AAA/BBB/CCC appear in no revision, pointer or SpecCodeLink with a non-candidate role.
- `test_canonical_revision_lock.py`: cycle A's IC READY, then cycle B's `create_integration_candidate` → 409 `CANONICAL_REVISION_HELD`. Cycle A's new remediation IC is allowed. After cycle A releases (simulated `mark_released`), B's IC is created with `base_sha == DEF`.
- `test_canonical_revision_revert.py`: cancel a cycle whose IC is READY. `canonical_commit` returns to the default-branch head, the pointer returns to the CANONICAL index at that SHA (or is cleared), a `REVERTED` revision row references the reverted one, and the IC is SUPERSEDED.

### Integration Tests
- Candidate indexes have `kind=CANDIDATE`, are never referenced by the pointer, and are DISCARDED after IC READY.
- Lineage forward: Feature → FeatureSpec → ImplementationSpec → Task → Execution → candidate commit → IC → principal entities → tests (fixture built from deterministic helpers).
- Lineage reverse from a method entity resolves to Feature, Capability and ProductSource.

### Runtime / Live-LLM Tests
- Workflow (live, reusing the Phase 06 live workflow output): execute two planned SupportDesk tasks with live Forge, create the IC, and assert READY, canonical index SHA = integrated SHA and SpecCodeLinks GENERATED_LINEAGE for the created routes. This is a precursor to Phase 10.

### Failure / Recovery Tests
- Kill the worker during `integration.merge`. The new execution restarts from base on a fresh worktree, the IC re-enters INTEGRATING (same IC, new execution) and the result is the same integrated tree hash.

### Commands
```
make check
uv run pytest -m "git or integration" tests/integration/integration_candidate tests/integration/traceability
LLM_LIVE_TESTS=1 uv run pytest -m workflow --live-required tests/workflow/integration
```

## 13. Milestone

Multiple candidate commits from a DeliveryCycle converge deterministically into one IntegrationCandidate with an immutable integrated SHA, or into a visible CONFLICT Finding with remediation work. The authoritative Code Intelligence Index is built for exactly that SHA, while execution indexes remain provisional and are discarded. GENERATED_LINEAGE SpecCodeLinks connect FeatureSpec/ImplementationSpec/AC versions to principal code entities and tests, and the lineage is traversable forward from Feature to code and in reverse from code to ProductSource.

## 14. Acceptance Criteria

- [ ] Candidate commits never independently become assurance or release targets. Only an IC with `integrated_sha` can.
- [ ] Merge conflicts produce a Finding plus a remediation task, and no autonomous resolution happens.
- [ ] IC READY implies the canonical index pointer's `commit_sha == integrated_sha`.
- [ ] Candidate indexes are `kind=CANDIDATE`, never pointed to, and DISCARDED after integration.
- [ ] `code_entity_changes` records which execution, task and commit changed each stable key.
- [ ] GENERATED_LINEAGE links carry task, execution and commit with confidence 1.0, and map only principal symbols.
- [ ] AC → test VERIFIES links exist for Forge-declared, index-validated mappings.
- [ ] Forward and reverse lineage queries return complete paths for the fixture.
- [ ] Multi-dependency tasks receive a deterministic dependency base, or are ineligible with a conflict Finding.
- [ ] Integration does not modify the default branch or tags in the canonical RepositoryWorkspace.
- [ ] Candidate commits are never canonical. `Repository.canonical_commit` advances to `integrated_sha` only when the IC becomes READY, atomically with the canonical index pointer move, and records a `repository_revisions` row (`INTEGRATION_READY`) that references the IC and the canonical index version.
- [ ] Whenever a canonical index pointer is set, its `commit_sha` equals `Repository.canonical_commit`.
- [ ] Another cycle cannot create an IC while one cycle holds an unreleased canonical revision (`CANONICAL_REVISION_HELD`). A cancelled or failed cycle's held revision is reverted with a `REVERTED` revision row.

## 15. Exit Criteria

- §14 green, including the live workflow precursor.
- `LineageService.register_hop` and `FindingPolicy` are documented for 09/10.
- Guard placeholders for this phase are removed.
- `STATUS.md`: invariants "IntegrationCandidate is the assurance target", "canonical Code Intelligence index tied to integrated SHA", "Candidate commits do not automatically change canonical project revision" and "canonical revision changes only through governed integration flow" checked; technical trackers IntegrationCandidate, Code Intelligence and Repository Integration updated.

## 16. Dependencies

### Depends On
- 04: candidate commits, `git_local`, deterministic executor via ToolGateway, ExecutionWorkspaces.
- 01 (transitively): `RepositoryRevisionService`.
- 06: planned tasks with ImplementationSpec lineage.
- 07: indexer.

### Blocks
- 09.

### Can Run In Parallel With
- None.

## 17. Risks / Implementation Notes

- **Git risk:** merges create merge commits. The integrated SHA is therefore a merge commit, which is fine because "exact SHA" semantics hold. Use `--no-ff` for traceable topology. Configure the merge author as `Olympus Integration`.
- **Index cost:** a full rebuild per IC is acceptable at SupportDesk scale. Phase 13 introduces incremental builds.
- **Principal-symbol ambiguity:** Forge declarations may be wrong. Validation against the index plus a MINOR Finding keeps lineage honest without blocking.
- **Data consistency:** links reference `code_stable_key` (not entity row IDs) so they survive re-indexing. Resolve them to rows by joining with the canonical version.
- **Canonical before release:** the canonical revision advances at IC READY (the assurance target), not at release. The default branch moves only at release (10) or external adoption (16), so it always marks the last revision that no in-flight IC holds, which is the revert target. Other cycles that pin `base_sha` while a revision is held build on an unreleased revision. If it is reverted, Phase 13 marks their work STALE because their base is no longer an ancestor of canonical.
- **Integration branches** `olympus/integration/*` and released candidate branches are retained, so every IC SHA stays reachable for audit and re-verification.

## 18. Deliverables

- Code: `core/integration/*`, `core/intelligence/code_index/{canonical,changes}.py`, `core/traceability/**`, `core/assurance/findings.py` (base).
- Migrations: `0017`, `0018`.
- APIs/events: §8.
- Config: `findings:` policy section.
- Tests: §12 suites.
