# Phase 09 — Assurance: Evidence, Verification Obligations, Warden, Sentinel, Gates and Remediation Loop

## 1. Objective

Implement independent, evidence-based assurance against the exact IntegrationCandidate SHA (ARCH §11.2–11.4, TECH §18):

- typed, immutable **Evidence** bound to `(IC, integrated_sha)`;
- **VerificationObligations** derived deterministically from mandatory ACs (and later baselines, impact and defects);
- **AcceptanceCoverage**;
- **Warden**: live-LLM engineering review that produces Findings and a recommendation;
- **Sentinel**: live-LLM verification *planning* plus deterministic execution of tests and runtime probes that produces Evidence and a recommendation;
- the deterministic **Gate Finalizer**, which alone sets Gate PASS/FAIL;
- the **Finding → remediation → new Execution → new IC → impacted verification** loop;
- finding **waivers** via explicit Approval.

This is where "AI recommends, Olympus decides" becomes enforceable code.

## 2. Architectural Context

- **Position:** Assurance (Warden, Sentinel, Evidence + Gate Finalization) between IntegrationCandidate and Release Eligibility.
- **Upstream:**
  - 08: IC READY, canonical index, Findings base, VERIFIES links.
  - 04: `test.run`, readonly workspaces.
  - 05: ACs with `evidence_requirement`.
  - 06: ImplementationSpec/Architecture for Warden.
  - 03: executions.
- **Downstream:**
  - 10: release eligibility consumes gates, coverage and findings.
  - 12: baselines execute via Sentinel; READINESS findings.
  - 13: impact-selected obligations.
  - 14/15: new AC + baseline + reproduction/regression obligations.
  - 17: Assurance view.
- **Lifecycle:** cycle ASSURANCE (and REGRESSION for bug fix); Gate PENDING → PASS/FAIL; Obligation lifecycle; Finding lifecycle.
- **Invariants:**
  - 20–23: Warden produces findings/recommendations; Sentinel produces verification evidence; neither can set Gate PASS; gate finalization is deterministic.
  - 26–27: mandatory ACs require evidence; model opinion alone cannot satisfy an AC.
  - 17: assurance targets the exact IC SHA.

## 3. Current Repository Assessment

Inspection on 2026-10-01: none of this exists.

### Existing
- (after 08) `findings` table + `FindingPolicy`, IC, canonical index, VERIFIES links — **EXTEND**.
- (after 04) `test.run`, readonly worktrees — **EXTEND** (`test.run_probe`, overlay workspace).

### Partial
- Guards `required_gates_pass` and `remediation_tasks_exist` (ASSURANCE side) are placeholders — **REPLACE**.

### Missing
- Evidence, obligations, coverage, gates, Warden, Sentinel, verification workspace, finalizer, remediation orchestration and waivers — **ADD**.

### Refactor / Migration Required
- None.

## 4. Scope

1. Tables: `evidence`, `verification_obligations`, `acceptance_coverage`, `gates`, `verification_plans`, `reviews` (Warden review summaries).
2. **Obligation derivation** (`ObligationService.derive(ic)`), deterministic. For every mandatory AC version in the cycle's approved scope (and, from 12–15, baselines/impact/reproduction):
   - one obligation `{subject_type=AC, subject_id, required_evidence_types (from evidence_requirement), reason=AC_MANDATORY}`;
   - non-mandatory ACs get `required=false` obligations.
   The derivation records `reason` and `source_refs` (ARCH §21.4: "record why each verification obligation was chosen").
