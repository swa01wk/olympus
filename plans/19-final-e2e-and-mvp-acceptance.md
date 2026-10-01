# Phase 19 — Final Four-Journey E2E and MVP Acceptance

## 1. Objective

Prove the Olympus MVP Definition of Done (ARCH §26, TECH §32) on **one persistent Project** through **one control-plane kernel**, from a clean environment, with live LLM execution at every model-dependent stage:

```
PROJECT: SUPPORTDESK
  DC-001 GREENFIELD_BUILD      PRD → Features → Specs → Tasks → Code → Code Index → Release R1
  DC-002 BROWNFIELD_ONBOARDING Repo@R1 → Code Graph → Recovered Specs/Features → Baselines → READY_FOR_CHANGE
  DC-003 FEATURE_CHANGE        Ticket Priority → Spec Delta → Code Impact → Code Delta → Re-index → Release R2
  DC-004 BUG_FIX               Closed-ticket 500 → Reproduction → Spec/Code Path → Repair → Re-index → Release R3
```

This phase adds **no new domain capability**. It delivers:

1. A clean-environment bootstrap and preflight for the full stack.
2. A **chained demo driver** and journey test that run DC-001 → DC-004 on the same Project, with no seeded trusted state. This differs from Phases 14 and 15, which use `seed_trusted_project` for isolation.
3. The deterministic **defect-introduction strategy** for the chained demo (resolution of Q-05).
4. **Restart boundaries** between cycles, which prove that canonical state survives runtime loss.
5. A read-only **MVP Acceptance Evaluator**. It computes every term of `MVP_COMPLETE` (ARCH §26) and `TECH_MVP_COMPLETE` (TECH §32) from authoritative APIs and produces an evidence report.
6. An **acceptance matrix** that maps every ARCH §22 architectural acceptance test and every TECH §31 mandatory technical criterion to passing test node IDs.
7. A Playwright **operator walkthrough** over the final chained state, including the R3 release approval performed through the dashboard.
8. Two consecutive clean-environment runs (one with failure injection). Results are recorded in `STATUS.md`, and the MVP is declared `MVP_COMPLETE` only if the evaluator returns true.

## 2. Architectural Context

- **Position:** acceptance layer over the whole system. It exercises every plane (Governance, Work, Execution, Intelligence) and both integration directions.
- **Upstream:** every phase 00–18. Directly: 10 (Greenfield harness, `assert_live_llm_proof`), 12 (Brownfield journey), 14 (Feature Change), 15 (Bug Fix), 16 (Gitea, CI runner, webhooks, repository sync for Q-05), 17 (dashboard, Playwright), 18 (`assert_system_invariants`, chaos harness, sandbox, backup/restore).
- **Downstream:** none. This is the MVP exit gate.
- **Lifecycle stages:** all four journey lifecycles, run in sequence on one Project.
- **Invariants:** all 38 prompt invariants and the `STATUS.md` §7 tracker. In particular:
  - 18–19: canonical index pointer equals the current IC/release SHA, and candidate indexes are distinguishable.
  - 28–30: Brownfield DC-002 runs in an isolated context even though the Project already has a canonical model.
  - 31–35: Feature Change uses a spec delta and graph impact; Bug Fix reproduces first and proves regression.
  - 36: restart does not lose canonical delivery state.
  - 37: product-to-code lineage is queryable across R1, R2 and R3.
  - 38: inbound and outbound integrations are auditable, idempotent and correlated.
  - LLM policy: journey proof uses live providers only.

## 3. Current Repository Assessment

Inspection on 2026-10-01: the repository contains only the two source documents and `plans/`. Nothing in this phase exists.

### Existing
- (after 10) `tests/journey/{conftest,helpers}.py`, `assert_live_llm_proof`, `scripts/demo/greenfield.py` — **RETAIN / EXTEND** (the chained driver reuses the helpers and generalizes the Greenfield script).
- (after 12, 14, 15, 16) per-journey tests and fixtures — **RETAIN**. They stay as isolated journey proofs. Phase 19 does not replace them.
- (after 14) `tests/journey/seed.py::seed_trusted_project` — **RETAIN, but forbidden in Phase 19**. The chained run must establish trust only through DC-001 and DC-002.
- (after 16) `deploy/compose.test.yaml` (Gitea, MinIO, CI runner), signed webhooks, `RepositorySyncService` — **RETAIN**.
- (after 17) dashboard + `tests/ui` Playwright setup — **EXTEND** with the walkthrough spec.
- (after 18) chaos harness, fault points, `assert_system_invariants`, `GET /ops/invariants`, backup/restore scripts — **RETAIN**.

### Partial
- None.

### Missing
- Chained driver, defect injector, restart-boundary helper, chained fixtures, chained journey test, MVP Acceptance Evaluator, acceptance matrix and checker, Playwright walkthrough, demo compose overlay, Make targets and demo runbook — **ADD**.

### Refactor / Migration Required
- None planned. Any defect found while running this phase is fixed in the **owning phase's modules**. That fix must keep that phase's §14 criteria green (re-run its suites) and is recorded in the `STATUS.md` Architecture Drift Log only if it changes a contract.

