# Phase 15 — Bug Fix Journey (R3)

## 1. Objective

Implement and prove **Journey 4 — Bug Fix** (ARCH §18, TECH §21 / §22): **reproduce before modifying**, create evidence of the failure, resolve expected behavior explicitly, find the faulty code path from runtime/test traces and the code graph, repair minimally, re-index, and prove that the **original reproduction passes**, a **regression test passes** and **impacted baselines pass**, all at the exact integrated SHA, before **Release R3**.

The reference defect is "Updating a CLOSED ticket returns HTTP 500" (expected: 409 Conflict per the approved AC).

## 2. Architectural Context

- **Position:** BUG_FIX lifecycle TRIAGE → REPRODUCTION → EXPECTED_BEHAVIOR → ROOT_CAUSE → DEVELOPMENT → INTEGRATION → REGRESSION → ASSURANCE → RELEASE → COMPLETE (D-05).
- **Planes:**
  - product model (Defect, links to Feature/AC/Baseline);
  - assurance (reproduction, regression evidence);
  - intelligence (trace correlation, code path, root-cause impact);
  - execution (repair contracts).
- **Upstream:** 13 (ImpactEngine with seed entities, HybridRetrieval, SpecDelta, staleness), 12 (baselines), 09 (evidence/gates/verification workspace), 06 (REPAIR ImplementationSpec kind, compiler), 05 (inbound kernel).
- **Downstream:** 16 (defect events from trackers or CI call `intake_defect`), 17 (Defect view), 19.
- **Invariants:**
  - Failure evidence exists before repair.
  - Expected behavior is explicit.
  - Original reproduction passes after repair.
  - Regression obligations pass.
  - Re-index before final assurance.
  - Inference (probable cause) is kept separate from evidence.
  - Model opinion never replaces runtime/test evidence (Sentinel constraint).

## 3. Current Repository Assessment

Inspection on 2026-10-01: none of this exists.

### Existing
- (after 13) `ImpactEngine.assess(seed_stable_keys=…)`, HybridRetrieval, SpecDelta — **RETAIN**.
- (after 09) EvidenceType `REPRODUCTION`/`REGRESSION_TEST`, obligation reasons `DEFECT_REPRODUCTION`/`REGRESSION`, gate types `REPRODUCTION`/`REGRESSION`, verification workspace — **EXTEND** (sources registered here).
- (after 06) ImplementationSpec `kind=REPAIR`, Task.origin `REPAIR` (D-12) — **EXTEND**.
- (after 12) KnowledgeItem suggestions `suggested_defect=true` — **EXTEND** (convert to Defect).

### Partial
- Guards `defect_triaged`, `reproduction_recorded`, `expected_behavior_resolved`, `repair_spec_approved_contracts_issued` and `reproduction_and_regression_pass`, plus the eligibility conditions for reproduction/regression, are placeholders — **REPLACE**.

### Missing
- Defect, Reproduction, TraceCorrelation, RootCauseAnalysis, the profiles, the orchestrator and the journey — **ADD**.

### Refactor / Migration Required
- None of earlier behavior. New obligation sources and eligibility conditions are registered via registries.

## 4. Scope

1. Tables: `defects`, `reproductions`, `trace_correlations`, `root_cause_analyses`, `expected_behavior_resolutions`.
2. **Intake**: inbound adapter `defect_report_api` (operator/API; idempotent) → `intake_defect` → Defect REPORTED + BUG_FIX cycle (TRIAGE) + ProductSource (`DEFECT_REPORT`). Also `create_defect_from_suggestion` (Phase 12 KnowledgeItem). The project must satisfy `project_change_ready` (14).
3. **Triage** (`kira.defect_triage`, live):
   - Input: defect text, `HybridRetrieval.resolve_feature` candidates (features/specs/ACs/baselines with labels), affected release manifest.
   - Output `DefectTriage`:
     - `feature_keys` (⊂ candidates);
     - `suspected_ac_lineage_keys`, `suspected_baseline_keys`;
     - severity (S1–S4);
     - a structured `reproduction_plan`: preconditions, HTTP or function steps, and observed symptom;
     - `observed_symptom_signature`, for example `{"kind":"http_status","value":500}`;
     - open questions.
   - The deterministic validator checks references and that the plan has ≥1 step.
   - Guard `defect_triaged`: triage persisted and validated, severity set, and either ≥1 linked feature or a HUMAN decision "unlinked defect".