3. **Verification workspace**: a READONLY ExecutionWorkspace (Phase 04 `create_readonly`; logical `projects/<project_id>/worktrees/<EX-key>`, detached at `integrated_sha`) plus an overlay directory `.olympus_verification/` for Sentinel-authored checks. The overlay never enters any commit. Each check is stored as an artifact with a content hash. Before executing, the executor asserts `git rev-parse HEAD == ic.integrated_sha == Repository.canonical_commit`. Otherwise it fails with `CANONICAL_REVISION_MISMATCH` and records no evidence.
4. **Sentinel** (two stages):
   - **Plan (live LLM, `sentinel.plan`):** input is the obligations, AC texts, existing test entities with VERIFIES links, route list and schemas from the canonical index. Output is a `VerificationPlan`. Per obligation, choose:
     - (a) existing test node IDs in the IC;
     - (b) Sentinel-authored pytest checks (code as text);
     - (c) HTTP API probes `{method, path, body, expected_status, expected_json_subset}` against the app started from the IC.
     The plan is validated deterministically: test node IDs must exist in the canonical index; probe paths must match ROUTE entities; every required obligation must have ≥1 executable check.
   - **Execute (deterministic, `sentinel.execute`):** for each check, run it via ToolGateway in the verification workspace:
     - `test.run` with `pytest <nodeid> --junitxml`;
     - an overlay test file;
     - `test.run_probe`: start `uvicorn` on an ephemeral port with an isolated temp DB env, wait for health, execute probes, stop.
     Each result becomes an Evidence row: type UNIT_TEST / INTEGRATION_TEST / API_TEST / E2E_TEST / RUNTIME_OBSERVATION, result PASS/FAIL/ERROR, `commit_sha=integrated_sha`, plus a check artifact hash and log artifact. The coverage row links the obligation to the evidence.
   - **Recommendation (`sentinel.summarize`, live, optional per policy):** produces a `SentinelRecommendation{recommended: PASS|FAIL, uncovered_obligations, observations}` stored on the gate as a recommendation only.
5. **Warden** (`warden.review`, live LLM):
   - Input: the exact integrated diff (`git diff ic.base_sha..integrated_sha`, read from Git objects in the canonical RepositoryWorkspace and chunked by file), relevant FeatureSpec/ImplementationSpec versions, Architecture constraints/dependency rules, canonical index neighborhood of changed principal entities, risk tier and contract constraints.
   - Output `WardenReview{findings: [WardenFindingDraft], recommendation: APPROVE|REQUEST_CHANGES, conformance: [{implementation_spec_key, conforms, notes}], summary}`.
   - Findings are persisted with `source=WARDEN`. Severity is proposed by Warden, and **`blocking` is computed by `FindingPolicy`**.
   - STATIC_REVIEW Evidence rows (one per review) are bound to the integrated SHA.
6. **Gates**: per IC, gates `INTEGRATION` (from Phase 08 checks), `WARDEN`, `SENTINEL`. Phases 12–15 add `BASELINE`, `REGRESSION` and `REPRODUCTION`. The finalizer implements TECH §18.4 exactly:

```python
def finalize_gate(gate_id):
    ic = gate.integration_candidate
    assert ic.status == READY and ic is cycle.current_ic
    assert repository.canonical_commit == ic.integrated_sha     # else FAIL-closed reason CANONICAL_REVISION_MISMATCH (README §5.9.5)
    assert all(e.commit_sha == ic.integrated_sha for e in gate_evidence)
    assert mandatory_coverage_complete(gate)        # every required obligation in gate scope SATISFIED by allowed evidence types
    assert no_blocking_findings(gate)               # OPEN/IN_REMEDIATION blocking findings in scope == 0
    decision = apply_policy(gate, policy)           # e.g. WARDEN requires review evidence present
    persist(gate.status = PASS | FAIL, inputs_hash, reasons)
    recompute_release_eligibility(cycle)            # hook; implemented in Phase 10
```

   Model recommendations are recorded as inputs but **never** decide. A recommendation of FAIL with all deterministic conditions met yields PASS plus a recorded `recommendation_overridden` note. Policy may (configurably, default **true**) treat a Warden REQUEST_CHANGES without findings as a MAJOR Finding `WARDEN_UNSPECIFIED_CONCERN` so that it surfaces for human attention.
7. **Allowed evidence for mandatory ACs**:
   - EXECUTABLE → {UNIT_TEST, INTEGRATION_TEST, API_TEST, E2E_TEST, REGRESSION_TEST, EXTERNAL_CI};
   - RUNTIME → {RUNTIME_OBSERVATION, API_TEST, E2E_TEST};
   - EXECUTABLE_OR_RUNTIME → the union;
   - REVIEW_ALLOWED → also STATIC_REVIEW.
   `MODEL_ASSESSMENT` never satisfies a mandatory AC.