| Component | Classification |
|---|---|
| `scripts/demo/bootstrap.sh`, `scripts/demo/preflight.py` | ADD |
| `scripts/demo/chained/{driver,stages,restart,inject_defect,probe}.py`, `scripts/demo/run_mvp.py` | ADD |
| `deploy/compose.demo.yaml` | ADD |
| `tests/fixtures/supportdesk/chained/*` | ADD |
| `tests/journey/chained/{assertions,__init__}.py`, `tests/journey/test_mvp_chained_supportdesk.py` | ADD |
| `scripts/acceptance/{evaluate_mvp,check_matrix}.py`, `tests/acceptance/matrix.yaml` | ADD |
| `apps/dashboard/tests/e2e/mvp_walkthrough.spec.ts` | ADD |
| `Makefile` targets `mvp-env`, `mvp-demo`, `mvp-acceptance` | EXTEND |
| `docs/demo/MVP_DEMO_RUNBOOK.md` | ADD |

## 4. Scope

### 4.1 Clean-environment bootstrap and preflight
- `make mvp-env` performs these steps:
  1. Remove the demo volumes.
  2. Bring up the stack: `docker compose -f docker-compose.yml -f deploy/compose.test.yaml -f deploy/compose.demo.yaml --profile integrations --profile demo up -d`. This starts postgres, gitea, ci-runner, minio, control-api, scheduler-worker, execution-worker (Linux sandbox image from Phase 18) and the dashboard. Add the `observability` overlay when `MVP_OBSERVABILITY=1`.
  3. Run `alembic upgrade head`.
  4. Seed actors: `lead` (HUMAN; OPERATOR, APPROVER) and `viewer` (HUMAN; VIEWER).
  5. Create the Gitea organization, the empty repository `supportdesk` and the webhook secret.
  6. Register connector configs (git_provider=gitea, issue_tracker=gitea, ci=http_ci, artifact=artifact_s3 on MinIO, deployment=deploy_local).
- `scripts/demo/preflight.py` fails fast unless **all** of the following hold:
  - `OLYMPUS_ENV=journey` and `LLM_LIVE_TESTS=1`;
  - provider credentials resolve for every alias in `config/models.yaml`, and one cheap live `ModelRouter.invoke` with `diagnostic.structured_echo` succeeds;
  - the embedding alias works (Q-04);
  - `/ready` is 200 on control-api and `/healthz` is 200 on both workers;
  - the Linux sandbox is available (Phase 18 `/ready` check);
  - Gitea, the CI runner and MinIO are healthy;
  - `LLM_TEST_BUDGET_USD` is set and at least the Q-06 ceiling;
  - `FakeProvider` is not constructible (Phase 02 guard).

### 4.2 Chained driver (`scripts/demo/chained/`)
- One driver drives every step through the **public control API only**, with typed commands and `Idempotency-Key`s. The same driver is used by `scripts/demo/run_mvp.py` (manual demo) and by the journey test.
- Human decisions come only from human-authored fixtures under `tests/fixtures/supportdesk/chained/`. They are keyword- or property-matched, never model output, and the HUMAN `lead` token applies them.
- Options:
  - `--pause-before <stage>` lets Playwright perform a decision in the UI;
  - `--chaos` enables the §4.6 fault plan;
  - `--report <dir>` writes per-stage timings, cost and IDs.

#### Stage A — DC-001 Greenfield (reuses the Phase 10 flow)
1. Create Project `SUPPORTDESK` and cycle DC-001. Upload `tests/fixtures/supportdesk/PRD.md` (Phase 05) through the document adapter.
2. Run live Kira decomposition. Answer clarifications from `clarification_answers.yaml` (Phase 10). **Restart boundary RB-A** (§4.4) happens while a clarification is pending, so the answer resumes the Execution from its continuation package after the runtime state is lost.
3. Approve scope, then the Atlas architecture, ImplementationSpecs and TaskPlan (all live), each with a scripted approval.
4. Forge executions, IC, canonical index, Warden, Sentinel, gates, eligibility, R1 approval and R1 execution follow.
5. Stratos pushes `main` and tag `olympus/release/R1` to Gitea (Phase 16). Run `deploy_local` R1 (policy `release.deploy.require_approval=true` → scripted approval).
6. Record `S_R1 = integrated_sha(R1)`.

#### Stage B — DC-002 Brownfield on the same Project and repository at `S_R1`
1. **Restart boundary RB-B.**
2. Create cycle DC-002 against the existing Repository with `base_sha = S_R1`.
3. Run RECON → CODE_INDEX → RECOVERED_SPEC (live Scout) → BASELINE (live `sentinel.characterize`) → READINESS → READY.
4. Isolation: the `ScoutContextBuilder` manifest (Phase 11) must contain **no** refs to DC-001's product model, artifacts, model calls or runtime checkpoints, even though they exist in the same database.
5. The Phase 11 reconciliation report (Q-02) classifies recovered specs as MATCHED, NEW, MISSING or DIVERGENT against DC-001's canonical model.
6. Apply scripted review decisions from `chained/brownfield_review.yaml`. Rules use deterministic properties only:
   - MATCHED → `CONFIRM_EXISTING` (no new canonical lineage);
   - NEW with a tested route → `PROMOTE_AS_CANONICAL`;
   - NEW without tests → `DEFER`;
   - DIVERGENT → `REJECT_AS_NOT_INTENDED` when the canonical AC disagrees (canonical intent wins), else `DEFER`;
   - MISSING → recorded as an UNCERTAINTY and then `ACCEPT_KNOWN_GAP`;
   - recovered architecture → `CONFIRM_EXISTING` against the approved DC-001 Architecture.