4. **Reproduction** (`sentinel.reproduce`, live test authoring, then deterministic execution):
   1. Sentinel writes a pytest reproduction test from the plan in the verification workspace at the **affected SHA** (`defects.affected_sha`: the release SHA named in the report, or the current canonical default-branch head when the defect was introduced by an external commit detected by Phase 16 — the Phase 19 chained-demo case). Writes go through ToolGateway `fs.write`, scope `tests/olympus_repro/**` only. HTTP tests must use `TestClient(app, raise_server_exceptions=False)` so the 500 is observable.
   2. Deterministic executor `reproduction.run` runs it with `pytest --junitxml` under coverage (§4.5), with pinned dependency env and a time limit.
   3. **Reproduced** iff all of the following hold:
      - the test fails with an assertion failure (not a collection, import or syntax error);
      - the failure output matches `observed_symptom_signature` (deterministic matcher per kind: `http_status`, `exception_type`, `message_regex`);
      - the test is stable over 2 consecutive runs.
   4. The test file is stored as an immutable artifact (content-hashed) and Evidence `REPRODUCTION` is created with `subject=DEFECT`, `phase=PRE_REPAIR`, `commit_sha=affected_sha`, `result=FAIL` and `reproduced=true`.
   5. If not reproduced: retry Sentinel up to policy `bugfix.reproduction_attempts=3` (new Executions with the prior attempt's output in the continuation package). Then Defect NOT_REPRODUCIBLE and the cycle stays in REPRODUCTION, pending a HUMAN decision: either `proceed_unreproduced` (Approval(UNREPRODUCED_REPAIR) with reason; permitted only if policy `bugfix.allow_unreproduced=true`, default **false**) or `reject_defect` → CANCELLED.
   6. Guard `reproduction_recorded`: PRE_REPAIR REPRODUCTION evidence with `reproduced=true`, or an approved UNREPRODUCED_REPAIR.
5. **Runtime / test trace correlation** (deterministic executor `trace.correlate`, run as part of `reproduction.run`):
   - coverage line hits of the reproduction test → map to CodeEntities via index spans at the affected SHA (`executed_stable_keys`);
   - server-side traceback captured by a logging handler injected through a `conftest.py` in `tests/olympus_repro/` → frames → stable keys (`traceback_stable_keys`, ordered innermost first);
   - entry route resolution: the ROUTE entity matching the request method and path.
   Persisted as `trace_correlations`.
6. **Expected behavior** (`kira.expected_behavior`, live):
   - Input: defect, triage, linked FeatureSpec(s) with ACs, baselines, reproduction output.
   - Output `ExpectedBehaviorProposal`:
     - `classification` ∈ {SPECIFIED, UNDERSPECIFIED, CONFLICTING, NOT_A_DEFECT};
     - `cited_ac_lineage_keys` (SPECIFIED; must exist and be APPROVED);
     - `proposed_ac` (UNDERSPECIFIED);
     - `expected_behavior_statement`;
     - questions.
   - Resolution (`expected_behavior_resolutions`):
     - SPECIFIED → system-resolved if the cited AC is APPROVED (policy may require HUMAN confirmation, default no);
     - UNDERSPECIFIED → SpecDelta (13) FeatureSpec v(n+1) with the new AC → Approval(SPEC_DELTA);
     - CONFLICTING → clarification to HUMAN, then Approval(EXPECTED_BEHAVIOR);
     - NOT_A_DEFECT → HUMAN confirms → Defect REJECTED, cycle CANCELLED.
   - Guard `expected_behavior_resolved`.
7. **Code path resolution** (deterministic `CodePathResolver`):
   - Candidate faulty symbols = traceback keys ∪ (executed keys ∩ graph-reachable from the entry ROUTE via EXPOSES/CALLS, depth ≤ policy).
   - Each candidate gets a graph path from the route, and `evidence_basis` ∈ {TRACEBACK, EXECUTED, GRAPH_ONLY}.
   - Plus the SpecCodeLinks of the resolved AC's principal symbols.
8. **Root cause** (`warden.root_cause`, live; Q-09):
   - Input: defect, expected behavior, failure output, traceback, candidates with paths and source snippets (read-only context; no worktree).
   - Output `RootCauseHypothesis`:
     - `faulty_stable_keys` (⊂ candidates);
     - `explanation` (classified **INFERENCE**);
     - `confidence`;
     - `fix_outline`;
     - `regression_risks`;
     - `cited_evidence_ids`.
   - Persisted in `root_cause_analyses`, kept separate from evidence: the probable cause is never Evidence.
   - Then `ImpactEngine.assess(seed_kind=DEFECT_ROOT_CAUSE, seed_stable_keys=faulty keys)` → IA (impacted tests and baselines).
9. **Repair spec and contracts**:
   - `kira.implementation_spec` with `mode=REPAIR` (live) → ImplementationSpec `kind=REPAIR` (components and files limited to the faulty symbols' files plus the test directory; `required_tests` includes a **regression test** derived from the reproduction artifact).
   - `kira.task_plan` (live) → typically 1 IMPLEMENTATION task (`origin=REPAIR`).
   - Validator: `allowed_scope` files ≤ policy `bugfix.max_repair_files=3` (excluding tests), and required outputs include `regression_test_path` under `tests/`.
   - Approval(IMPLEMENTATION_SPEC) subject includes the RCA id and IA hash.
   - The compiler adds constraints:
     - "make the reproduction pass: <artifact ref>";
     - "add a regression test equivalent to the reproduction in tests/";
     - "preserve impacted baselines".
   - Guard `repair_spec_approved_contracts_issued`.
10. Forge repair (live) → candidate → IC → incremental re-index (13) → link refresh → GENERATED_LINEAGE for changed symbols linked to the expected-behavior AC.
11. **REGRESSION state** (deterministic):
    1. `reproduction.run` at the **IC SHA** with the **same** artifact → Evidence `REPRODUCTION` `phase=POST_REPAIR`, which must PASS.
    2. Run the regression test added by Forge → Evidence `REGRESSION_TEST` PASS.
    3. Check that the regression test fails at the affected SHA (deterministic proof that it actually guards the defect; recorded as `regression_test_validated=true`).
    - Obligations:
      - `DEFECT_REPRODUCTION` (gate REPRODUCTION);
      - `REGRESSION` (gate REGRESSION);
      - impacted baselines (BASELINE, via 13 selection);
      - the expected-behavior AC (SENTINEL).
    - Guard `reproduction_and_regression_pass`: REPRODUCTION and REGRESSION gates PASS.
12. ASSURANCE: Warden review of the repair diff, Sentinel plan/execute for baselines and AC (09 machinery) → gates. Required gates for BUG_FIX: INTEGRATION, REPRODUCTION, REGRESSION, BASELINE, WARDEN, SENTINEL.
13. Eligibility conditions:
    - `defect_reproduced_before_repair` (PRE_REPAIR evidence exists with an earlier `created_at` than the first repair candidate commit, or an approved UNREPRODUCED_REPAIR);
    - `original_reproduction_passes`;
    - `regression_evidence_present`.
14. Release R3 → Defect RELEASED. The regression test becomes a baseline (`check_kind=TEST`, origin `REGRESSION`), added to BaselineSet B(n+1).
15. Bug-fix orchestrator (SYSTEM): deterministic sequencing, the same pattern as 10 and 14.
16. Fixture `tests/fixtures/repos/supportdesk_defect_closed_update/`: `supportdesk_r1` where the status-update handler dereferences a missing transition entry for CLOSED, raising a KeyError → 500. Existing tests do not cover updates to a CLOSED ticket. Seeded with `trusted_seed.yaml` (14) including the AC "updating a CLOSED ticket is rejected with HTTP 409".

## 5. Out of Scope

- Defect events from external trackers or CI (16).
- Production runtime telemetry ingestion (trace correlation uses test-run traces only for MVP).
- Auto-closing external tickets (16 outbound).

### Do Not Change
- The reproduction artifact is immutable. Post-repair runs use the exact same file hash.
- Forge never receives write scope to `tests/olympus_repro/**`.
- A RootCauseHypothesis never satisfies an obligation.

## 6. Domain / Data Model Changes

Migration `0025_p15_defects_reproduction_root_cause.py` (TECH 009 defects). If 14 and 15 merge out of order, the second one re-points `down_revision`, keeping a linear chain.

```python
class Defect(Base, UUIDPkMixin, TimestampMixin):
    __tablename__ = "defects"
    key: Mapped[str]
    project_id: Mapped[uuid.UUID]
    delivery_cycle_id: Mapped[uuid.UUID | None]
    title: Mapped[str]
    description: Mapped[str]
    product_source_id: Mapped[uuid.UUID]
    source_type: Mapped[str]
    external_ref: Mapped[str | None]
    inbound_event_id: Mapped[uuid.UUID | None]
    affected_release_id: Mapped[uuid.UUID | None]
    affected_sha: Mapped[str]
    severity: Mapped[str | None]  # S1..S4
    status: Mapped[
        str
    ]  # REPORTED|TRIAGED|REPRODUCED|NOT_REPRODUCIBLE|EXPECTED_RESOLVED|ROOT_CAUSED|IN_REPAIR|FIXED|RELEASED|REJECTED
    triage: Mapped[dict | None] = mapped_column(JSONB)
    linked_feature_ids: Mapped[list] = mapped_column(JSONB, default=list)
    expected_ac_ids: Mapped[list] = mapped_column(JSONB, default=list)
    __table_args__ = (UniqueConstraint("project_id", "source_type", "external_ref"),)


class Reproduction(Base, UUIDPkMixin, TimestampMixin):
    __tablename__ = "reproductions"
    defect_id: Mapped[uuid.UUID]
    phase: Mapped[str]  # PRE_REPAIR | POST_REPAIR | REGRESSION_VALIDATION
    commit_sha: Mapped[str]
    artifact_id: Mapped[uuid.UUID]
    artifact_hash: Mapped[str]
    execution_id: Mapped[uuid.UUID]
    outcome: Mapped[str]  # REPRODUCED | NOT_REPRODUCED | PASS | FAIL | ERROR
    signature_matched: Mapped[bool]
    runs: Mapped[int]
    evidence_id: Mapped[uuid.UUID | None]
    junit_artifact_id: Mapped[uuid.UUID]


class TraceCorrelation(Base, UUIDPkMixin, TimestampMixin):
    __tablename__ = "trace_correlations"
    reproduction_id: Mapped[uuid.UUID]
    index_version_id: Mapped[uuid.UUID]
    entry_route_key: Mapped[str | None]
    traceback_stable_keys: Mapped[list] = mapped_column(JSONB)
    executed_stable_keys: Mapped[list] = mapped_column(JSONB)
    candidates: Mapped[list] = mapped_column(JSONB)  # [{stable_key, evidence_basis, path}]


class RootCauseAnalysis(Base, UUIDPkMixin, TimestampMixin):
    __tablename__ = "root_cause_analyses"
    defect_id: Mapped[uuid.UUID]
    trace_correlation_id: Mapped[uuid.UUID]
    execution_id: Mapped[uuid.UUID]
    faulty_stable_keys: Mapped[list] = mapped_column(JSONB)
    explanation: Mapped[str]
    knowledge_class: Mapped[str] = mapped_column(default="INFERENCE")
    confidence: Mapped[float]
    fix_outline: Mapped[str]
    regression_risks: Mapped[list] = mapped_column(JSONB)
    cited_evidence_ids: Mapped[list] = mapped_column(JSONB)
    impact_assessment_id: Mapped[uuid.UUID | None]
    status: Mapped[str]  # PROPOSED | ACCEPTED | REJECTED


class ExpectedBehaviorResolution(Base, UUIDPkMixin, TimestampMixin):
    __tablename__ = "expected_behavior_resolutions"
    defect_id: Mapped[uuid.UUID]
    classification: Mapped[str]
    resolution_kind: Mapped[str]  # SPECIFIED|SPEC_DELTA|HUMAN_DECIDED|NOT_A_DEFECT
    ac_ids: Mapped[list] = mapped_column(JSONB)
    spec_delta_id: Mapped[uuid.UUID | None]
    approval_id: Mapped[uuid.UUID | None]
    statement: Mapped[str]
    execution_id: Mapped[uuid.UUID]
```

Other changes:
- `evidence.metadata` keys: `phase`, `reproduced`, `regression_test_validated`.
- New approval types: `UNREPRODUCED_REPAIR`, `EXPECTED_BEHAVIOR`.
- New baseline origin `REGRESSION`.

## 7. State / Lifecycle Changes

| BUG_FIX edge | Guard | Orchestrated side effects |
|---|---|---|
| TRIAGE → REPRODUCTION | `defect_triaged`, `repository_ready_with_canonical_commit` (01) | `pin_base_sha` (01): the affected SHA is `cycle.base_sha := canonical_commit` (normally the R2 released SHA); schedule `sentinel.reproduce` in a READONLY ExecutionWorkspace at that SHA |
| REPRODUCTION → EXPECTED_BEHAVIOR | `reproduction_recorded` | trace correlation persisted; schedule `kira.expected_behavior` |
| EXPECTED_BEHAVIOR → ROOT_CAUSE | `expected_behavior_resolved` | CodePathResolver → `warden.root_cause` → IA |
| ROOT_CAUSE → DEVELOPMENT | `repair_spec_approved_contracts_issued` | admit repair task |
| DEVELOPMENT → INTEGRATION | `all_code_tasks_completed` | IC |
| INTEGRATION → REGRESSION | `ic_ready_and_canonical_index_current` | post-repair reproduction, regression run, regression validation |
| REGRESSION → ASSURANCE | `reproduction_and_regression_pass` | Warden + Sentinel |
| ASSURANCE → RELEASE → COMPLETE | `required_gates_pass`, `release_executed` | R3, regression baseline |
| any → CANCELLED | HUMAN `reject_defect` | Defect REJECTED |

Defect: REPORTED → TRIAGED → REPRODUCED | NOT_REPRODUCIBLE → EXPECTED_RESOLVED → ROOT_CAUSED → IN_REPAIR → FIXED (IC passes REGRESSION) → RELEASED, or REJECTED (`DefectService`, following the cycle).

## 8. API / Contract Changes

| Method | Path | Notes |
|---|---|---|
| POST | `/projects/{id}/defects` | via inbound kernel; creates BUG_FIX cycle |
| GET | `/projects/{id}/defects`, `/defects/{id}` | with triage, reproductions, RCA, resolution |
| GET | `/defects/{id}/reproductions` | evidence + artifact links |
| GET | `/defects/{id}/trace` | trace correlation + candidates with paths |
| GET | `/defects/{id}/root-cause` | hypothesis (INFERENCE label), IA link |
| POST | `/defects/{id}/expected-behavior/decide` | HUMAN decision (CONFLICTING path) |
| POST | `/defects/{id}/proceed-unreproduced` | HUMAN + policy |
| POST | `/defects/{id}/reject` | HUMAN |
| POST | `/knowledge-items/{id}/create-defect` | from a Brownfield suggestion |

Events: `defect.reported`, `defect.triaged`, `defect.reproduced`, `defect.not_reproducible`, `defect.expected_behavior_resolved`, `defect.root_caused`, `defect.fixed`, `defect.released`, `defect.rejected`, `reproduction.completed`.

## 9. Services / Modules

| Path | Responsibility |
|---|---|
| `core/product_model/defects/{service,triage,expected_behavior,orchestrator,guards}.py` | defect lifecycle |
| `core/integrations/inbound/adapters/defect_report_api.py` | inbound adapter |
| `core/assurance/reproduction/{executor,signature,regression}.py` | `reproduction.run`, matchers, regression validation |
| `core/intelligence/impact/{trace,code_path}.py` | trace correlation + CodePathResolver |
| `agents/kira/prompts/{defect_triage,expected_behavior,implementation_spec_repair}.md` | Kira profiles |
| `agents/sentinel/prompts/reproduce.md` | `sentinel.reproduce` |
| `agents/warden/prompts/root_cause.md`, `schemas.py` | `warden.root_cause` |
| `core/assurance/obligations.py`, `core/release/eligibility.py` | EXTEND: sources and conditions |
| `apps/control_api/routers/defects.py` | REST |
| `tests/fixtures/repos/supportdesk_defect_closed_update/`, `tests/fixtures/supportdesk/defect_closed_update.md` | fixtures |
| `tests/journey/test_bug_fix_supportdesk.py` | journey |

## 10. Development Tasks

- [x] 15.1 Add migration `0028`/`0029` and the models and services.
- [x] 15.2 Implement the `defect_report_api` adapter, `intake_defect` and `create_defect_from_suggestion`.
- [x] 15.3 Implement the `kira.defect_triage` profile and validator, and the `defect_triaged` guard.
- [x] 15.4 Implement the `sentinel.reproduce` profile (scope `tests/olympus_repro/**`) and the `reproduction.run` executor (junit, coverage, traceback capture conftest, 2-run stability).
- [x] 15.5 Implement the signature matchers (`http_status`, `exception_type`, `message_regex`) and error-vs-assertion classification.
- [x] 15.6 Implement the reproduction retry loop, the NOT_REPRODUCIBLE path and the `reproduction_recorded` guard.
- [x] 15.7 Implement trace correlation (coverage → stable keys via spans; traceback → stable keys; route resolution).
- [x] 15.8 Implement the `kira.expected_behavior` profile, the resolution paths (SpecDelta reuse) and the `expected_behavior_resolved` guard.
- [x] 15.9 Implement `CodePathResolver`.
- [x] 15.10 Implement the `warden.root_cause` profile and validator, RCA persistence and the IA call.
- [x] 15.11 Implement REPAIR mode for `kira.implementation_spec` / `kira.task_plan`, the validator limits, compiler constraints and the `repair_spec_approved_contracts_issued` guard.
- [x] 15.12 Implement the REGRESSION stage: post-repair reproduction, regression run, regression validation at the affected SHA, obligations and the guard.
- [x] 15.13 Add the eligibility conditions and BUG_FIX required gates in policy.
- [x] 15.14 Implement the release hook (regression baseline, BaselineSet bump, Defect RELEASED).
- [x] 15.15 Implement the bug-fix orchestrator.
- [x] 15.16 Add the fixtures (defect repo, defect report text).
- [x] 15.17 Add the REST routes and events.
- [x] 15.18 Write the tests in §12, including the journey.

## 11. LLM-Dependent Tasks

| Profile | Why | Inputs (source) | Output | Alias | Validation | Failure handling | Live test |
|---|---|---|---|---|---|---|---|
| `kira.defect_triage` | Interpreting a free-text defect against the product model | defect text, hybrid candidates, release manifest | `DefectTriage` | `product_decomposition` | refs ⊂ candidates; plan ≥1 step | schema retry; HUMAN edit | `test_kira_defect_triage_live.py` |
| `sentinel.reproduce` | Semantic test design from a defect description | triage plan, linked ACs, route/schema context | reproduction test file + `observed_symptom_signature` | `verification_planning` | file scope; PASS/FAIL comes only from execution | up to 3 attempts, then NOT_REPRODUCIBLE | `test_sentinel_reproduce_live.py` (defect repo: reproduces 500) |
| `kira.expected_behavior` | Mapping the defect to intended behavior | defect, specs/ACs, baselines, failure output | `ExpectedBehaviorProposal` | `product_decomposition` | cited ACs exist and are APPROVED | clarification path | `test_kira_expected_behavior_live.py` (cites the 409 AC) |
| `warden.root_cause` | Probable-cause reasoning over trace + code | traceback, executed keys, candidates + snippets | `RootCauseHypothesis` | `review` | keys ⊂ candidates; cites evidence | retry; HUMAN may reject RCA → rerun | `test_warden_root_cause_live.py` (identifies the update handler/transition symbol) |
| `kira.implementation_spec` / `kira.task_plan` (REPAIR) | Minimal repair design | RCA, IA, AC, architecture | REPAIR ImplementationSpec, TaskPlan | `planning` | file limits; regression test required | Phase 06 | journey |
| `forge` | Repair + regression test | contract | `ImplementationResult` | `implementation` | Phase 04 | Phase 03 retry | journey |
| `warden.review` / `sentinel.plan` | Review / verification | IC | Phase 09 | `review` / `verification_planning` | Phase 09 | Phase 09 | journey |

## 12. Testing Strategy

### Unit Tests
- Signature matchers.
- Assertion vs collection-error classification from junit.
- Coverage-to-stable-key mapping with nested functions.
- CodePathResolver on a synthetic graph (TRACEBACK > EXECUTED > GRAPH_ONLY ordering).
- Validator limits (max repair files; regression test required).

### Persistence Tests
- Reproduction artifact immutability (hash).
- Defect idempotency by external ref.
- RCA `knowledge_class` is always INFERENCE.

### Integration Tests (deterministic; human-authored test inputs only)
- `reproduction.run` with a hand-written reproduction test (a test **input**, not a model output) on the defect repo gives REPRODUCED with a signature match. On `supportdesk_r1` (no defect) it gives NOT_REPRODUCED.
- Post-repair stage with a hand-written fix commit (git fixture **input**): POST_REPAIR PASS. A regression test that also passes at the affected SHA gives `regression_test_validated=false` and the REGRESSION gate FAILs.
- `defect_reproduced_before_repair` fails if PRE_REPAIR evidence is created after the candidate commit.
- `proceed_unreproduced` is rejected when policy forbids it.

### Runtime / Live-LLM Tests
- The §11 live tests.

### E2E / Journey Tests (`journey`, live)
`test_bug_fix_supportdesk.py`:
1. `seed_trusted_project(supportdesk_defect_closed_update, trusted_seed.yaml)` → READY_FOR_CHANGE with B1 and released SHA S0.
2. POST defect "Updating a CLOSED ticket returns HTTP 500" → BUG_FIX cycle TRIAGE → live triage links the ticket status feature.
3. Live Sentinel reproduction → PRE_REPAIR REPRODUCTION evidence at S0 (FAIL, 500 matched), with the trace correlation including the update handler.
4. Live expected behavior → SPECIFIED citing the 409 AC.
5. Live root cause → faulty keys ⊂ candidates. IA lists impacted tests and baselines.
6. Live REPAIR spec + task plan → scripted HUMAN approval → contract `allowed_scope` ≤ 3 source files.
7. Live Forge repair → IC → incremental re-index (canonical SHA == IC SHA) → link refresh.
8. REGRESSION:
   - POST_REPAIR reproduction PASS with the same artifact hash;
   - regression test PASS at the IC SHA and FAIL at S0;
   - REPRODUCTION and REGRESSION gates PASS.
9. Assurance live → BASELINE, WARDEN and SENTINEL gates PASS.
10. Release R3 (scripted HUMAN) → `main` == IC SHA, regression baseline in B(n+1), Defect RELEASED.
11. `assert_live_llm_proof(cycle, [defect_triage, reproduce, expected_behavior, root_cause, implementation_spec_repair, task_plan, forge, warden, sentinel_plan])`.
12. Lineage: Defect → reproduction evidence (S0) → RCA (INFERENCE) → repair Task → Execution → commit → IC → changed entity → regression test → evidence → R3.

### Failure / Recovery Tests
- Kill the worker during `reproduction.run` → lease expiry → new Execution → the same artifact is reused (no new Sentinel call needed if the artifact exists).
- HUMAN rejects the RCA → rerun produces a new RCA row and the old one is REJECTED.

### Commands
```
make check
uv run pytest tests/integration/defects tests/integration/reproduction
LLM_LIVE_TESTS=1 uv run pytest -m "live_llm or journey" --live-required tests/integration/live_llm/defects tests/journey/test_bug_fix_supportdesk.py -s
```

## 13. Milestone

**Journey 4 complete.** For "Updating a CLOSED ticket returns HTTP 500":
- a live-authored reproduction test fails at the affected SHA with matching-symptom evidence recorded **before** any repair;
- expected behavior (409) is resolved against an approved AC;
- trace correlation and the code graph identify the faulty path;
- a live root-cause hypothesis (labeled inference) drives an impact-assessed minimal repair contract;
- Forge's repair is integrated and re-indexed.

At the exact IC SHA, the original reproduction, a validated regression test and the impacted baselines all pass, and a human-approved **Release R3** is produced.

## 14. Acceptance Criteria

- [x] A Defect is ingested idempotently and linked to one BUG_FIX cycle and, after triage, to the affected Feature/ACs.
- [x] PRE_REPAIR REPRODUCTION evidence (assertion failure + symptom signature match, stable over 2 runs) exists at the affected SHA before the first repair commit.
- [x] Expected behavior is explicitly resolved (cited approved AC, approved spec delta, or human decision) before root-cause analysis.
- [x] Faulty-symbol candidates are derived deterministically from traceback/coverage and the code graph, with paths.
- [x] The root-cause hypothesis is persisted as INFERENCE, separate from evidence, and never satisfies an obligation.
- [x] The repair contract is minimal (≤ policy file limit) and requires a regression test.
- [x] The affected SHA is the repository's canonical revision pinned at `start_reproduction`. The repair runs in an isolated ExecutionWorkspace from that base. At IC READY, `canonical_commit` advances to the IC SHA, and the canonical index is re-indexed at that SHA before the REGRESSION stage.
- [x] The original reproduction (same artifact hash) passes at the IC SHA. The regression test passes at the IC SHA and fails at the affected SHA.
- [x] Impacted baselines pass. Release R3 is eligible only with the REPRODUCTION, REGRESSION, BASELINE, WARDEN, SENTINEL and INTEGRATION gates PASS.
- [x] The Bug Fix journey test passes live with LLM proof for all model-dependent stages.

## 15. Exit Criteria

- §14 green, with the journey run recorded in `STATUS.md`.
- Journey Readiness → Bug Fix = COMPLETE (pending Phase 19).
- No BUG_FIX guard placeholders remain. Q-09 decision recorded.

## 16. Dependencies

### Depends On
- 13.

### Blocks
- 16.

### Can Run In Parallel With
- 14. See the Phase 14 §16 ownership split: shared files are `core/assurance/obligations.py` (separate registration functions), `core/release/eligibility.py` (registry entries) and the migration chain.

## 17. Risks / Implementation Notes

- **Flaky reproduction:** the 2-run stability rule plus pinned dependency env.
- **Overfitted regression test** (the test passes even at S0): caught by regression validation at S0.
- **Root cause wrong:** the IA and repair are bounded by candidates. The post-repair reproduction is the arbiter, and on failure the remediation loop (09) returns to DEVELOPMENT.
- **Traceback capture** depends on the app logging config. The repro `conftest.py` installs a handler on the `uvicorn.error`/root logger and uses `raise_server_exceptions=False`.
- **Q-09:** the root-cause agent is Warden (read-only, independent of Forge) because the docs do not name one.
- **Q-05:** introducing the defect in the chained demo is handled in 16/19.

## 18. Deliverables

- Code: `core/product_model/defects/*`, `core/assurance/reproduction/*`, trace/code_path, profiles (Kira ×3 modes, Sentinel reproduce, Warden root cause), obligation/eligibility extensions, orchestrator.
- Migration: `0025`.
- APIs/events: §8.
- Fixtures: defect repo, defect report.
- Tests: §12, including the Bug Fix journey.