8. **Remediation loop** (ARCH §11.4):
   1. For a blocking Finding, the command `remediate_finding` (HUMAN, or SYSTEM per policy `auto_remediate_blocking: true`) creates a REMEDIATION Task. Its contract is compiled from the Finding (objective, code refs → allowed_scope) and the original ImplementationSpec, with origin REMEDIATION. The Finding becomes IN_REMEDIATION.
   2. Cycle `return_to_development` → Forge → new candidate commit → new IC (supersedes the old one) → canonical index → **impacted verification only**: obligations whose evidence was FAIL, or whose covered entities intersect the remediation's `code_entity_changes` (via VERIFIES/CALLS one-hop), are re-run. Untouched PASS evidence from the superseded IC is **not** reused automatically. Instead, the deterministic `EvidenceCarryForward` rule re-binds it only if the obligation's covered entity set has unchanged content hashes between the two canonical indexes, and records a CARRIED_FORWARD evidence row that references the original. Phase 13 refines selection with ImpactAssessment.
   3. Findings are RESOLVED when the remediation IC is READY and the originating check passes (or Warden re-review no longer reports the same finding fingerprint).
9. **Waivers**: `POST /findings/{id}/waive` creates an Approval(FINDING_WAIVER). On APPROVED the Finding becomes WAIVED and no longer counts as blocking.
10. Guards: `required_gates_pass` (all gates required by policy for the cycle type are PASS for the current IC) and `remediation_tasks_exist` (ASSURANCE → DEVELOPMENT).
11. Lineage hops: AC → Evidence, Evidence → IC/SHA, Finding → remediation task.

## 5. Out of Scope

- Release eligibility and release (10). The finalizer calls a hook that is a no-op until Phase 10.
- Baseline obligations (12), impact-driven obligations (13), reproduction/regression obligations (15) and external CI evidence (16). The schema supports them now.

### Do Not Change
- Warden/Sentinel agents receive no ToolGateway action that can write gates, findings' `blocking` or evidence directly. Persistence is done by platform services from validated outputs and deterministic check results.
- Evidence rows are immutable. A re-run creates new rows.

## 6. Domain / Data Model Changes

Migration `0019_p09_evidence_obligations_coverage_gates.py` (TECH 010).

```python
class EvidenceType(StrEnum):
    UNIT_TEST = "UNIT_TEST"
    INTEGRATION_TEST = "INTEGRATION_TEST"
    API_TEST = "API_TEST"
    E2E_TEST = "E2E_TEST"
    REGRESSION_TEST = "REGRESSION_TEST"
    REPRODUCTION = "REPRODUCTION"
    RUNTIME_OBSERVATION = "RUNTIME_OBSERVATION"
    STATIC_REVIEW = "STATIC_REVIEW"
    MODEL_ASSESSMENT = "MODEL_ASSESSMENT"
    EXTERNAL_CI = "EXTERNAL_CI"
    INTEGRATION_CHECK = "INTEGRATION_CHECK"


class Evidence(Base, UUIDPkMixin, TimestampMixin):
    __tablename__ = "evidence"
    key: Mapped[str]
    project_id: Mapped[uuid.UUID]
    delivery_cycle_id: Mapped[uuid.UUID]
    integration_candidate_id: Mapped[uuid.UUID | None]
    commit_sha: Mapped[str]  # exact SHA verified
    evidence_type: Mapped[EvidenceType]
    result: Mapped[str]  # PASS | FAIL | ERROR | SKIPPED
    subject_type: Mapped[str]
    subject_id: Mapped[uuid.UUID]  # AC | BASELINE | FINDING | DEFECT | GATE | IC
    obligation_id: Mapped[uuid.UUID | None]
    check_ref: Mapped[str]  # pytest node id | probe id | artifact hash
    check_artifact_id: Mapped[uuid.UUID | None]
    log_artifact_id: Mapped[uuid.UUID | None]
    producer: Mapped[str]  # SENTINEL | WARDEN | INTEGRATION | CI | SYSTEM
    execution_id: Mapped[uuid.UUID | None]
    carried_forward_from_id: Mapped[uuid.UUID | None]
    details: Mapped[dict] = mapped_column(JSONB)  # duration, assertions, http status...


class VerificationObligation(Base, UUIDPkMixin, TimestampMixin):
    __tablename__ = "verification_obligations"
    delivery_cycle_id: Mapped[uuid.UUID]
    integration_candidate_id: Mapped[uuid.UUID]
    gate_type: Mapped[str]  # SENTINEL | BASELINE | REGRESSION | REPRODUCTION
    subject_type: Mapped[str]
    subject_id: Mapped[uuid.UUID]
    subject_key: Mapped[str]
    required: Mapped[bool]
    allowed_evidence_types: Mapped[list] = mapped_column(JSONB)
    reason: Mapped[
        str
    ]  # AC_MANDATORY | AC_OPTIONAL | IMPACT_ASSESSMENT | BASELINE_REQUIRED | DEFECT_REPRODUCTION | REGRESSION
    source_refs: Mapped[list] = mapped_column(JSONB)  # why: [{type, id, path?}]
    status: Mapped[str]  # OPEN | SATISFIED | FAILED | WAIVED


class Gate(Base, UUIDPkMixin, TimestampMixin):
    __tablename__ = "gates"
    key: Mapped[str]
    delivery_cycle_id: Mapped[uuid.UUID]
    integration_candidate_id: Mapped[uuid.UUID]
    gate_type: Mapped[str]  # INTEGRATION | WARDEN | SENTINEL | BASELINE | REGRESSION | REPRODUCTION
    status: Mapped[str]  # PENDING | PASS | FAIL | SUPERSEDED
    recommendation: Mapped[dict | None] = mapped_column(
        JSONB
    )  # agent recommendation — informational
    reasons: Mapped[list] = mapped_column(JSONB)
    inputs_hash: Mapped[str | None]
    policy_version_id: Mapped[uuid.UUID | None]
    finalized_at: Mapped[datetime | None]
    finalized_by: Mapped[str | None] = mapped_column(default=None)  # always "SYSTEM:gate_finalizer"
    __table_args__ = (UniqueConstraint("integration_candidate_id", "gate_type"),)
```