7. `declare_ready` sets `Project.readiness_state = READY_FOR_CHANGE` and creates a new BaselineSet. Its number is the next in sequence; the run asserts monotonicity, not a fixed number.

#### Stage C — DC-003 Feature Change via the issue tracker (reuses the Phase 14 and 16 flows)
1. **Restart boundary RB-C.**
2. Create a Gitea issue from `chained/change_issue.md` ("Add ticket priority: LOW, MEDIUM, HIGH") labeled `olympus:change`. The signed webhook creates a ChangeRequest and cycle DC-003. A duplicate webhook redelivery is sent deliberately and must be acknowledged as DUPLICATE.
3. Run live `kira.change_interpret` → FeatureSpec v(n+1) → approved SpecDelta → ImpactAssessment (structural first) → architecture delta (only if suggested; approve or decline) → ImplementationSpec delta → TaskPlan → contracts → live Forge.
4. Then IC → Gitea PR → CI runner evidence at the IC SHA → incremental re-index → link refresh → Warden and Sentinel (new ACs plus impacted baselines) → gates → R2.
5. Push R2 to Gitea, run `deploy_local` R2, then comment on and close the issue.
6. Record `S_R2`.

#### Stage D — defect introduction (Q-05, strategy A; §4.3), then DC-004 Bug Fix
1. **Restart boundary RB-D.**
2. Run `inject_defect.py` to push an external commit `S_D` to Gitea `main`.
3. Phase 16 sync classifies it as `EXTERNAL_FAST_FORWARD` → canonical index at `S_D` (`source=EXTERNAL_PUSH`) → link refresh → StalenessService marks impacted baselines `REVALIDATION_REQUIRED`.
4. Create a Gitea issue from `chained/defect_issue.md` ("Updating a CLOSED ticket returns HTTP 500") labeled `olympus:defect` → Defect + DC-004 with `affected_sha = S_D`.
5. Run live triage, then live Sentinel reproduction at `S_D` (PRE_REPAIR REPRODUCTION FAIL with a 500 signature, stable over 2 runs) before any repair commit.
6. Run live expected behavior. It must classify as SPECIFIED, citing the approved closed-ticket 409 AC from DC-001 (or its DC-003 successor version).
7. Run `CodePathResolver`, then live `warden.root_cause` (INFERENCE), then IA, then the live REPAIR ImplementationSpec and TaskPlan (scripted approval), then live Forge.
8. Then IC → re-index at the IC SHA → REGRESSION:
   - the original reproduction artifact passes at the IC SHA;
   - the regression test passes at the IC SHA and fails at `S_D`;
   - impacted baselines pass.
9. Run Warden and Sentinel, then gates, then eligibility.
10. **R3 approval is performed in the dashboard by Playwright** (`--pause-before approve_release:DC-004`).
11. Execute R3, push it to Gitea, then close the defect issue.

### 4.3 Defect introduction strategy (Q-05)
R1 is generated by a live model, so its code shape is not known in advance. The injector is a **human-authored, deterministic tool** (test input, not model output). It is located through Olympus's own canonical index and applied as an **external** commit, which is exactly the inbound path Phase 16 provides.

1. **Precondition probe** (`probe.py`): in a scratch clone at `S_R2`, start the app through its indexed FastAPI entry point, using the Phase 09 `test.run_probe` style sandboxed runner.
   - Discover routes from the app's OpenAPI document: ticket create (`POST /tickets`) and the status-update or close route (`PATCH|PUT /tickets/{id}`, `POST /tickets/{id}/close`, or a status field update).
   - Create a ticket, close it, then attempt an update.
   - The probe must observe **409**. If it does not, the injector aborts: R1/R2 already violate the AC, and the operator must investigate.
2. **Target location:** query `GET /code/entities` and the Phase 07 relations at the canonical index for `S_R2`. Start from the ROUTE entity of the update route and follow its `CALLS` closure (depth ≤ 4). Select statements that raise the 409, recognized as one of:
   - `raise HTTPException(status_code=409 | status.HTTP_409_CONFLICT, ...)`;
   - a `raise` of a project exception class that a registered FastAPI exception handler maps to 409, also resolved through the index.
3. **Transform:** exactly one raise site must match; otherwise abort with a diagnostic listing the candidates. A LibCST transform replaces it with `raise RuntimeError("ticket is closed")`. With no handler, an unhandled `RuntimeError` produces HTTP 500.
4. **Verification:** the probe at the injected tree observes **500**.
5. **Commit and push:** commit as external author `External Developer <external@supportdesk.invalid>`. Push directly to Gitea `main` with the Gitea admin token held by the demo script. This is outside Olympus by design: it simulates a human developer, not an Olympus action.
6. **Fallback (strategy B; only if Q-05 is resolved to allow it):** run Stage D on the hand-written `supportdesk_defect_closed_update` fixture repository (Phase 15) in a second Project. This breaks the single-Project narrative, so it is recorded in `STATUS.md` as a waiver and never used silently.