Other tables:
- `acceptance_coverage`: obligation_id, evidence_id, satisfied bool, computed_at (rows are inserted only).
- `verification_plans`: id, ic_id, execution_id, artifact_id, status (PROPOSED|VALIDATED|REJECTED), validation_report.
- `reviews`: id, ic_id, execution_id, recommendation, summary, artifact_id.

Findings (extend 08): add a `fingerprint` column (sha of source + category + normalized code refs) for resolution matching.

Triggers:
- `evidence`: immutable.
- `gates`: immutable once PASS/FAIL, except → SUPERSEDED.
- DB constraint: `gates.status IN ('PASS','FAIL') ⇒ finalized_by = 'SYSTEM:gate_finalizer'`.

Structured outputs:

```python
class PlannedCheck(BaseModel):
    obligation_key: str
    kind: Literal["EXISTING_TEST", "AUTHORED_TEST", "API_PROBE"]
    test_node_id: str | None = None
    test_code: str | None = None
    test_filename: str | None = None
    probe: ApiProbe | None = None
    rationale: str


class VerificationPlan(BaseModel):
    model_config = ConfigDict(extra="forbid")
    checks: list[PlannedCheck]
    uncovered_obligations: list[str]
    notes: list[str] = []


class WardenFindingDraft(BaseModel):
    category: Literal[
        "ARCHITECTURE_CONFORMANCE",
        "CONTRACT_CONFORMANCE",
        "SECURITY",
        "CORRECTNESS",
        "MAINTAINABILITY",
        "TEST_ADEQUACY",
        "SCOPE_VIOLATION",
        "RISK",
    ]
    severity: Literal["BLOCKER", "MAJOR", "MINOR", "INFO"]
    title: str
    detail: str
    file_path: str | None
    line_start: int | None
    spec_refs: list[str] = []


class WardenReview(BaseModel):
    model_config = ConfigDict(extra="forbid")
    findings: list[WardenFindingDraft]
    recommendation: Literal["APPROVE", "REQUEST_CHANGES"]
    conformance: list[dict]
    summary: str
```

## 7. State / Lifecycle Changes

- Gate: PENDING → PASS | FAIL (finalizer only) → SUPERSEDED (new IC). Re-finalization on new evidence creates a **new** gate row for the new IC. A FAIL gate for the same IC can be re-finalized only by creating a superseding gate row via `refinalize` after remediation obligations change (simplest rule: gates are per IC; remediation ⇒ new IC ⇒ new gates).
- Obligation: OPEN → SATISFIED | FAILED (coverage recomputation) | WAIVED (approval).
- Finding: Phase 08 machine, plus fingerprint-based RESOLVED.
- DeliveryCycle:
  - ASSURANCE → RELEASE (`required_gates_pass`);
  - ASSURANCE → DEVELOPMENT (`remediation_tasks_exist`).
- Assurance orchestration on IC READY (SYSTEM, deterministic):
  1. derive obligations;
  2. create gates PENDING;
  3. schedule Warden ANALYSIS and Sentinel plan ANALYSIS tasks;
  4. when the plan is VALIDATED, schedule the `sentinel.execute` VERIFICATION task (DETERMINISTIC);
  5. when all producers are complete, run the finalizer.

## 8. API / Contract Changes

| Method | Path | Notes |
|---|---|---|
| POST | `/integration-candidates/{id}/warden` | schedule Warden review (ARCH §20) |
| POST | `/integration-candidates/{id}/sentinel` | schedule Sentinel plan + execute |
| GET | `/integration-candidates/{id}/obligations` | with reasons + status |
| GET | `/delivery-cycles/{id}/evidence`, `/evidence/{id}` | |
| GET | `/delivery-cycles/{id}/coverage` | AC → obligations → evidence matrix |
| GET | `/delivery-cycles/{id}/findings`, `/findings/{id}` | (extended) |
| POST | `/findings/{id}/remediate` | create remediation task |
| POST | `/findings/{id}/waive` | Approval(FINDING_WAIVER) |
| GET | `/integration-candidates/{id}/gates`, `/gates/{id}` | status, reasons, recommendation, inputs hash |
| POST | `/gates/{id}/finalize` | SYSTEM/HUMAN trigger of the deterministic finalizer (agents: 403) |
| GET | `/verification-plans/{id}`, `/reviews/{id}` | |

Events: `obligation.derived`, `evidence.recorded`, `coverage.updated`, `review.completed`, `finding.created`, `finding.resolved`, `finding.waived`, `gate.finalized`, `remediation.requested`.

## 9. Services / Modules

| Path | Responsibility |
|---|---|
| `core/assurance/evidence.py` | Evidence persistence, allowed-type rules, carry-forward |
| `core/assurance/obligations.py` | derivation registry (`register_obligation_source`) |
| `core/assurance/coverage.py` | coverage computation |
| `core/assurance/gates.py` | finalizer (pure decision function + persistence) |
| `core/assurance/orchestrator.py` | deterministic assurance sequencing on IC READY |
| `core/assurance/remediation.py` | remediation task creation, resolution by fingerprint |
| `core/assurance/findings.py` | EXTEND (fingerprint, waiver) |
| `core/assurance/verification_workspace.py` | readonly + overlay workspace |
| `core/tools/handlers/test_runner.py` | EXTEND: junit parsing; `test.run_probe` (uvicorn lifecycle, ephemeral port, temp DB env) |
| `core/execution/executors/sentinel_execute.py` | deterministic executor |
| `agents/sentinel/{profile,schemas,graph}.py`, `prompts/{plan.md,summarize.md}` | Sentinel |
| `agents/warden/{profile,schemas,graph}.py`, `prompts/review.md` | Warden |
| `core/assurance/guards.py` | guards |
| `apps/control_api/routers/assurance.py` | REST |

## 10. Development Tasks