### 4.4 Restart boundaries
`restart.py::restart_boundary(name)` performs these steps:
1. Wait until no Execution is in LEASED, STARTED, OUTPUT_PRODUCED or VALIDATING. Checkpointed Executions are allowed.
2. Capture a **canonical fingerprint**: hashes of project, cycles, tasks, executions, snapshots, evidence, gates, approvals, ICs, releases, index pointers and lineage query results.
3. Stop control-api, scheduler-worker and execution-worker (SIGTERM).
4. Run `TRUNCATE` on every table in schema `langgraph_runtime` (and drop its checkpoint blobs).
5. Start the processes and wait for `/ready`.
6. Recompute the fingerprint and assert it is equal. Then run `assert_system_invariants(project)` (Phase 18).

### 4.5 Cross-cycle assertions (`tests/journey/chained/assertions.py`)
- **Lineage:**
  - forward from the Feature for ticket status/close reaches R1, R2 and R3;
  - reverse from each changed CodeEntity in R2 and R3 reaches its FeatureSpec version, Feature, Capability and ProductSource (PRD, change issue, defect issue).
- **Release chain:**
  - R1, R2 and R3 manifests reference their exact `integrated_sha`;
  - Gitea `main` == `S_R3`, and the tags `olympus/release/R1..R3` point at the manifest SHAs;
  - `released_index_version_id.commit_sha == S_R3`.
- **Canonical index:** at every ASSURANCE entry the pointer `commit_sha` equals the cycle's IC `integrated_sha`. Candidate index versions are `kind=CANDIDATE` and DISCARDED.
- **Brownfield:**
  - there is no CANONICAL FeatureSpec without a PROMOTION approval or a GENERATED_LINEAGE origin;
  - DC-002 MATCHED specs produced no duplicate lineage keys;
  - every HUMAN_CONFIRMED link references a DISCOVERED link;
  - FACT, INFERENCE and UNCERTAINTY counts are non-zero and distinguishable through the API.
- **Feature Change:** every verification obligation created for DC-003 has a STRUCTURAL source and a recorded reason. FeatureSpec v(n) is unchanged after v(n+1).
- **Bug Fix:** the PRE_REPAIR evidence `created_at` is earlier than the first repair candidate commit. The RCA is INFERENCE and is referenced by no Evidence.
- **Baselines:** BaselineSet sequence numbers increase monotonically. Every baseline in the final set PASSes at `S_R3`.
- **Integrations:**
  - every inbound event in the run is unique by source identity, and the deliberate duplicate redelivery is recorded as DUPLICATE;
  - every outbound connector action carries an idempotency key, correlation ID and external ID, and is linked through `external_links`.
- **LLM proof:**
  - `assert_live_llm_proof` passes per cycle with the stage lists from Phases 10, 12, 14 and 15;
  - globally, `SELECT count(*) FROM model_calls WHERE provider='fake'` = 0, and every SUCCEEDED call has a `provider_request_id`.
- **Governance:**
  - every Approval in the run is decided by a HUMAN actor;
  - `audit/verify` passes for the project;
  - no Gate has `finalized_by` other than the Gate Finalizer.

### 4.6 Failure-injection run (`--chaos`)
The second clean run enables, on top of the normal flow:
- RC-01-style `kill -9` of the execution worker mid-Forge in DC-003;
- a fault-proxy timeout-after-forward on the Gitea issue-close call in DC-003, which must go through reconciliation and end with exactly one close;
- a lease expiry during `sentinel.execute` in DC-004;
- a control-api restart during SSE streaming while the Playwright walkthrough is connected.

Every injected failure must leave a FAILED/expired record in history and a completed retry. The final assertions in §4.5 must still pass.