- [ ] 09.1 Add migration `0019` and the models, triggers and constraint `finalized_by`.
- [ ] 09.2 Implement the allowed-evidence-type rules and `EvidenceService` (immutable insert, carry-forward rule).
- [ ] 09.3 Implement `ObligationService` with the AC source, and a registry for later sources.
- [ ] 09.4 Implement the coverage computation.
- [ ] 09.5 Implement the verification workspace: a READONLY ExecutionWorkspace at `integrated_sha` + overlay (overlay excluded from git via the worktree's `info/exclude`) + the `CANONICAL_REVISION_MISMATCH` precondition.
- [ ] 09.6 Implement the `test.run` junit parsing and the `test.run_probe` tool (uvicorn lifecycle; `SUPPORTDESK_DATABASE_URL` pointed at a temp sqlite file for the app under test).
- [ ] 09.7 Implement the Sentinel plan profile, schema and prompt v1, and the plan validator.
- [ ] 09.8 Implement the `sentinel.execute` deterministic executor: one evidence row per check, coverage links.
- [ ] 09.9 Implement the Sentinel summarize profile (recommendation only).
- [ ] 09.10 Implement the Warden profile, schema and prompt v1, diff chunking, finding persistence with policy-computed `blocking`, and the STATIC_REVIEW evidence.
- [ ] 09.11 Implement the gate finalizer as a pure function `decide(gate_inputs, policy) -> GateDecision` plus persistence. Add the release-eligibility hook (no-op).
- [ ] 09.12 Implement the assurance orchestrator on `integration.ready`.
- [ ] 09.13 Implement remediation (task creation, IN_REMEDIATION, resolution by fingerprint) and impacted re-verification selection.
- [ ] 09.14 Implement waivers via Approval(FINDING_WAIVER).
- [ ] 09.15 Replace guard placeholders `required_gates_pass` and `remediation_tasks_exist` (assurance).
- [ ] 09.16 Register the lineage hops (AC → Evidence → IC).
- [ ] 09.17 Add the REST routes and events.
- [ ] 09.18 Write the tests in §12.

## 11. LLM-Dependent Tasks

| Profile | Why | Inputs (context source) | Output | Alias | Validation | Failure handling | Live test |
|---|---|---|---|---|---|---|---|
| `warden.review` | Semantic engineering review | integrated diff (git), specs (DB), architecture (DB), index neighborhood (canonical index) | `WardenReview` | `review` | schema; file paths must exist in the diff; spec refs must exist | FAILED → retry new Execution; gate stays PENDING (cannot PASS without review evidence when policy requires Warden) | `test_warden_review_live.py`: fixture IC with a deliberately introduced issue (route bypasses service layer, violating dependency rule) → ≥1 ARCHITECTURE_CONFORMANCE finding expected (soft on exact wording, hard on schema validity and persistence) |
| `sentinel.plan` | Semantic test design mapping ACs to checks | obligations + AC text (DB), tests/routes/schemas (canonical index) | `VerificationPlan` | `verification_planning` | node IDs/routes exist; every required obligation has a check | plan REJECTED → retry with errors (≤2) → FAILED | `test_sentinel_plan_live.py`: supportdesk_r1 + ACs → validated plan executes and produces evidence |
| `sentinel.summarize` | Human-readable recommendation | evidence summary | `SentinelRecommendation` | `verification_planning` | schema | non-blocking; gate unaffected | covered in workflow |

Execution of checks is **deterministic** (`sentinel.execute`). PASS/FAIL comes from executable/runtime evidence (TECH §18.3). Model calls and costs are linked through `model_calls.execution_id`.

## 12. Testing Strategy

### Unit Tests
- `gates.decide` truth table:
  - missing mandatory evidence → FAIL;
  - evidence for a different SHA → FAIL;
  - a blocking Finding → FAIL;
  - all satisfied → PASS even if the recommendation is FAIL (override recorded);
  - MODEL_ASSESSMENT-only coverage → FAIL;
  - STATIC_REVIEW for a REVIEW_ALLOWED AC → satisfied.
- Obligation derivation: mandatory/optional, reasons recorded.
- Carry-forward eligibility (content-hash equality of the covered entity set).
- Finding fingerprint stability.

### Persistence Tests
- Evidence immutability. Gate immutability after finalization. The `finalized_by` constraint rejects an agent/other value.

### Security Tests
- An AGENT token calling `/gates/{id}/finalize` gets 403.
- No Warden/Sentinel profile has an `allowed_tools` entry that writes gates or evidence (static assertion over the profile registry).

### Integration Tests (deterministic executor with fixture IC; checks are real pytest runs)
- `supportdesk_r1` as the IC with 3 mandatory ACs mapped to existing tests:
  - all pass → SENTINEL gate PASS;
  - break one test in a variant commit → FAIL with reason `OBLIGATION_FAILED:<AC>`.
- An evidence row with `commit_sha` ≠ IC SHA (inserted directly) is ignored by the finalizer and its reason is recorded.
- Canonical binding: Warden's diff range is `ic.base_sha..integrated_sha`, and Sentinel's verification workspace HEAD is `integrated_sha`. If the canonical revision is reverted after evidence is recorded (Phase 08 guardian, simulated cancel-and-reopen), `finalize_gate` returns FAIL with `CANONICAL_REVISION_MISMATCH`, never PASS.
- A waiver approval removes the blocking finding and the gate PASS becomes possible.

### Runtime / Live-LLM Tests
- The §11 live tests.

### Workflow Tests (live)
- Remediation loop: a fixture cycle where the Sentinel-executed check fails → Finding → `remediate_finding` → live Forge fix → new IC → impacted re-verification only (assert that untouched obligations have CARRIED_FORWARD evidence and touched ones were re-run) → gates PASS.

### Commands
```
make check
uv run pytest -m integration tests/integration/assurance
LLM_LIVE_TESTS=1 uv run pytest -m "live_llm or workflow" --live-required tests/integration/live_llm/assurance tests/workflow/assurance
```

## 13. Milestone

For a READY IntegrationCandidate, Olympus deterministically derives verification obligations from mandatory ACs. Live Warden produces engineering findings and live Sentinel produces a validated verification plan, whose checks run deterministically against the exact integrated SHA to produce immutable evidence. The deterministic Gate Finalizer alone sets Gate PASS/FAIL from evidence, coverage, findings and policy, and a failing assurance drives a remediation execution and a new IC with impacted-only re-verification.

## 14. Acceptance Criteria

- [ ] Every Evidence row references the exact IC and `integrated_sha`. Evidence for any other SHA cannot satisfy obligations.
- [ ] Warden reviews and Sentinel checks target the exact integrated SHA, which is the Repository's canonical revision: the verification ExecutionWorkspace HEAD equals `integrated_sha` equals `canonical_commit`. A gate cannot PASS unless `Repository.canonical_commit == ic.integrated_sha`.
- [ ] A mandatory AC without allowed evidence cannot become SATISFIED. MODEL_ASSESSMENT never satisfies a mandatory AC.
- [ ] Warden and Sentinel cannot set Gate status (DB constraint + API 403 + no tool path).
- [ ] The gate decision is a pure deterministic function of evidence, coverage, findings and policy (truth-table tests).
- [ ] Finding `blocking` is computed by policy, not by agents.
- [ ] A blocking Finding produces a remediation Task and contract, which produces a new Execution, a new IC and new gates.
- [ ] Re-verification after remediation re-runs impacted obligations and carries forward only provably unchanged evidence (with reference).
- [ ] Waivers require an explicit Approval(FINDING_WAIVER).
- [ ] Each obligation records why it was chosen (reason + source refs).
- [ ] Warden and Sentinel planning run through the live ModelRouter path, and check execution is deterministic.

## 15. Exit Criteria

- §14 green, including live tests and the remediation workflow (evidence recorded).
- The obligation source registry and finalizer hook are documented for 10/12/13/15.
- Guard placeholders for this phase are removed.
- `STATUS.md`: invariants "mandatory ACs require evidence" and "Warden/Sentinel cannot directly finalize gates" checked; Warden/Sentinel LLM readiness updated.

## 16. Dependencies

### Depends On
- 08: IC, canonical index, findings base.

### Blocks
- 10.

### Can Run In Parallel With
- None.

## 17. Risks / Implementation Notes

- **Runtime probe sandboxing:** starting the app under test executes generated code. Run it under the Phase 04 shell policy with no secrets in the env and a temp DB. Phase 18 containerizes it.
- **Flaky tests:** treat a check that FAILs then PASSes on retry as FAIL plus a `FLAKY_TEST` MINOR finding. Policy may allow ≤1 deterministic retry and must record both evidence rows.
- **Model risk:** Sentinel may propose checks that trivially pass (for example `assert True`). Policy `sentinel.authored_test_min_assertions` (default 1, AST-checked: at least one `assert` referencing the response/result) plus Warden review of authored checks mitigate this.
- **Deferred:** external CI evidence (16), baseline gates (12) and impact-driven obligation selection (13).

## 18. Deliverables

- Code: `core/assurance/*`, `agents/warden/*`, `agents/sentinel/*`, `core/execution/executors/sentinel_execute.py`, test-runner extensions.
- Migration: `0019`.
- APIs/events: §8.
- Config: `assurance:`/`findings:` policy sections.
- Tests: §12 suites.