### 4.7 MVP Acceptance Evaluator (`scripts/acceptance/evaluate_mvp.py`)
- **Read-only.** It uses a VIEWER token, and the test asserts it made zero mutating calls.
- It computes each conjunct of ARCH §26 `MVP_COMPLETE` and TECH §32 `TECH_MVP_COMPLETE` as a named check with `{name, ok, evidence_refs[], query}`. Examples:
  - `greenfield_source_to_feature_spec_to_verified_R1` → DC-001 COMPLETE, R1 RELEASED, manifest SHA verified;
  - `canonical_product_semantics_are_unambiguous` → no duplicate CANONICAL lineage keys, and every FeatureSpec has exactly one ImplementationSpec lineage per version;
  - `code_index_matches_current_integration_candidate` → pointer SHA == `S_R3` == the last IC SHA;
  - `inbound_events_are_authenticated_idempotent_and_traceable`;
  - `connector_partial_failures_are_reconcilable` (requires the chaos run's reconciliation item RESOLVED_EXECUTED);
  - `canonical_state_survives_runtime_restart` (RB-A..RB-D fingerprints equal);
  - `live_LLM_required_flows_do_not_depend_on_mock_outputs`;
  - and every remaining term, one check per conjunct (the full list in the evaluator is the union of ARCH §26 and TECH §32, de-duplicated).
- Output: `var/olympus/reports/mvp_acceptance_<run_id>.json` plus a Markdown summary. The exit code is non-zero if any check fails.

### 4.8 Acceptance matrix (`tests/acceptance/matrix.yaml` + `scripts/acceptance/check_matrix.py`)
- One entry per ARCH §22 row (24 rows) and per TECH §31 row (13 rows). Each entry lists ≥1 pytest node ID from Phases 01–19 (or Playwright spec ID) that proves it.
- `check_matrix.py` reads the junit XML of the final runs. It fails if any entry has no mapped test, if a mapped test is missing from the junit, or if a mapped test did not pass. **Skipped counts as failed.**

### 4.9 Playwright operator walkthrough (`apps/dashboard/tests/e2e/mvp_walkthrough.spec.ts`)
It runs against the live chained stack:
1. Wait for the driver's pause at `approve_release:DC-004`.
2. Log in as `lead`. The Governance inbox shows the pending Approval(RELEASE) for R3. The Release view shows the exact IC SHA, all required gates PASS (INTEGRATION, REPRODUCTION, REGRESSION, BASELINE, WARDEN, SENTINEL) and all eligibility conditions OK. Approve through the UI.
3. The driver resumes and R3 executes.
4. Verify the views:
   - Project overview: current release R3; DC-001..DC-004 terminal; `READY_FOR_CHANGE`.
   - Lineage explorer: Feature → R1, R2, R3.
   - Brownfield view: knowledge chips are distinct.
   - Impact Explorer (DC-003): STRUCTURAL labels and paths.
   - Assurance (DC-004): REPRODUCTION PRE/POST evidence.
   - Integrations: issue events, the PR, CI evidence and the reconciliation item from the chaos run.
5. Log in as `viewer`: decision controls are disabled, and a forged approval request returns 403.

## 5. Out of Scope

- New domain entities, state machines, agents, connectors or APIs. If the chained run reveals a missing capability, it is a defect in the owning phase and is fixed there.
- Performance or load testing, and multi-project or multi-tenant demos (ARCH §25).
- Cloud deployment; `deploy_local` only.
- Non-Python reference applications.

### Do Not Change
- Do not use `seed_trusted_project`, hand-authored model outputs, `FakeProvider`, or any canned Kira/Atlas/Scout/Forge/Warden/Sentinel/Orchestrator response anywhere in this phase.
- Do not relax any eligibility condition, gate policy, promotion rule, confidence cap or approval requirement to make the chained run pass. Escalate through the drift protocol (README §9).
- Do not let the defect injector call any Olympus mutating API. It acts only as an external Git user.
- Do not mark `STATUS.md` Overall State `MVP_COMPLETE` unless the evaluator exits 0 on two consecutive clean runs (one with `--chaos`) and `check_matrix.py` exits 0.

## 6. Domain / Data Model Changes

None. No migrations. The evaluator, matrix checker and driver are clients of existing APIs.

Report shape (file artifact, not a DB table):

```python
class AcceptanceCheck(BaseModel):
    name: str
    source: Literal["ARCH_26", "TECH_32", "ARCH_22", "TECH_31", "STATUS_DOD"]
    ok: bool
    evidence_refs: list[str]
    query: str
    detail: str | None = None


class MvpAcceptanceReport(BaseModel):
    run_id: str
    started_at: datetime
    finished_at: datetime
    chaos: bool
    project_key: str
    cycles: dict[str, str]  # DC key → terminal state
    releases: dict[str, str]  # R key → integrated_sha
    llm: dict[str, Decimal | int]  # calls, tokens, cost_usd by alias
    restart_fingerprints: dict[str, tuple[str, str]]  # boundary → (before, after)
    checks: list[AcceptanceCheck]
    mvp_complete: bool  # all(c.ok for c in checks)
```

## 7. State / Lifecycle Changes

No new states. Expected terminal states at the end of a run:

| Object | Expected terminal state |
|---|---|
| DC-001 | COMPLETE |
| DC-002 | READY (Project `readiness_state = READY_FOR_CHANGE`) |
| DC-003 | COMPLETE |
| DC-004 | COMPLETE |
| ChangeRequest (DC-003) | RELEASED |
| Defect (DC-004) | RELEASED |
| R1, R2, R3 | RELEASED; deployments HEALTHY for R2 and R3 (R1 superseded or rolled forward) |
| ReconciliationItems | none OPEN or ESCALATED at the end |
| Findings | no OPEN blocking findings |

## 8. API / Contract Changes

No new endpoints. The driver and evaluator use the existing APIs from Phases 01–18.

CLI contracts:

```
scripts/demo/run_mvp.py   [--chaos] [--pause-before STAGE] [--report DIR] [--strategy A|B]
scripts/acceptance/evaluate_mvp.py --project SUPPORTDESK --run-id ID --out DIR   # exit 0 iff mvp_complete
scripts/acceptance/check_matrix.py --matrix tests/acceptance/matrix.yaml --junit DIR/*.xml   # exit 0 iff all rows proven
```

Make targets:

```
make mvp-env          # clean volumes + stack + migrate + seed + gitea/connectors + preflight
make mvp-demo         # mvp-env + run_mvp.py + Playwright walkthrough + evaluate + check_matrix
make mvp-demo-chaos   # same with --chaos
make mvp-acceptance   # mvp-demo then mvp-demo-chaos on fresh environments; both must pass
```

## 9. Services / Modules

| Path | Responsibility |
|---|---|
| `scripts/demo/bootstrap.sh` | clean volumes, compose up, migrate, seed actors, Gitea org/repo/webhook, connector configs |
| `scripts/demo/preflight.py` | §4.1 checks; non-zero exit with the failing check names |
| `scripts/demo/chained/driver.py` | API client, wait helpers, scripted-decision application, pause/resume, report writer |
| `scripts/demo/chained/stages.py` | Stage A–D functions (§4.2) |
| `scripts/demo/chained/restart.py` | restart boundary + canonical fingerprint |
| `scripts/demo/chained/inject_defect.py`, `probe.py` | Q-05 strategy A (§4.3) |
| `scripts/demo/run_mvp.py` | CLI entry |
| `deploy/compose.demo.yaml` | workers, dashboard, `demo` profile wiring, Gitea webhook URL |
| `tests/fixtures/supportdesk/chained/{brownfield_review.yaml,change_issue.md,defect_issue.md,approvals.yaml}` | human-authored inputs |
| `tests/journey/chained/assertions.py` | §4.5 |
| `tests/journey/test_mvp_chained_supportdesk.py` | journey test that runs the driver and the assertions |
| `scripts/acceptance/evaluate_mvp.py` | §4.7 |
| `tests/acceptance/matrix.yaml`, `scripts/acceptance/check_matrix.py` | §4.8 |
| `apps/dashboard/tests/e2e/mvp_walkthrough.spec.ts` | §4.9 |
| `docs/demo/MVP_DEMO_RUNBOOK.md` | prerequisites, commands, expected outputs, troubleshooting, cost and duration |

## 10. Development Tasks

- [ ] 19.1 Write `deploy/compose.demo.yaml` and the `mvp-env`, `mvp-demo`, `mvp-demo-chaos` and `mvp-acceptance` Make targets.
- [ ] 19.2 Write `scripts/demo/bootstrap.sh` (Gitea org/repo/webhook creation through the Gitea admin API, connector configs through Olympus APIs).
- [ ] 19.3 Write `scripts/demo/preflight.py` with every §4.1 check and a live diagnostic call.
- [ ] 19.4 Implement the chained driver: API client, `wait_for`, scripted decisions, `--pause-before`, report writer.
- [ ] 19.5 Implement the restart boundary with the canonical fingerprint and the `assert_system_invariants` call.
- [ ] 19.6 Write the chained fixtures (`brownfield_review.yaml` rules by deterministic properties, `change_issue.md`, `defect_issue.md`, `approvals.yaml`).
- [ ] 19.7 Implement Stage A (DC-001), including RB-A while a clarification is pending, plus the push and deploy of R1.
- [ ] 19.8 Implement Stage B (DC-002) on the same Project and repository, including the context-isolation manifest assertion and the reconciliation-driven review.
- [ ] 19.9 Implement Stage C (DC-003) through the Gitea issue, including the deliberate duplicate webhook redelivery.
- [ ] 19.10 Implement the precondition probe and the defect injector (strategy A), and abort with diagnostics when there is no single target.
- [ ] 19.11 Implement Stage D (DC-004) with the external push, staleness checks, reproduction-before-repair, and the pause for UI release approval.
- [ ] 19.12 Implement the §4.5 cross-cycle assertions and `test_mvp_chained_supportdesk.py`.
- [ ] 19.13 Implement the `--chaos` fault plan (§4.6) using the Phase 16 fault proxy and Phase 18 fault points.
- [ ] 19.14 Implement the MVP Acceptance Evaluator with one check per ARCH §26 / TECH §32 conjunct and per `STATUS.md` §11 final condition.
- [ ] 19.15 Write `tests/acceptance/matrix.yaml` (all 24 ARCH §22 rows and all 13 TECH §31 rows) and `check_matrix.py`.
- [ ] 19.16 Write the Playwright walkthrough, including the UI R3 approval and the VIEWER 403 check.
- [ ] 19.17 Write `docs/demo/MVP_DEMO_RUNBOOK.md`.
- [ ] 19.18 Run `make mvp-acceptance` from a fresh clone on a Linux host. Record run IDs, durations, LLM cost per alias, evaluator reports and matrix results in `STATUS.md`.
- [ ] 19.19 Update `STATUS.md`: all trackers, Journey Readiness evidence, MVP Definition of Done, and Overall State (`MVP_COMPLETE` only if §15 holds).

## 11. LLM-Dependent Tasks

No new agent profiles or prompts. This phase **exercises** every model-dependent profile live, in one chained run:

| Cycle | Profiles (alias) |
|---|---|
| DC-001 | `kira.decompose` (product_decomposition), `atlas.propose_architecture` (architecture), `kira.implementation_spec` + `kira.task_plan` (planning), `forge` (implementation), `warden.review` (review), `sentinel.plan` / `sentinel.summarize` (verification_planning) |
| DC-002 | `scout.survey`, `scout.recover_feature` (repository_reasoning), `sentinel.characterize` (verification_planning) |
| DC-003 | `kira.change_interpret` (product_decomposition), `atlas.architecture_delta` (architecture, if suggested), `kira.implementation_spec` DELTA + `kira.task_plan` (planning), `forge`, `warden.review`, `sentinel.plan`; `embedding` for semantic expansion |
| DC-004 | `kira.defect_triage`, `sentinel.reproduce`, `kira.expected_behavior`, `warden.root_cause`, `kira.implementation_spec` REPAIR + `kira.task_plan`, `forge`, `warden.review`, `sentinel.plan` |
| Walkthrough (optional) | `orchestrator.converse` (orchestration): one EXPLAIN query "why is R3 eligible?" with no command executed |

- **Validation, retries, failure handling:** unchanged from the owning phases. Model variance is absorbed only by policy-bounded retries and remediation loops, never by canned output.
- **Cost and token logging:** the driver report and the evaluator aggregate `model_calls` by alias and cycle. The run fails if the total exceeds `LLM_TEST_BUDGET_USD`.
- **Live acceptance test:** `tests/journey/test_mvp_chained_supportdesk.py` (`journey`, `--live-required`).

## 12. Testing Strategy

### Unit Tests
- Injector target selection on hand-written fixture modules: one 409 raise site; zero sites (abort); two sites (abort); handler-mapped exception class.
- Canonical fingerprint stability: the same DB state gives the same hash, and a one-row change gives a different hash.
- Evaluator check functions on seeded rows (each check true and false).
- `check_matrix.py`: a missing mapping, a missing test and a skipped test each fail.

### Integration Tests
- `inject_defect.py` against the hand-written `supportdesk_r1` fixture (deterministic input): the probe observes 409 before and 500 after, and the commit is authored by the external identity.
- Restart boundary on a deterministic Phase 03 diagnostic cycle: fingerprints are equal and the invariants pass.
- The evaluator makes zero mutating calls (the HTTP recorder sees GET only).

### Workflow Tests
- Abort paths: the probe sees 500 before injection → the injector aborts with diagnostic `AC_ALREADY_VIOLATED`. Ambiguous targets → `INJECTION_TARGET_AMBIGUOUS`. Neither path pushes anything.

### Git / Worktree Tests
- After a run: Gitea `main` == `S_R3`; tags R1–R3 resolve to the manifest SHAs; the canonical checkout was never written by agents (reflog shows only Stratos fast-forwards plus the external fetch); no orphan worktrees remain.

### Connector Tests
- Covered by Phase 16. The chained run re-verifies: one PR per IC, one close per issue under fault injection, and CI evidence accepted only for known IC SHAs.

### E2E / Journey Tests (`journey`, live, `--live-required`)
- `test_mvp_chained_supportdesk.py`: the full §4.2 flow, then the §4.5 assertions, then the evaluator (exit 0).
- The same test with `MVP_CHAOS=1`: the §4.6 fault plan, then the same assertions, then the evaluator (exit 0).
- Playwright `mvp_walkthrough.spec.ts` against the paused chained run.

### Failure / Recovery Tests
- Restart boundaries RB-A..RB-D in every run.
- Chaos run per §4.6.
- After a successful run: `scripts/ops/backup.sh` → wipe → `restore.sh` → re-run the evaluator. The report checks are identical (Phase 18 RC-12 on the chained dataset).

### Security Tests
- The VIEWER token cannot approve (UI and API return 403).
- Secret scan of `var/olympus/reports/**`, artifacts and the Gitea repository history (gitleaks) finds nothing.
- The injected repository text from Phase 18 is not used here. Prompt-injection proof stays in Phase 18.

### Commands
```
make check
make mvp-env
LLM_LIVE_TESTS=1 uv run pytest -m journey --live-required tests/journey/test_mvp_chained_supportdesk.py -s --junitxml=var/olympus/reports/junit-chained.xml
(cd apps/dashboard && pnpm playwright test tests/e2e/mvp_walkthrough.spec.ts --reporter=junit > ../../var/olympus/reports/junit-ui.xml)
uv run python scripts/acceptance/evaluate_mvp.py --project SUPPORTDESK --run-id $RUN_ID --out var/olympus/reports
uv run python scripts/acceptance/check_matrix.py --matrix tests/acceptance/matrix.yaml --junit 'var/olympus/reports/*.xml'
make mvp-acceptance
```

## 13. Milestone

From a fresh clone on a Linux host, `make mvp-acceptance` succeeds twice in a row (the second run with failure injection). Each run takes one Project, SUPPORTDESK, through:
- DC-001 Greenfield: PRD → Release R1;
- DC-002 Brownfield: repository at R1 → trusted model → READY_FOR_CHANGE, in an isolated Scout context;
- DC-003 Feature Change: Gitea issue → spec delta → graph impact → Release R2;
- DC-004 Bug Fix: externally pushed defect → reproduction before repair → root cause → regression-proven Release R3, approved in the dashboard.

Every model-dependent stage uses a live provider. Canonical state is identical across four runtime-wiping restarts. The read-only MVP Acceptance Evaluator returns `mvp_complete = true`, with every ARCH §26 / TECH §32 term and every ARCH §22 / TECH §31 row backed by passing evidence.

## 14. Acceptance Criteria

- [ ] `make mvp-env` builds the full stack from a fresh clone, and preflight passes only with live credentials, a working sandbox and healthy integrations. It fails clearly otherwise.
- [ ] One Project runs DC-001 → DC-004 to the §7 terminal states without `seed_trusted_project`, `FakeProvider` or any hand-authored model output.
- [ ] Every restart boundary (RB-A..RB-D) produces identical canonical fingerprints before and after a LangGraph state wipe, and `assert_system_invariants` passes. The RB-A clarification resumes from its continuation package.
- [ ] DC-002's Scout context manifest contains no DC-001 product-model, artifact, model-call or runtime refs, and MATCHED specs create no duplicate canonical lineage.
- [ ] DC-003 is ingested from a signed Gitea webhook. A duplicate redelivery is DUPLICATE, and every DC-003 verification obligation has a STRUCTURAL source and a reason.
- [ ] The defect is introduced only as an external commit located through the canonical index. The probe shows 409 before injection and 500 after, and Phase 16 sync classifies the commit as EXTERNAL_FAST_FORWARD and re-indexes it.
- [ ] DC-004 PRE_REPAIR reproduction evidence at `affected_sha` predates the first repair commit, the regression test fails at `affected_sha` and passes at the IC SHA, and R3 is approved through the dashboard by a HUMAN.
- [ ] R1, R2 and R3 manifests, Gitea tags, Gitea `main` and the released index pointer all reference the exact verified integrated SHAs.
- [ ] Lineage is queryable forward from Feature to R1, R2 and R3, and in reverse from changed code to ProductSource (PRD, change issue, defect issue).
- [ ] `assert_live_llm_proof` passes for all four cycles. `model_calls` contains zero `provider='fake'` rows, and the total cost is within `LLM_TEST_BUDGET_USD`.
- [ ] The chaos run passes with every injected failure visible as an immutable failed or expired record plus a successful retry, and exactly one external effect per idempotency key.
- [ ] The MVP Acceptance Evaluator is read-only and exits 0, with every ARCH §26, TECH §32 and `STATUS.md` §11 condition true and evidence-referenced.
- [ ] `check_matrix.py` exits 0: all 24 ARCH §22 rows and all 13 TECH §31 rows map to passing, non-skipped tests.
- [ ] The Playwright walkthrough passes, including the VIEWER 403 check.
- [ ] After backup → wipe → restore, the evaluator report checks are identical.

## 15. Exit Criteria

- §14 is green on **two consecutive** clean-environment runs (normal, then `--chaos`). Run IDs, durations, costs, evaluator reports and matrix results are recorded in `STATUS.md`.
- Every phase 00–18 is `COMPLETE` in `STATUS.md`, and none was re-opened by a Phase 19 fix without being re-closed.
- `STATUS.md` §6 Journey Readiness shows all four journeys COMPLETE with chained-run evidence. §7, §8, §9, §10 and §11 are fully checked.
- The Architecture Drift Log has no unresolved entry that changes an invariant.
- Only then is `STATUS.md` Overall State set to `MVP_COMPLETE`.

## 16. Dependencies

### Depends On
- 17: dashboard, Playwright and the UI approval path.
- 18: chaos harness, fault points, `assert_system_invariants`, sandbox and backup/restore.
- Transitively 00–16. In particular 10, 12, 14 and 15 (journey flows) and 16 (Gitea, webhooks, repository sync for Q-05).

### Blocks
- None. This is the MVP exit gate.

### Can Run In Parallel With
- None. Every check here requires every other phase to be complete.

## 17. Risks / Implementation Notes

- **Model variance across a long chain:** a 4-cycle live run multiplies the failure probability. Mitigate with policy-bounded retries and remediation loops already in the system, a small PRD (Phase 05), and the per-stage report so a failed run can be diagnosed. Never mitigate with canned output or by relaxing gates.
- **Injector fragility (Q-05):** generated code may not have a single recognizable 409 raise site. The injector aborts loudly rather than guessing. If it repeatedly aborts on real R2 outputs, escalate Q-05 to the human owner (strategy B waiver, or extend the recognizer). Do not add an Olympus feature to inject defects.
- **Brownfield on a project with an existing canonical model (Q-02):** reconciliation outcomes depend on Scout's grouping. Review rules must be property-based, so a different but valid grouping still converges. An unexpected DIVERGENT result is a valid outcome that must be handled, not a test failure.
- **Duration and cost:** expect roughly 1.5–4 hours and a cost set by Q-06 per run. Run only in the gated live environment.
- **Host requirements:** the Linux sandbox (Phase 18) is required. macOS developers run the stack in the Linux worker image.
- **External-push semantics:** the canonical pointer moves to `S_D` with `source=EXTERNAL_PUSH` (Phase 16). Assurance for DC-004 still requires pointer == IC SHA at ASSURANCE entry (invariant 18). See the `STATUS.md` question Q-10.
- **Deferred:** none. Anything not proven here is not part of the MVP.

## 18. Deliverables

- Scripts: `scripts/demo/{bootstrap.sh,preflight.py,run_mvp.py,chained/*}`, `scripts/acceptance/{evaluate_mvp,check_matrix}.py`.
- Deploy: `deploy/compose.demo.yaml`; Make targets `mvp-env`, `mvp-demo`, `mvp-demo-chaos`, `mvp-acceptance`.
- Tests: `tests/journey/test_mvp_chained_supportdesk.py`, `tests/journey/chained/assertions.py`, `tests/acceptance/matrix.yaml`, `apps/dashboard/tests/e2e/mvp_walkthrough.spec.ts`, unit/integration tests for the injector, fingerprint, evaluator and matrix checker.
- Fixtures: `tests/fixtures/supportdesk/chained/*`.
- Reports: two `mvp_acceptance_<run_id>.json` plus Markdown summaries, and junit files, referenced from `STATUS.md`.
- Docs: `docs/demo/MVP_DEMO_RUNBOOK.md`.
- No migrations, no new APIs, no new agents.
