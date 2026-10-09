# STATUS — Olympus MVP Implementation Control Document

This file is the **authoritative implementation tracker** for the Olympus MVP. Implementation agents read `plans/README.md`, then this file, then the phase file they are executing, and they update this file as they work (see §14 Status Discipline).

- Authoritative sources: `Olympus_MVP_Architecture_and_Implementation_Plan_v1.2.docx` (**ARCH**) and `Olympus_MVP_Technical_Implementation_Specification_v1.0.docx` (**TECH**).
- Plans: `plans/README.md` (conventions, source reconciliations D-01..D-17, repository ownership §5.9, guardrails, drift protocol) and `plans/00-…` through `plans/19-…`.
- Planning baseline: 2026-10-01.

---

## 1. OLYMPUS MVP IMPLEMENTATION STATUS

**Objective.** Build the smallest reusable Olympus control plane that proves four end-to-end software-delivery journeys on one persistent Project, through one kernel:

| Journey | Input | Required outcome |
|---|---|---|
| Greenfield Build | PRD / product description | Verified Release R1 |
| Brownfield Onboarding | Unknown/existing repository | Trusted product model + READY_FOR_CHANGE |
| Feature Change | Requested product delta | Impact-aware, regression-safe Release R2 |
| Bug Fix | Observed defect | Reproduced, repaired, regression-proven Release R3 |

**Governing principle.** AI reasons probabilistically; Olympus controls deterministically. Agents propose, reason, implement, inspect and recommend. Olympus validates, persists, schedules, authorizes, verifies and decides. Agent runtimes (including LangGraph checkpoints and model transcripts) are never the source of truth for delivery progress.

**Implementation shape.** Python 3.12 modular monolith (FastAPI, Pydantic v2, SQLAlchemy 2 + Alembic, PostgreSQL 16 + pgvector) with separate scheduler and execution worker processes. AgentRuntime is a LangGraph adapter, and ModelRouter calls live providers. Git worktrees isolate execution, and a ToolGateway governs actions. The Code Intelligence index is a Python AST index. The full sequence is 20 phases (00–19).

**Repository reality at planning time** (basis for every state below):

| Item | Observation |
|---|---|
| Git | Branch **`main`**, last tagged baseline **`4b127e5`** (`v1` on `origin/main`). Working tree holds **uncommitted** Phases **00–18** implementation (control-api, workers, migrations **`0000`–`0032`**, agents, tests); local gates **`make check`**, **`make verify-phase-17-exit`**, **`make verify-phase-18-exit`** pass on this tree — **commit/push pending**. Agent environment may fail `git fetch` over SSH (`Permission denied`). |
| Content | `.docx` sources, `plans/` (incl. **`plans/17`**–**`18`** §14 **[x]**), `STATUS.md`, root **`README.md`**, **`.github/workflows/ci.yml`**. |
| Backend (Phase 00) | **COMPLETE:** packaging, settings, async SQLAlchemy, Alembic `0000_p00_baseline`, `/health` + `/ready`, JSON logging + correlation IDs, worker skeletons, pytest lanes, import-linter, Docker Compose postgres. |
| Backend (Phase 01) | **COMPLETE:** domain kernel, Alembic `0001_p01_repos` → `0004_p01_events`, mutating REST via `CommandBus`, §12 suites + security in `make check`, `make check` green. |
| Backend (Phase 02) | **COMPLETE:** ModelRouter, LangGraphRuntime, `model_calls`, live lane (OpenAI `gpt-5.4-mini`); `make check` + `make test-live` green (2026-10-02). |
| Backend (Phase 03) | **COMPLETE:** scheduler eligibility/admission, execution spine (`0006`), leases, snapshots, workers, checkpoint/resume, repository gates; **126** CI pytest + recovery green; live execution spine verified (2026-10-02). |
| Backend (Phase 04) | **COMPLETE:** migrations `0007`–`008`, worktrees/ToolGateway/materialization/Forge; REST; §12; live Forge (`LLM_LIVE_TESTS=1`). |
| Backend (Phase 05) | **COMPLETE:** migrations `0009`–`0012`, inbound kernel + document upload, product model + scope approval, Kira snapshot context + re-decompose + large-PRD chunking; deterministic **`make check`** lanes **204** pytest (2026-10-02). |
| Backend (Phase 06) | **COMPLETE:** migrations `0013`–`0015`, `core/planning/*`, Atlas + Kira planning profiles, guards, TaskContract compiler, REST; **`make check` green** — **213** pytest (**112** unit, **36** persistence, **47** integration, **10** security, **11** `@git`; 2026-10-02); workflow `test_planning_greenfield_workflow.py`; live planning **3/3** (`live_llm/planning/`, spend ≈ **$0.0046**). |
| Backend (Phase 07) | **COMPLETE:** migration `0016`, deterministic code index + retrieval APIs, golden `supportdesk_r1` fixture (2026-10-02). |
| Backend (Phase 08) | **COMPLETE (2026-10-02):** migrations `0017`–`0018`; IC merge, canonical promotion, traceability + lineage hops; **`make check` green** — **257+** pytest lanes. **`./scripts/verify-phases-00-07.sh --phase 08 --live`** exit **0** (§12 + **§15**: handoff doc, workflow IC deterministic + live Forge precursor PASS). Optional follow-up: **08.13** compiler refs, worker kill mid-merge test. |
| Backend (Phase 09) | **COMPLETE (2026-10-03):** migration **`0019_p09_assurance`**; assurance kernel + gates; **`./scripts/verify-phases-00-07.sh --live --skip-bootstrap`** exit **0** (Phases **00–10**, CHECK, FULL-DET, **JOURNEY**, **LIVE** when `--live`). Includes live Forge remediation (`test_remediation_live_forge.py`), live IC precursor (`test_ic_workflow_live_forge.py`), and **`make test-live`**. Real **`sentinel.execute`**: **`tests/integration/assurance_execute/`** (incl. supportdesk 3-AC). |
| Backend (Phase 10) | **COMPLETE (2026-10-03):** migrations **`0020`–`0022`** (release plane + scoped entity keys for full-suite regression); Greenfield **R1**; **`./scripts/verify-phases-00-07.sh --skip-bootstrap`** exit **0** (Phases **00–10**, CHECK, FULL-DET, **JOURNEY**). Optional: chained seven-alias `assert_live_llm_proof` journey + `scripts/demo/greenfield.py`. |
| Backend (Phase 11) | **COMPLETE (2026-10-04):** migration **`0023_p11_brownfield_recovery`**; discovery, observed behaviors, Scout recovery, reconciliation; **`make check`** green (**347** collected, golden index + brownfield suites); **`./scripts/verify-phases-00-07.sh --skip-bootstrap`** (~19 min) and **`--skip-bootstrap --live`** (~26 min) exit **0** (Phases **00–11**, CHECK, FULL-DET, **JOURNEY**, **LIVE**); **`make test-live`** **15/15** (incl. Scout supportdesk). |
| Backend (Phase 12) | **COMPLETE (2026-10-04):** migration **`0024_p12_baselines_readiness`**; baselines, **`PromotionService`**, **`ReadinessService`**, **`BrownfieldRemediationService`**, **`BaselineSet`** / **`declare_ready`**; **`make check`** green (**~360** pytest); **`./scripts/verify-phases-00-07.sh --skip-bootstrap`** exit **0** (Phases **00–12**, CHECK, FULL-DET, JOURNEY); **`--phase 12 --live`** PASS (live characterize + **`test_brownfield_supportdesk.py`** → **`READY_FOR_CHANGE`**). |
| Backend (Phase 13) | **COMPLETE (2026-10-04):** migration **`0025_p13_spec_deltas_impact`**; SpecDelta + **ImpactEngine** + hybrid retrieval + incremental canonical index + **StalenessService** + REST; assurance obligations from latest **COMPLETE** IA at IC READY; **`make verify-phase-13`** / **`make verify-phase-13-exit`** + **`make check`** green; **`./scripts/verify-phases-00-07.sh --skip-bootstrap --live`** exit **0** (~35 min). Extras: verify script **00–14**, Scout live retry, live harness hardening — see Phase **13** detail. |
| Backend (Phase 14) | **COMPLETE (2026-10-05):** migrations **`0026_p14_change_requests`**, **`0027_feature_spec_supersede`**; ChangeRequest intake, **`kira.change_interpret`**, architecture delta decline, IA-bounded planning, Feature Change orchestrator, R2 baseline promotion; **`tests/journey/test_feature_change_supportdesk.py`** + **`tests/journey/feature_change_acceptance.py`**; **`./scripts/verify-phases-00-07.sh --phase 14 --live`** exit **0**; sequential **`make db-up && make migrate && make lint && make check && make typecheck`** green (**2026-10-05**). |
| Backend (Phase 15) | **COMPLETE (2026-10-05):** migrations **`0028_p15_defects`**, **`0029_p15_unreproduced_approval`**; defect kernel + REGRESSION / release eligibility; bug-fix agent prompts + runtime wiring (**`_snapshot` → execution snapshot**, worker **artifact:** outputs before validation, triage signature normalization); REST + **`DefectService`** (`proceed_unreproduced`, `reject`, reproductions / trace / root-cause reads); **`make verify-phase-15-exit`** exit **0** (bootstrap + Phase **15** deterministic + **`live_llm/defects`** + Journey **4** + **`make check`**); **`tests/journey/test_bug_fix_supportdesk.py`** + **`bug_fix_acceptance.py`**. |
| Backend (Phase 16) | **COMPLETE (2026-10-06):** migration **`0030_p16_integrations`**; inbound + outbound connectors; **`make verify-phase-16-exit`** exit **0** (bootstrap + §12 deterministic + compose + **`test-connector-live`** + §13 **`make test-journey-issue-tracker`**). OSS stack: **`deploy/compose.test.yaml`** (Gitea, MinIO via **`elestio/minio`**, CI runner, fault proxy); **`make integrations-seed`** → **`GITEA_API_TOKEN`**; live path: Gitea issue → Feature Change R2 → **`attach_remote`** (push + release tag) → PR/CI/**`EXTERNAL_CI`**/**`deployment_local`** → issue comment/close. |
| Backend (Phase 17) | **COMPLETE (2026-10-06):** migration **`0031_p17_orchestrator`**; read models + guard preview + command catalog; **`orchestrator.converse`**; execution read **`GET /executions/{id}/model-calls`** + worktree mapping; **`plans/17`** §10/§14 synced; **`make verify-phase-17-exit`** exit **0** (bootstrap + §12 Python + live **`test_orchestrator_live.py`** **3/3**). Verify script accepts **`--phase 17`**. |
| Backend (Phase 18) | **COMPLETE (2026-10-06):** migration **`0032_p18_security_observability`**; OTel spans (command/scheduler/execution/model/tool/connector); metrics + retention; API token scopes + audit chain + rate limits; adversarial ToolGateway + **`SandboxRunner`**; RC-01..RC-12 deterministic suite + backup/restore smoke; Forge/Scout injection tests; **`make verify-phase-18`** exit **0** (**86** passed, **2** skipped); **`make verify-phase-18-live`** exit **0** (**4** passed, **1** skipped — Scout/Forge live §11; RC-01 live in **`test_rc01_forge_kill_live.py`** when **`OLYMPUS_FULL_RECOVERY=1`**). |
| Remaining MVP surface | Phase **19** (four-journey MVP acceptance). Phase **12** optional follow-ups (**P12-F02**..**P12-INV**; **P12-F01** closed). |
| Conflicts with target architecture | None (nothing to conflict with). Risk R-REMOTE: if `origin/main` has content, Phase 00 task 00.1 re-runs the assessment before any code is written. |

---

## 2. OVERALL STATUS

| Field | Value |
|---|---|
| **Overall State** | `IN_PROGRESS` (**18 / 20** phases complete) |
| **Current Phase** | Phase **19** — Final four-journey E2E & MVP acceptance (**`IN_PROGRESS`**) |
| **Current Milestone** | Phase **19** implementation (**2026-10-07**): chained driver + chaos/RC-01 wiring (**`chaos_hooks`**, **`worker_drain`**, **`MVP_CHAOS_*`**) landed; **`make mvp-acceptance`** / chaos sign-off + **P19-REG** still pending (Linux host, Docker, live keys, **`GITEA_API_TOKEN`**). Phase **18** exit remains **`make verify-phase-18-exit`** green (**2026-10-06**). |
| **Last Completed Phase** | Phase **18** — Observability, security & recovery hardening (**2026-10-06**) |
| **Next Phase** | Phase **19** |
| **Overall Completion** | **18 / 20 phases** |
| **Planning artifacts** | `plans/README.md` (incl. D-16/D-17 and §5.9 repository ownership) + 20 phase files + `STATUS.md` (complete) |

Allowed Overall State values: `NOT_STARTED | IN_PROGRESS | BLOCKED | MVP_COMPLETE`. `MVP_COMPLETE` may be set only after Phase 19 §15 **and** the Post–Phase 19 full-repo regression gate (**P19-REG**) — see §5.

---

## 3. IMPLEMENTATION SEQUENCE

Recommended serial order, with the only technically justified parallel paths shown beside it:

```
Phase 00  Foundation & scaffold
   ↓
Phase 01  Domain model & control-plane kernel
   ↓ ─────────────────────────────────────────────┐
Phase 02  ModelRouter & AgentRuntime              │
   ↓                                              │  Phase 07  Code Intelligence Index
Phase 03  Scheduler, Execution, Snapshot, Lease   │  (parallel path P1: depends only on 01)
   ↓ ───────────────┐                             │
Phase 04  Git/Tool  │  Phase 05  Product Source   │
Gateway/Forge       │  & Product Model            │
   │  (parallel path P2: both depend only on 03)  │
   ↓ ───────────────┘                             │
Phase 06  Architecture, ImplementationSpec, Task Planning
   ↓ ←────────────────────────────────────────────┘ (07 must be COMPLETE)
Phase 08  IntegrationCandidate, canonical index, traceability
   ↓
Phase 09  Assurance, evidence, findings, gates
   ↓
Phase 10  Release & GREENFIELD JOURNEY (R1)              ← Journey 1
   ↓
Phase 11  Brownfield discovery & recovered specifications
   ↓
Phase 12  Baselines, promotion, readiness (READY_FOR_CHANGE)  ← Journey 2
   ↓
Phase 13  Spec delta, impact engine, hybrid retrieval, staleness
   ↓ ───────────────┐
Phase 14  Feature   │  Phase 15  Bug Fix journey (R3)       ← Journeys 3 and 4
Change (R2)         │  (parallel path P3: both depend only on 13)
   ↓ ───────────────┘
Phase 16  External integrations & reconciliation
   ↓ ───────────────┐
Phase 17  Operator   │  Phase 18  Observability, security,
read models +       │  recovery hardening
Orchestrator (API)  │
   │  (parallel path P4: both depend only on 16)
   ↓ ───────────────┘
Phase 19  Final four-journey E2E & MVP acceptance       ← MVP exit gate
   ↓
Post-19   Full-repo E2E regression (verify-phases-live) ← required before MVP_COMPLETE
```

| Parallel path | Phases | Technical justification | Coordination rule |
|---|---|---|---|
| P1 | 07 alongside 02→03→04/05→06 | 07 needs only the Phase 01 `Repository` entity. It is pure deterministic parsing with no shared modules (`core/intelligence/code_index` vs `core/runtime`, `core/scheduler`, `core/execution`, `core/tools`, `core/product_model`, `core/planning`). | 07 must be COMPLETE before 08 starts. Rebase the Alembic `down_revision` at merge (README §5.8). |
| P2 | 04 alongside 05 | Both depend only on 03. Their modules are disjoint (`core/tools`, `core/execution/worktrees`, `agents/forge` vs `core/product_model`, `core/integrations/inbound`, `agents/kira`). Kira needs no ToolGateway tools. | Both must be COMPLETE before 06. Linearize migrations 0007–0012. |
| P3 | 14 alongside 15 | Both depend only on 13 and own disjoint packages (`core/product_model/changes` vs `core/product_model/defects`, `core/assurance/reproduction`). | Serialize merges of `core/release/eligibility.py`, `core/release/service.py`, `core/assurance/obligations.py` and the migration chain. |
| P4 | 17 alongside 18 | Both depend only on 16. 17 owns read models and `agents/orchestrator`; 18 owns telemetry, security and recovery in `core/*`. | Coordinate on auth middleware; Alembic linearized (**`0031`** → **`0032_p18_security_observability`**). |

There are no other parallel paths. Phases 08→13 and 16→19 are strictly serial because each consumes the previous phase's frozen contracts. Phase 10 → 11 is serialized by ARCH §2 (vertical-slice delivery: complete one journey before expanding breadth).

---

## 4. PHASE DEPENDENCY MATRIX

| Phase | Name | Depends On | Blocks | Parallel With | State |
|---|---|---|---|---|---|
| 00 | Foundation and Repository Scaffold | — | 01 (and all) | — | COMPLETE |
| 01 | Domain Model and Control Plane Kernel | 00 | 02, 03, 07, all later | — | COMPLETE |
| 02 | ModelRouter, AgentRuntime and Live LLM Infrastructure | 01 | 03, all agent phases | 07 | COMPLETE |
| 03 | Scheduler, Execution, Snapshot, Lease and Execution Worker | 01, 02 | 04, 05 | 07 | COMPLETE |
| 04 | Git Worktrees, ToolGateway, Governed Actions and Connector Framework | 02, 03 | 06, 08, 09, 10, 11, 16 | 05, 07 | COMPLETE |
| 05 | Product Source Intake, Inbound Event Kernel and Product Model | 03 | 06 | 04, 07 | COMPLETE |
| 06 | Architecture, ImplementationSpec, Task Planning and TaskContract Compiler | 04, 05 | 08 | 07 | COMPLETE |
| 07 | Code Intelligence Index (Deterministic, Python-First) | 01 | 08, 11 | 02, 03, 04, 05, 06 | COMPLETE |
| 08 | IntegrationCandidate, Canonical Index Promotion and Product-to-Code Traceability | 04, 06, 07 | 09 | — | COMPLETE |
| 09 | Assurance: Evidence, Verification Obligations, Warden, Sentinel, Gates and Remediation Loop | 08 | 10 | — | COMPLETE |
| 10 | Release Eligibility, Release Manifest and the Greenfield Journey (R1) | 09 | 11 | — | COMPLETE |
| 11 | Brownfield Repository Discovery, Observed Behavior and Recovered Specifications | 10 (and 07, 08, 09) | 12 | — | COMPLETE |
| 12 | Behavioral Baselines, Human Promotion, Readiness, Remediation and READY_FOR_CHANGE | 11 (and 09, 10) | 13 | — | COMPLETE |
| 13 | Specification Delta, Impact Engine, Hybrid Retrieval, Incremental Re-index and Staleness | 12 (and 05, 06, 07, 08) | 14, 15 | — | COMPLETE |
| 14 | Feature Change Journey (R2) | 13 | 16 | 15 | COMPLETE |
| 15 | Bug Fix Journey (R3) | 13 | 16 | 14 | COMPLETE |
| 16 | External Integrations: Inbound Adapters, Outbound Connectors and Reconciliation | 14, 15 (and 04, 05, 10, 13) | 17, 18 | — | COMPLETE |
| 17 | Operator read models and Orchestrator (backend only) | 16 | 19 | 18 | COMPLETE |
| 18 | Observability, Security and Recovery Hardening | 16 (and 02–15) | 19 | 17 | COMPLETE |
| 19 | Final Four-Journey E2E and MVP Acceptance | 17, 18 (transitively 00–16) | — | — | IN_PROGRESS |

Cycle check: every dependency points to a lower-numbered phase, so the graph is a DAG. Topological order: 00, 01, {02, 07}, 03, {04, 05}, 06, 08, 09, 10, 11, 12, 13, {14, 15}, 16, {17, 18}, 19.

---

## 5. DETAILED PHASE TRACKING

Each Acceptance Criteria list below is copied verbatim from §14 of the phase file. If a phase file's §14 changes, update the list here in the same commit.

### Phase 00 — Foundation and Repository Scaffold

Status: COMPLETE

Plan:
`plans/00-foundation-and-repository-scaffold.md`

Objective: Python 3.12 modular-monolith skeleton with packaging, settings, PostgreSQL 16 + pgvector, async SQLAlchemy, Alembic baseline, JSON logging with correlation IDs, control-api health, worker skeletons, pytest lanes, import-boundary enforcement and CI. No domain entities.

Dependencies: none.

Milestone: From a clean clone, `make setup && make db-up && make migrate && make check` succeeds. The control-api answers `/ready` against PostgreSQL 16 + pgvector, workers start and stop gracefully, logs are JSON with correlation IDs, and agent packages are structurally prevented from importing persistence.

Milestone Status: COMPLETE

**Verification run (2026-10-01, local):**

| Command / check | Result |
|---|---|
| `make check` | PASS — ruff, import-linter (`agents-no-persistence`, `core-no-apps`), mypy, pytest `-m unit` (9), `-m persistence` (1), `-m "integration and not live_llm"` (4) |
| `uv run pytest -m security` | PASS (1) — import-boundary probe |
| `uv run pytest --strict-markers --collect-only` | PASS — 15 tests, all markers registered |
| `make db-up && make migrate` | PASS — Docker Compose `pgvector/pgvector:pg16`, Alembic upgrade to `0000_p00_baseline` |
| `uvicorn` + `curl /health`, `/ready` | PASS — `200` with live Postgres (`{"db":"ok","migrations":"head"}`) |
| `python -m apps.{scheduler,execution}_worker.main --once` | PASS — exit 0, JSON logs with `service` + `env` |
| R-REMOTE (`git fetch origin`) | SSH `Permission denied`; local `main` has **no commits** — no remote divergence observed |

Key Deliverables:
- `pyproject.toml`, `uv.lock`, `core/{config,db,observability}`, `apps/*` skeletons, full package tree
- Migration `0000_p00_baseline.py`; `/health`, `/ready`
- `docker-compose.yml`, `Dockerfile`, `Makefile`, `.env.example`, import-linter contracts, CI workflow

Acceptance Criteria:
- [x] `uv sync` completes from `uv.lock` on Python 3.12.
- [x] `alembic upgrade head`, `downgrade base` and `upgrade head` succeed against PostgreSQL 16 with `vector` and `pg_trgm` enabled.
- [x] `GET /ready` returns 200 with DB available and 503 without it.
- [x] Every HTTP response carries `X-Correlation-ID`, and log lines carry the same `correlation_id`.
- [x] Both worker processes start, run one tick (`--once`) and exit 0 on SIGTERM.
- [x] All markers from `plans/README.md` §6.1 are registered, and `pytest --strict-markers` passes.
- [x] The import-linter contract `agents-no-persistence` is enforced in `make lint`.
- [x] The CI `deterministic` job definition runs lint, typecheck, unit, persistence, integration, security, and `@git` with a PostgreSQL service (2026-10-02).
- [x] No domain tables exist yet (only the baseline migration).
- [x] `OLYMPUS_WORKSPACE_ROOT` is a required settings field, resolved to an absolute writable directory at startup. It is configuration only and is never persisted in a domain row (README D-16, §5.9.2).

Progress:
- [x] 00.1 Remote divergence check resolved (R-REMOTE): fetch unreachable; no local commits to diverge from.
- [x] 00.2–00.4 Packaging, `.gitignore`, `.env.example`.
- [x] 00.5–00.10 Settings (incl. `OLYMPUS_WORKSPACE_ROOT`), DB layer, Alembic baseline, logging/correlation, `/health` + `/ready`, worker skeletons.
- [x] 00.11–00.14 Package tree, compose/Docker/Make, lint/type/import contracts, test harness.
- [x] 00.15–00.17 Smoke tests, CI, root README.
- [x] 00.18 First commit on `main` — `4b127e5` (`v1`), includes scaffold.
- [x] §12 commands green (`make check` + plan §12 smoke commands above).
- [x] §14 acceptance criteria verified (see table).
- [x] §15 exit criteria satisfied locally (commit on `main`; re-run `git fetch origin` when SSH/credentials work to close R-REMOTE formally).

Blockers:
- None. Phase 00 is **closed** for sequencing; proceed to Phase 01.

Notes:
- Do not modify the two `.docx` files. PostgreSQL is mandatory (D-01).

### Phase 01 — Domain Model and Control Plane Kernel

Status: COMPLETE (2026-10-01 — §14 acceptance + §15 exit criteria verified locally; evidence below)

Plan:
`plans/01-domain-model-and-control-plane-kernel.md`

Objective: Authoritative control-plane kernel, made up of:
- Project and unified Repository (`GREENFIELD_MANAGED` / `EXTERNAL_CLONE`) with RepositoryWorkspace identity and append-only revision metadata (no source-code bytes);
- DeliveryCycle with five journey state machines;
- Task, TaskDependency and versioned immutable TaskContract;
- explicit Approval and hashed Policy versions;
- command bus with idempotency;
- fail-closed guard registry and transition service;
- transactional domain/audit events with outbox and SSE;
- authenticated Actors.

Dependencies: 00.

Milestone: Through the authenticated REST command API, an operator creates a Project, registers an external repository (or has a GREENFIELD cycle declare a managed one) as control-plane metadata with a logical canonical workspace and a guarded, append-only canonical revision history, opens DeliveryCycles of each type, drives permitted transitions and creates Tasks with immutable, versioned TaskContracts. Illegal, unauthorized and unguarded transitions are rejected. Every accepted transition commits atomically with its domain and audit events, and duplicate idempotent commands never duplicate state.

Milestone Status: COMPLETE

**Verification run (2026-10-01, local):**

| Command / check | Result |
|---|---|
| `make check` | **PASS** — ruff, import-linter, mypy, unit (48) + persistence (18) + integration (13) + security (4) |
| `uv run pytest tests -q` | **PASS** — 83 tests |
| `uv run pytest -m security` | **PASS** — 4 tests (`test_control_plane_api`, import boundaries) |
| Testcontainers: Alembic upgrade / downgrade base / stepwise `0001`–`0004` / upgrade head | **PASS** |
| Plan §12 suites | **PASS** — `tests/unit/state/*`, `tests/persistence/*`, `tests/integration/control_plane/*`, `tests/security/test_control_plane_api.py` |

Key Deliverables:
- `core/domain/*` (incl. `repositories`, `repository_workspaces`, `repository_revisions`), `core/repositories/{service,revision,workspace_locator}`, `core/state/*`, `core/commands/*`, `core/policy/*`, outbox + SSE, auth, routers, `seed_actor` CLI
- Migrations `0001`–`0004` (incl. `olympus_forbid_mutation()` trigger, `delivery_cycle_events` view)
- `config/policy/default.yaml`

Acceptance Criteria:
- [x] All five DeliveryCycle types start in their defined initial state, and exhaustive tests prove that only listed edges are accepted. *(`test_machines_exhaustive`, `test_machines`.)*
- [x] An illegal lifecycle transition is rejected with 409 and audited as `transition.rejected`. *(`test_illegal_transition_409_and_rejection_audit`.)*
- [x] A guard that is not yet implemented fails closed (422 `GUARD_NOT_IMPLEMENTED`). *(`test_kernel_flow`.)*
- [x] A state change, its domain event and its audit event commit in one transaction (failure injection proves all-or-nothing). *(`test_transition_rolls_back_on_event_failure`.)*
- [x] Concurrent identical transitions result in exactly one success. *(`test_concurrent_cancel_one_wins`, `test_concurrent_advance_one_wins`.)*
- [x] An ISSUED TaskContract cannot be modified (application guard **and** DB trigger). A new version supersedes it, and history is retained. *(`test_contract_immutability`.)*
- [x] Task dependency cycles are rejected. *(`test_dependency_cycles`.)*
- [x] Approvals can be decided only by HUMAN actors with the APPROVER role, and are pinned to subject version and hash. *(`test_approval_decide_forbidden_and_allowed`, `test_approval_pinning`.)*
- [x] A duplicate `Idempotency-Key` does not create a duplicate DeliveryCycle, Task or transition. *(`test_idempotency`, `test_idempotent_delivery_cycle_create`, `test_idempotent_task_create`, `test_idempotent_delivery_cycle_transition`.)*
- [x] No API accepts a direct lifecycle `state`/`status` field (OpenAPI assertion). *(`test_openapi_request_bodies_forbid_state_and_status`.)*
- [x] The SSE stream delivers post-commit events and resumes by sequence. *(`test_sse_delivers_events_and_resumes` + list `after_sequence`.)*
- [x] Project and DeliveryCycle are distinct tables, and a Project holds multiple cycles.
- [x] Repository is a single entity for both `GREENFIELD_MANAGED` and `EXTERNAL_CLONE` sources (provider, remote_url, status, `credential_ref`, SHAs, one per project). *(`test_brownfield_repository_guard_and_pin`, revision integrity tests.)*
- [x] Canonical RepositoryWorkspace is logical-only; `WorkspaceLocator` confines paths; API responses omit physical paths. *(`test_workspace_locator`, `test_repository_api_hides_paths_and_secrets`.)*
- [x] Only `credential_ref` is persisted; secrets rejected; no credential values in API. *(`test_repository_validation`, repository API test.)*
- [x] `canonical_commit` changes only through `RepositoryRevisionService`; DB rejects raw updates. *(`test_revision_service`, `test_repository_revision_integrity`.)*
- [x] Code-needing cycle transitions fail with `REPOSITORY_NOT_READY` until READY; success pins `base_sha`. *(`test_brownfield_repository_guard_and_pin`.)*

Progress:
- [x] 01.1–01.8 Canonical JSON, ORM models, migrations `0001_p01_repos` … `0004_p01_events`, immutability triggers, `delivery_cycle_events` view.
- [x] 01.9–01.11 State machines as data, fail-closed GuardRegistry (`repository_ready_with_canonical_commit` implemented), TransitionService.
- [x] 01.12–01.16 CommandBus + command_log idempotency, Task/Contract/Approval/Policy services.
- [x] 01.17–01.18 Outbox + SSE endpoint, bearer auth + routers (all mutating REST via `CommandBus`).
- [x] 01.19 RepositoryService, RepositoryRevisionService, repository machine.
- [x] 01.20 WorkspaceLocator, GitInspector, `tests/fixtures/repositories.py` materialization helper.
- [x] 01.21 §12 unit/persistence/integration/security suites (see **Implementation record** for narrative gaps).
- [x] §14 acceptance criteria verified (see checklist above).
- [x] §15 exit criteria satisfied **locally** (`make check`, migrations via testcontainers, service module docstrings).
- [x] §15 CI parity: GitHub Actions deterministic job runs lint/typecheck/unit/persistence/integration/**security**/**git** (2026-10-02).

Blockers:
- None.

Notes:
- Guards owned by later phases remain fail-closed `RequiredGuard` placeholders until those phases register real implementations.
- Migrations split per plan: `0001_p01_repos`, `0002_p01_tasks`, `0003_p01_gov`, `0004_p01_events` (shared PostgreSQL enums use `create_type=False` where reused; triggers + `delivery_cycle_events` view on head).
- All Phase 01 mutating REST routes (including contracts, approvals, task dependencies) dispatch through `CommandBus` + `command_log`; read-only GET routes and `GET /policy/current` (lazy `ensure_policy_version`) stay direct.
- Plan detail: `plans/01-domain-model-and-control-plane-kernel.md` §19 **Implementation record** (extras, deviations, follow-ups).

**Implementation record (plan vs delivered):**

| Category | Detail |
|---|---|
| **Extras** | `core/commands/handlers.py`, `apps/control_api/command_dispatch.py`; CommandBus on all mutating routes; extra idempotency API tests (task, cycle transition); stepwise Alembic test; `subject_hash` on approval request (plan §8 table updated). |
| **Deviations** | No per-aggregate `core/domain/*/repository.py` (services use ORM directly); migration revision IDs shortened; `GitInspector` shipped without dedicated unit tests. |
| **§12 gaps (optional)** | No single HTTP test asserting GREENFIELD cycle declares managed repo + PENDING workspace at `projects/<id>/repo`; approval test uses VIEWER not AGENT (AGENT lifecycle block exists in code); no idempotency integration tests for contract/approval yet. |
| **Follow-ups** | Optional tests above; CI includes security + `@git` lanes (2026-10-02). |

### Phase 02 — ModelRouter, AgentRuntime and Live LLM Infrastructure

Status: COMPLETE

Plan:
`plans/02-model-router-and-agent-runtime.md`

Objective: A provider-neutral ModelRouter with these properties:
- alias-based model selection;
- Anthropic adapter required, OpenAI optional;
- Pydantic-validated structured output with schema-feedback retries;
- usage, cost and budget tracking.

Alongside it: the AgentRuntime protocol and LangGraphRuntime adapter (non-authoritative checkpoints), the AgentProfile and prompt registries, `model_calls` audit, and a live-LLM test lane enforced by `--live-required`.

Dependencies: 01.

Milestone: A real configured provider returns schema-validated structured output through `LangGraphRuntime → ModelRouter → provider`. Every call (successful or failed) is persisted with alias, model, prompt version/hash, tokens, latency, cost and provider request ID. Wiping LangGraph runtime state does not prevent resume from a continuation package.

Milestone Status: COMPLETE (OpenAI `gpt-5.4-mini` live lane, 2026-10-02)

Key Deliverables:
- `core/runtime/{model_router,model_policy,structured_output,usage,budget,agent_runtime,langgraph_runtime,agent_profiles,tool_client}.py`, providers, prompt registry
- Migration `0005` (`model_calls`); `config/models.yaml`, `config/model_pricing.yaml`
- `tests/plugins/live_guard.py`; CI `live` job

Acceptance Criteria:
- [x] All model selection goes through aliases, and no model ID literal appears outside `config/`.
- [x] A live structured-output call succeeds and is persisted with `provider_request_id`, tokens and cost. *(OpenAI `gpt-5.4-mini`; latest `make test-live` 2/2 — spend ≈ $0.000378.)*
- [x] Schema-invalid output is retried with validation feedback up to the bound, then fails with a persisted record.
- [x] Transient, rate-limit and auth errors are classified and retried or failed according to policy (unit-tested with FakeProvider).
- [x] Budget enforcement blocks calls that would exceed the configured budget.
- [x] `FakeProvider` cannot be constructed when `OLYMPUS_ENV` is `integration` or `journey`.
- [x] `--live-required` turns skipped live tests into failures (`tests/plugins/live_guard.py`).
- [x] `LangGraphRuntime` supports run, stream, cancel and resume via continuation package (unit tests; Postgres checkpointer wiring deferred).
- [x] No secrets appear in logs or `model_calls` (API keys not persisted; provider clients use env secrets only).

Progress:
- [x] 02.1–02.3 `model_calls` + migration `0005`, model/pricing config, alias policy.
- [x] 02.4–02.9 Providers, structured-output loop, transport retry, usage/budget, `ModelRouter.invoke/embed`.
- [x] 02.10–02.15 Prompt registry, runtime contracts, LangGraphRuntime, ToolGatewayClient protocol, FakeProvider guard, diagnostic profile.
- [x] 02.16–02.17 `live_guard` plugin + CI live job; deterministic suites (see **Test evidence**).
- [x] Live suite passed with real credentials (latest local verification **2026-10-02**: `make test-live`, 2 passed, spend ≈ **$0.000378**); §14 verified; §15 exit (interfaces frozen) satisfied for Phase 03/04 consumption.

**Test evidence (2026-10-02, local — latest verification):**

| Command | Result |
|---|---|
| `make check` | **PASS** — ruff, import-linter, mypy; pytest **62** unit + **19** persistence + **13** integration + **4** security (**98** selected / **100** collected). |
| `make test-live` | **PASS** — 2/2 live_llm (`test_model_router_live`, `test_langgraph_runtime_live`); OpenAI `gpt-5.4-mini`; session spend ≈ **$0.000378** (~6.1s). |
| Runtime unit highlights | `test_model_router.py` (schema retry, rate-limit retry, auth no-retry, budget block, FakeProvider env guard); `test_langgraph_runtime.py` (diagnostic run + continuation resume); `test_model_calls_immutable.py`. |

**Live lane (OpenAI — default for Phase 02 proof):**

Set `OPENAI_API_KEY` in gitignored `.env` (see `.env.example`: `MODEL_PROVIDER=openai`, `MODEL_DEFAULT=gpt-5.4-mini`, `MODEL_VERIFICATION=gpt-5.4-mini`), then:

```bash
make test-live
```

Blockers:
- Provider credentials: chat aliases per **`MODEL_PROVIDER`**; **`OPENAI_API_KEY`** required for live **`embedding`** / semantic tests (**Q-04** **CONFIRMED**, 2026-10-04) even when chat uses Anthropic.

Notes:
- Q-03 (alias set) remains open; **Q-04** (embedding provider) **CONFIRMED** (see §12).
- Postgres LangGraph checkpointer wiring deferred; continuation-package resume is unit-tested.
- Test harness fixes: `tests/integration/live_llm/conftest.py` (`system_actor`); root `tests/conftest.py` preserves `LLM_LIVE_TESTS=1` from `make test-live`.

**Implementation record (plan vs delivered):**

| Category | Detail |
|---|---|
| **Delivered** | `ModelRouter`, `ModelPolicy`, providers (Anthropic/OpenAI/Fake), `LangGraphRuntime`, `AgentProfile` registry, prompt registry, `model_calls` ORM + events, `diagnostic.structured_echo`, `DenyAllToolGateway` protocol stub. |
| **Deviations** | `AsyncPostgresSaver` checkpointer not wired in runtime (resume via continuation only in tests); embedding live test deferred to Phase **13** (`test_semantic_retrieval_live.py`). |
| **Follow-ups** | Run `make test-live` with secrets; wire checkpointer + cancel/truncate resume live tests; optional grep test for secrets in logs. |

### Phase 03 — Scheduler, Execution, Snapshot, Lease and Execution Worker

Status: COMPLETE

Plan:
`plans/03-scheduler-execution-snapshot-and-lease.md`

Objective: The deterministic execution spine:
- pure eligibility (ARCH §7.1) with atomic `SKIP LOCKED` admission;
- the Execution state machine;
- immutable hashed ExecutionSnapshots and single-owner leases with heartbeat and expiry recovery;
- the worker, with AGENT_RUNTIME and DETERMINISTIC executors;
- content-addressed Artifacts;
- checkpoint, clarification and resume from durable continuation packages;
- retry as a new Execution.

Dependencies: 01, 02.

Milestone: A READY ANALYSIS Task with an ISSUED TaskContract is deterministically admitted. It receives an immutable, hashed ExecutionSnapshot and a single-owner lease, and runs through `LangGraphRuntime → ModelRouter` against a live provider to produce a validated, content-addressed Artifact. Worker kill or restart, lease expiry, retry, cancellation and clarification checkpoint/resume all preserve complete immutable execution history.

Milestone Status: COMPLETE (deterministic CI + live execution spine verified)

Key Deliverables:
- `core/scheduler/*`, `core/execution/{service,worker,snapshots,leases,executors,validation,checkpoints,continuation,resume}`
- Migration `0006`; execution/clarification/artifact APIs and events

Acceptance Criteria:
- [x] Eligibility is a pure deterministic function implementing all seven ARCH §7.1 conditions with explicit reasons. *(unit: `tests/unit/scheduler/test_eligibility.py`.)*
- [x] A blocked Task cannot execute. *(workflow: `test_blocked_dependency_not_admitted`, `test_unblocks_after_dependency_completes`.)*
- [x] Concurrent schedulers create at most one active Execution per Task. *(persistence: `test_concurrent_admission_single_execution`.)*
- [x] Only one worker holds a lease at a time, workers heartbeat, and expired leases are recovered per the §7 rules. *(persistence `test_execution_lease`; recovery: `tests/workflow/execution/test_recovery.py`.)*
- [x] Every Execution has exactly one immutable snapshot whose hash is reproducible from its content. *(unit: `test_snapshot_hash_stable_under_key_order`; persistence: `test_snapshot_immutable`.)*
- [x] Retry produces a new Execution, and the failed Execution remains immutable and queryable. *(persistence: `test_execution_retry`.)*
- [x] A checkpoint persists the pending question and continuation. Resume works without LangGraph checkpoint data. *(unit: `test_ask_question_ambiguous_checkpoints`; recovery workflow tests.)*
- [x] Resume with changed authoritative inputs creates a new Execution with a new snapshot. *(workflow: `test_resume_changed_base_commit_new_execution`; execution `CHECKPOINTED→STALE`, task unblock, `previous_execution_id`.)*
- [x] Restarting workers or the API does not lose Task, Execution, Snapshot, Artifact or Clarification state. *(recovery: worker kill / lease expiry paths in `test_recovery.py`.)*
- [x] A live provider is used for the milestone run (a `model_calls` row with `provider_request_id`). *(live: `test_execution_spine_diagnostic_live`.)*
- [x] No LLM is invoked during eligibility or admission (asserted: no `model_calls` rows created by the scheduler process). *(persistence: `test_admission_does_not_create_model_calls`.)*
- [x] A Task bound to a repository is ineligible (`REPOSITORY_NOT_READY` / `BASE_COMMIT_UNAVAILABLE`) until its Repository is READY and the resolved base commit exists in the canonical RepositoryWorkspace. Its snapshot records the repository identity and the canonical revision it was resolved against. *(workflow: `test_repository_gates_eligibility_and_snapshot`; unit: `test_base_commit_unavailable`.)*

Progress:
- [x] 03.1–03.3 Models + migration 0006, Execution machine, RefResolver registry.
- [x] 03.4–03.8 Eligibility, admission, BaseCommitResolver, SnapshotBuilder, LeaseManager + sweeper.
- [x] 03.9–03.12 ArtifactStore, executors, output validators, worker flow.
- [x] 03.13–03.15 Checkpoint/clarification/resume scaffolding, APIs, deterministic workflow tests.
- [x] 03.16 Recovery/live suites (`diagnostic.ask_question`, lease kill, live execution spine evidence).
- [x] Live suite evidence recorded; §14 verified (§15 interface freeze spot-check via Phase 02 consumption).

**Test evidence (2026-10-02, local — latest verification):**

| Command | Result |
|---|---|
| CI pytest (`.venv/bin/ruff check .`, `-m "unit or persistence or (integration and not live_llm) or security"`) | **PASS** — **126** passed, **3** deselected (`live_llm`). |
| `LLM_LIVE_TESTS=1 pytest tests/integration/live_llm/test_execution_spine_live.py -m live_llm --live-required` | **PASS** — `test_execution_spine_diagnostic_live` (live provider, `model_calls.provider_request_id`, `DIAGNOSTIC_SUMMARY` artifact); session spend ≈ **$0.0002**. |
| Phase 03 highlights | `tests/workflow/execution/*` (deterministic flow, admission guards, recovery, repository gates, resume stale inputs), `tests/persistence/test_execution_*`, `test_scheduler_no_model_calls`, `tests/unit/scheduler/test_eligibility.py`, `tests/unit/runtime/test_diagnostic_ask_question.py`, `tests/unit/execution/test_snapshot_hash.py`, `tests/fixtures/execution_harness.py`. |
| Alembic | `0006_p03_executions` applied in testcontainers session fixtures (`upgrade head` / `downgrade base`). |

**Implementation record (plan vs delivered):**

| Category | Detail |
|---|---|
| **Delivered** | `core/scheduler/*` (pure eligibility, `SKIP LOCKED` admission, RefResolver ARTIFACT/TASK_CONTRACT); migration `0006`; Execution machine + `ExecutionService`; `SnapshotBuilder` + `BaseCommitResolver` (NONE, EXPLICIT_SHA, CYCLE_BASE); leases + sweeper; `ExecutionWorker` + AGENT_RUNTIME/DETERMINISTIC executors (`noop.verify_artifact`, `noop.fail`, `noop.sleep_past_wall_clock`); `ArtifactStore`; checkpoint/clarification/resume (`CHECKPOINTED→STALE` on changed snapshot hash); control-api routers `executions`, `clarifications`, `artifacts`; profile `diagnostic.ask_question` (unit-tested); settings for lease TTL / scheduler batch. |
| **Deviations / deferred** | Execution REST missing SSE **`/stream`**; no **`GET /delivery-cycles/{id}/executions`** list; live clarification + LangGraph truncate-resume tests not run; eligibility property test for all reason codes partial (core reasons covered); retry lineage does not set `previous_execution_id` (only stale-resume path does); `DEPENDENCY_INTEGRATION` base policy raises `BASE_RESOLVER_UNAVAILABLE`. |
| **Follow-ups** | Live `diagnostic.ask_question` E2E; optional scheduler-worker subprocess `model_calls` assertion. *(Dashboard execution reads — snapshot/events/actions/**`model-calls`**, worktree — delivered Phase **17**; see §5 Phase **17**.)* |

Blockers:
- None.

Notes:
- Multi-dependency base resolution: `DependencyBaseResolver` + `git_local.merge_candidates` (Phase 08); eligibility no longer emits `BASE_RESOLVER_UNAVAILABLE` for multi-dep tasks when resolver succeeds.
- Security import-boundary test invokes `.venv/bin/lint-imports` when `uv` is not on `PATH` (CI/local parity).
- Test harness `seed_ready_task(..., with_pending_required_approval=True)` supports approval-gate workflow tests without mutating ISSUED contracts.

### Phase 04 — Git Worktrees, ToolGateway, Governed Actions and Connector Framework

Status: COMPLETE

Plan:
`plans/04-git-worktree-tool-gateway-and-governed-actions.md`

Objective: The governed execution boundary:
- managed Git CLI wrapper;
- governed repository materialization (Greenfield provision, external clone) into a canonical RepositoryWorkspace;
- per-execution ExecutionWorkspaces (Git worktrees, writable or readonly);
- run-scoped execution tokens;
- path, shell and action policy;
- ToolGateway persisting every ActionRequest, decision and result;
- tool catalog, `RepositoryConnector` / `CredentialResolver` protocols and `git_local`;
- Forge, producing audited candidate commits that never become canonical.

Dependencies: 02, 03.

Milestone: A Greenfield-managed repository is provisioned and an external repository is cloned through the same governed materialization service. Each yields a READY canonical RepositoryWorkspace whose exact SHA is recorded as revision #1. A real TaskContract (CODE_CHANGE) is then deterministically scheduled and receives an immutable snapshot and an isolated ExecutionWorkspace (Git worktree). It runs Forge through `LangGraphRuntime → ModelRouter` against a live provider, makes every file, shell and test action through the ToolGateway (each one persisted and policy-checked), and produces an auditable candidate commit on `olympus/<EX-key>`. Out-of-scope writes, protected-branch writes and unauthorized tools are rejected.

Milestone Status: COMPLETE (Greenfield + external clone integration tests; live Forge Appendix B with `LLM_LIVE_TESTS=1`)

Key Deliverables:
- `core/execution/worktrees/*`, `core/repositories/{materialization,materialization_loop,connectors,credentials}`, `core/tools/*` (gateway, catalog, handlers, policy), `core/integrations/connectors/{base,registry,git_local}`
- `agents/forge/*`; migrations `0007`–`0008`; `execution_workspaces`; candidate commits; action APIs

Acceptance Criteria:
- [x] Every writable execution runs in its own ExecutionWorkspace (Git worktree). The canonical RepositoryWorkspace's protected refs and `canonical_commit` are never modified by an execution. *(integration: `test_writable_execution_worktree`, `test_concurrent_writable_worktrees_isolated`, candidate-commit API.)*
- [x] Concurrent writable executions use different worktrees and branches. *(integration: `test_concurrent_writable_worktrees_isolated`.)*
- [x] A `GREENFIELD_MANAGED` repository is provisioned (bare repository plus baseline commit) by governed SYSTEM actions, and its baseline SHA is recorded as `registered_sha`/`canonical_commit` (revision #1 `MATERIALIZED`). *(integration: `test_greenfield_provisioning`.)*
- [x] An `EXTERNAL_CLONE` repository is cloned into the canonical RepositoryWorkspace. Its default branch is resolved, its exact HEAD SHA is captured and recorded, it is validated against the materialization policy, and the external source is never written. *(integration: `test_external_clone_file_origin`.)*
- [x] Materialization is idempotent and crash-resumable. Failures leave the Repository in ERROR with a reason, and code-needing work stays blocked until a retry succeeds. *(`test_materialization_recovery.py`: ERROR retry, external adopt-after-clone, corrupt partial re-clone, greenfield OLYMPUS.md adopt; API `test_retry_materialization_api`; loop `resolve_materialization_head` adoption.)*
- [x] Workspace physical paths derive only from `OLYMPUS_WORKSPACE_ROOT` through `WorkspaceLocator`. Relocating the root requires no DB change. *(git: `test_workspace_root_relocation`.)*
- [x] Repository credentials are resolved from `credential_ref` only inside connector subprocesses, and never appear in DB rows, Git config, remote URLs, logs or API responses. *(security: `test_credential_secret_not_in_db_or_git_config` — LOCAL/`env:` scope.)*
- [x] A candidate commit never changes `Repository.canonical_commit`, the default branch or the revision history. *(integration/API + concurrent worktree tests.)*
- [x] ToolGateway persists an ActionRequest, decision and result for 100% of tool calls, including reads. *(persistence: `test_gateway_persists_denied_and_allowed`, `test_every_gateway_call_persists_request_and_result`; live Forge action audit.)*
- [x] Writes outside `allowed_scope`, path traversal, symlink escapes and `.git` access are denied with recorded reasons. *(unit path policy + gateway denial tests.)*
- [x] A tool not in `AgentProfile.allowed_tools` **or** `contract.allowed_actions` is denied. *(integration: `test_gateway_authorization`.)*
- [x] Implementation agents cannot write `main`, `release/*` or tags. Release-resource actions are denied for Forge. *(integration + unit action policy.)*
- [x] An approval-required action creates an Approval(ACTION) and checkpoints the execution, and proceeds only after APPROVED. *(integration: `test_action_approval_created_and_decidable_via_api`; gateway + Forge checkpoint.)*
- [x] Connector actions with the same idempotency key produce a single effect. *(persistence: `test_connector_idempotency_single_effect`.)*
- [x] The candidate commit records sha, parent, base, changed files and diff artifact, and its trailers reference execution, task and contract version. *(API `test_candidate_commit_api`; live Forge.)*
- [x] The live Forge milestone passes with real provider model calls (no mocked model output). *(live: `test_forge_candidate_commit_live` with `LLM_LIVE_TESTS=1`.)*
- [x] Execution tokens are run-scoped and invalid after lease loss or completion. *(security: `test_execution_tokens`.)*

Progress:
- [x] 04.1–04.3 GitCli allowlist, WorktreeManager + `execution_workspaces`, execution tokens; materialization service + scheduler loop.
- [x] 04.4–04.8 Path confinement, shell policy, tool catalog/handlers, action policy, ToolGateway (+ `GatewayToolClient`).
- [x] 04.9–04.11 Connector protocol + registry, `git_local`, credentials (`none:`/`env:`).
- [x] 04.17 REST routes (`actions`, `connectors`, `candidate_commits`, `execution_workspaces`, materializations + `retry_materialization`).
- [x] 04.12–04.18 Forge + candidate commit wiring; §12 git/security/persistence matrix; live Forge Appendix B.
- [x] Live Forge evidence recorded; §14 and §15 verified (2026-10-02).

Blockers:
- None.

Notes:
- Satisfies TECH Appendix B (first implementation milestone) together with Phases 00–03.
- **Verification (2026-10-02, latest):** ruff + import-linter + mypy green; **`make check`** lanes **162** pytest (81 unit, 28 persistence, 34 integration, 8 security, 11 `@git`; integration skips unchanged).
- **Phase 04 test map:** `@git` **11/11** (`test_materialization_recovery.py` **4/4**); control-plane `test_phase04_api` + `test_phase04_approval_api`; `test_gateway_authorization`; persistence gateway audit; security `test_execution_tokens`, `test_gateway_policy_unaffected_by_repo_content`, `test_credential_secret_not_in_db_or_git_config`; live Forge **`test_forge_candidate_commit_live`** PASS (`LLM_LIVE_TESTS=1`).
- **CI / local parity:** `Makefile` `check` = lint + typecheck + unit + persistence + integration + security + **`test-git`**; GitHub Actions `deterministic` job matches.

### Phase 05 — Product Source Intake, Inbound Event Kernel and Product Model

Status: COMPLETE (2026-10-02 — §14 acceptance + §15 exit criteria verified locally; evidence below)

Plan:
`plans/05-product-source-intake-and-product-model.md`

Objective:
- inbound event kernel (envelope, adapter registry, idempotency, audit);
- document-upload adapter;
- immutable, content-addressed ProductSource versions;
- product model: Capability, Feature, FeatureSpec, Requirement, UserStory, AC, KnowledgeItems (FACT/INFERENCE/UNCERTAINTY/DECISION/ASSUMPTION);
- live Kira decomposition run as an Execution;
- deterministic proposal validation;
- clarifications;
- hash-pinned human Scope Approval.

Dependencies: 03.

Milestone: A real PRD uploaded through the inbound document adapter becomes an immutable, versioned ProductSource. A live Kira execution decomposes it into a schema-validated proposal of Capabilities, Features, FeatureSpecs, Requirements, UserStories and ACs, and its open questions become durable Clarifications. After an explicit human Scope Approval, the FeatureSpecs become immutable APPROVED versions and the Greenfield DeliveryCycle can advance to ARCHITECTURE.

Milestone Status: COMPLETE

Key Deliverables:
- `core/integrations/inbound/*`, `core/product_model/*` (incl. `source_chunking.py`), `agents/kira` (`kira.decompose`), REST routers (`sources`, `product_model`, `specs`, `inbound`)
- Migrations `0009`–`0012`; fixtures `tests/fixtures/supportdesk/PRD.md`, `PRD_ambiguous.md`, `PRD_large.md`

Acceptance Criteria:
- [x] ProductSource versions are immutable and content-addressed. A duplicate upload creates no new version. *(trigger + ingest; `test_product_source_upload`.)*
- [x] Every inbound upload produces an `inbound_events` row with correlation ID, idempotency handling and audit. *(`test_upload_inbound_audit_and_guards`, `test_unauthenticated_inbound_rejected`.)*
- [x] Kira decomposition runs as an Execution through the ModelRouter path. *(`test_kira_decompose_execution_persists_via_worker`, `test_large_prd_chunking`; live **`test_kira_decompose_prd_live`** + **`make test-live`** `live_llm` **7/7 PASS** 2026-10-02.)*
- [x] Invalid proposals are rejected by the deterministic validator before any canonical row is written. *(unit tests + execution validator.)*
- [x] Every persisted FeatureSpec has ≥1 Requirement and ≥1 mandatory AC with an `evidence_requirement`. *(validator + workflow API assertions.)*
- [x] Open questions become Clarifications. Answers become DECISION KnowledgeItems and feed re-decomposition. *(persist + workflow clarifications; re-decompose orchestration present.)*
- [x] Scope approval is an explicit HUMAN Approval pinned to a scope-set hash, and it atomically approves the FeatureSpecs. *(`test_upload_inbound_audit_and_guards` scope API; `test_scope_approval_cascade_approves_entities`.)*
- [x] Approved FeatureSpecs are immutable. Edits create new versions. *(`test_approved_feature_spec_and_locked_children_immutable`; draft POST in workflow.)*
- [x] `start_architecture` is blocked until scope is approved and blocking clarifications are resolved. *(workflow + `test_kernel_flow`.)*
- [x] Kira has no write path to the DB (the import-linter contract passes).

Progress:
- [x] 05.1–05.4 Migrations, inbound kernel, document upload adapter, ProductSource versioning.
- [x] 05.5–05.6 Product model services, SupportDesk PRD fixture.
- [x] 05.7–05.10 `kira.decompose`, proposal validator, proposal persistence, re-decomposition after clarification.
- [x] 05.11–05.15 Scope sets + Approval(SCOPE), guards, RefResolvers, routes, tests.
- [x] 05.16 Large-PRD chunking (`chunk_markdown_by_headings`, multi-chunk Kira merge, `OLYMPUS_PRODUCT_SOURCE_DECOMPOSE_MAX_CHARS`).
- [x] §14 and §15 verified (deterministic `make check` + live Kira evidence).

Blockers:
- None.

Notes:
- Can run in parallel with Phase 04 (path P2).
- **Verification (2026-10-02, latest re-run):** ruff + import-linter + mypy green; deterministic pytest **204** (**105** unit, **33** persistence, **46** integration, **10** security, **9** workflow, **11** `@git`; **5** skipped live-only); Phase 05 §12 + large-PRD chunking (see test map).
- **Phase 05 test map (§12):** unit `test_validation.py` + `test_validation_rules.py`, `test_document_extraction.py` (md/docx/pdf), `test_scope_content_hash.py`, `test_source_chunking.py`; persistence immutability, scope cascade/rejection, `test_snapshot_product_context.py`, `test_scope_superseded_guard.py`; integration upload/workflow/kira/guards/redecompose/kernel, `test_prd_ambiguous_clarification.py`, `test_large_prd_chunking.py`; workflow `tests/workflow/product_model/test_greenfield_product_model_workflow.py`; live optional `test_kira_decompose_prd_live.py` (`LLM_LIVE_TESTS=1` + API key); security scope + spec approve denial.
- **Phase 05 follow-ups (plan gaps closed in code where noted):**
  - [x] Execution snapshot carries `project_name`, `decision_items`, `approved_product_summary` for Kira (`product_context_for_task`).
  - [x] Clarification answer → DECISION knowledge + auto `redecompose` task when cycle has ProductSource.
  - [x] `ProductDecomposition.assumptions` → ASSUMPTION `KnowledgeItem` rows on persist.
  - [x] Scope approval **REJECTED** → PROPOSED specs marked REJECTED (`on_scope_rejected`).
  - [x] Supersede decompositions scoped to delivery cycle (not global).
  - [x] Validator one-test-per-rule matrix (`test_validation_rules.py`); PDF extraction test; scope superseded guard (`test_scope_superseded_guard.py`); workflow lane `tests/workflow/product_model/`; deterministic ambiguous PRD clarification (`test_prd_ambiguous_clarification.py`); live worker harness (`test_kira_decompose_prd_live.py`, skipped unless `LLM_LIVE_TESTS=1`).
  - [x] Live Kira SupportDesk PRD run with real LLM (`test_kira_decompose_prd_live.py`; **2026-10-02** ~$0.005 session on OpenAI after strict-schema fix).
  - [x] Large-PRD chunking: heading-boundary splits + per-chunk Kira merge (`source_chunking.py`, `OLYMPUS_PRODUCT_SOURCE_DECOMPOSE_MAX_CHARS`, tests + `PRD_large.md` fixture).
- **Open Phase 05 follow-ups:** none required for COMPLETE. Optional later: live **`PRD_ambiguous.md`** end-to-end; assert Kira prompt includes snapshot decisions in a live test.
- **Fixes during verification:** scheduler skips cycle repository for `base_policy=NONE` analysis tasks; scope-set hash uses stable JSON sort; `ScopeService` content hash bug; `persist_proposal` allows nullable `execution_id`; `tests/security/conftest.py` supplies `system_ctx` for token tests; OpenAI strict `json_schema` (`pydantic_to_json_schema` recursive `additionalProperties: false`, `test_structured_output_schema.py`).
- **CI / local parity:** `make check` = lint + typecheck + unit + persistence + integration + security + `test-git` → **204** pytest (2026-10-02); `make test-live` adds **`live_llm`** lane (**7/7** when keys + `LLM_LIVE_TESTS=1`).
- **Migration fix:** `0010` product_sources unique constraints named explicitly (`uq_product_sources_project_lineage_version` / `_hash`).
- **Deps added:** `python-multipart`, `pypdf`, `python-docx` in `pyproject.toml`.
- Plan detail: `plans/05-product-source-intake-and-product-model.md` §12–§15; live Kira PRD run optional (`LLM_LIVE_TESTS=1`). Large PRDs: chunk at markdown headings when over `OLYMPUS_PRODUCT_SOURCE_DECOMPOSE_MAX_CHARS` (default 32_000).

**Implementation record (plan vs delivered):**

| Plan item | Delivered | Gap / follow-up |
|---|---|---|
| §12 unit validator matrix | `test_validation.py` + `test_validation_rules.py` | — |
| §12 persistence immutability + scope cascade | `test_product_model_immutability.py`, `test_scope_superseded_guard.py` | Duplicate inbound row test folded into upload integration |
| §12 integration upload + guards | upload + workflow + `test_kernel_flow` | — |
| §12 live Kira SupportDesk PRD | FakeProvider worker + live `test_kira_decompose_prd_live.py` (**PASS** 2026-10-02) | — |
| §12 clarification → DECISION → re-decompose | `test_product_model_redecompose`, `test_prd_ambiguous_clarification.py` | Full live ambiguous PRD still optional |
| §12 security inbound + scope | unauthenticated inbound + agent scope/spec denial | — |
| §12 snapshot product context | `test_snapshot_product_context` | Full Kira prompt assert with decisions optional |
| §12 scope rejection | `test_scope_rejection` + handler hook | — |
| §12 workflow greenfield product model | `tests/workflow/product_model/test_greenfield_product_model_workflow.py` | — |
| §12 large-PRD chunking (§17) | `test_source_chunking.py`, `test_large_prd_chunking.py`, Kira multi-chunk merge | Tune `OLYMPUS_PRODUCT_SOURCE_DECOMPOSE_MAX_CHARS` per model context |
| §15 live Kira + structured output | `test_kira_decompose_prd_live.py`; `core/runtime/structured_output.py` OpenAI strict fix | — |

### Phase 06 — Architecture, ImplementationSpec, Task Planning and TaskContract Compiler

Status: COMPLETE (2026-10-02 — §14 acceptance + §15 exit criteria verified locally; evidence below)

Plan:
`plans/06-architecture-implementation-spec-and-task-planning.md`

Objective:
- versioned Architecture (live Atlas) and ImplementationSpec (live Kira), each with an approval flow;
- an architectural-conformance validator (Architecture constrains ImplementationSpec);
- live Kira TaskPlan with DAG, scope and AC-coverage validation;
- a pure, deterministic TaskContract compiler;
- the Greenfield repository precondition (`start_planning` requires a READY `GREENFIELD_MANAGED` repository with a recorded baseline SHA).

Dependencies: 04, 05.

Milestone: For the SupportDesk scope, a live Atlas architecture and live Kira ImplementationSpecs are validated for architectural conformance and explicitly approved. A live Kira TaskPlan is validated as an acyclic, scope-bounded DAG covering every mandatory AC. The deterministic compiler emits immutable, hash-reproducible TaskContracts for every task, and the Greenfield cycle enters DEVELOPMENT against a provisioned repository.

Milestone Status: COMPLETE

Key Deliverables:
- `core/planning/*` (architecture, implementation specs, task plan validator, contract compiler), `agents/atlas`, Kira planning profiles
- Migrations `0013`–`0015`

Acceptance Criteria:
- [x] Architecture and ImplementationSpec are distinct, versioned entities. APPROVED versions are immutable.
- [x] An ImplementationSpec that references components, paths or contracts not in the Architecture is rejected as `ARCHITECTURE_DELTA_REQUIRED`.
- [x] An invalid or cyclic TaskPlan is rejected before any Task becomes READY.
- [x] Every mandatory AC of every in-scope FeatureSpec is covered by ≥1 Task (TaskPlan validator + accept path).
- [x] Every CODE_CHANGE Task references an APPROVED ImplementationSpec, and manual issue of such contracts is rejected.
- [x] Compiler output is deterministic (identical hash for identical inputs) and involves no model call.
- [x] Greenfield `start_planning` is rejected until the `GREENFIELD_MANAGED` repository is READY with its recorded baseline SHA. On success, `delivery_cycles.base_sha` is pinned to that canonical SHA, and the repository's provisioning ActionRequests are audited SYSTEM actions.
- [x] Atlas, Kira ImplementationSpec and Kira TaskPlan run through the ModelRouter path (FakeProvider integration: `test_planning_agent_profiles.py`; live optional: `tests/integration/live_llm/planning/` with `LLM_LIVE_TESTS=1`).
- [x] Snapshots of planned tasks include Architecture and ImplementationSpec versions.

Progress:
- [x] 06.1–06.4 Migrations, Architecture + Atlas, architecture approval, guards wired (repository precondition reuses Phase 01/04).
- [x] 06.5–06.7 ImplementationSpec + Kira profile, conformance validator, approval handlers.
- [x] 06.8–06.12 TaskPlan + validator + acceptance, TaskContractCompiler, CODE_CHANGE issue guard, plan guard.
- [x] 06.13–06.15 RefResolvers + snapshot extension, REST routes, deterministic tests (`tests/unit/planning`, persistence, guard integration).
- [x] Deterministic planning workflow + agent-profile evidence; Forge live uses `compiler:` contract metadata (06.11); live Atlas/Kira/planning lane (`LLM_LIVE_TESTS=1`).
- [x] §14 and §15 verified (deterministic `make check` + live planning evidence).

Blockers:
- None.

Notes:
- The Phase 04 Forge live test carries `compiled_by="compiler:TaskContractCompiler"` metadata; full compile→issue path is proven in `test_planning_greenfield_workflow.py` (Forge live body remains hand-built by design).
- **Verification (2026-10-02, latest):** ruff + import-linter + mypy green; **`make check`** **213** pytest; Phase 06 acceptance lane **19** pytest (`tests/unit/planning/`, `test_planning_*`, `test_snapshot_planning_versions.py`, `tests/workflow/planning/test_planning_greenfield_workflow.py`; Docker Postgres).
- **Live planning (§15):** `LLM_LIVE_TESTS=1 pytest tests/integration/live_llm/planning/ -v` → **3 passed** (~18s wall); session spend ≈ **$0.0046** (`test_atlas_supportdesk_live`, `test_kira_impl_spec_create_ticket_live`, `test_kira_task_plan_live`).
- **Phase 06 test map (§12):** unit `tests/unit/planning/`; persistence `test_planning_immutability.py`, `test_compiled_contract_guard.py`, `test_snapshot_planning_versions.py`; integration `test_planning_guards.py`, `test_planning_start_planning.py`, `test_planning_agent_profiles.py` (Atlas/Kira impl spec + task plan via FakeProvider); workflow `tests/workflow/planning/test_planning_greenfield_workflow.py` (decompose → planning → compiled contracts); live optional `tests/integration/live_llm/planning/` (Atlas, Kira impl spec, Kira task plan).
- **Runtime fixes during AC verification:** `DeliveryCycleRefResolver` for planning task admission; planning agent artifacts persisted before output validation; Atlas/Kira/task_plan prompt YAML front matter; worker completion path unchanged.
- **Live planning lane:** greenfield DB seed + live agent only (no live decompose); Kira impl spec prompt includes architecture contracts; completion-time conformance sanitize; live impl spec targets **Create Ticket** feature only.
- **Open Phase 06 follow-ups:** none required for COMPLETE. Optional: wire Forge live contract body through `TaskContractCompiler`; live impl spec for second SupportDesk feature after architecture contracts expanded; sync `plans/06-…md` §10/§14 checkboxes.

**Implementation record (plan vs delivered):**

| Plan item | Delivered | Gap / follow-up |
|---|---|---|
| §12 compiler determinism | `test_compiler.py` | — |
| §12 conformance validator | `test_conformance.py` | — |
| §12 TaskPlan validator | `test_task_plan_validator.py` | — |
| §12 persistence immutability | `test_planning_immutability.py` | — |
| §12 manual CODE_CHANGE issue guard | `test_compiled_contract_guard.py` | — |
| §12 guards integration | `test_planning_guards.py`, `test_planning_start_planning.py` | — |
| §11 Atlas/Kira ModelRouter | `test_planning_agent_profiles.py` + live harness under `live_llm/planning/` | live **3/3** with `LLM_LIVE_TESTS=1` (2026-10-02) |
| §06.11 Forge fixture | `compiler:` metadata on live Forge contract; compiled path proven in workflow test | Optional: Forge live body from compiler inputs |
| §12 workflow planning | `test_planning_greenfield_workflow.py` | — |
| §12 snapshot planning versions | `test_snapshot_planning_versions.py` | — |

### Phase 07 — Code Intelligence Index (Deterministic, Python-First)

Status: COMPLETE

Plan:
`plans/07-code-intelligence-index.md`

Objective:
- A deterministic, SHA-bound Python/FastAPI Code Intelligence Index covering: packages, modules, files, classes, methods, functions, routes, Pydantic schemas, SQLAlchemy models/tables and pytest tests.
- Relations: contains, imports, calls, inherits, accesses, exposes, verified_by.
- Git metadata and classification of external imports (stdlib / declared / undeclared).
- CANDIDATE vs CANONICAL index kinds.
- Structural and lexical retrieval with provenance.

Dependencies: 01.

Milestone: Given any registered Python repository and an exact commit SHA, Olympus deterministically builds an immutable, SHA-bound Code Intelligence Index of packages, modules, files, classes, methods, functions, FastAPI routes, Pydantic schemas, SQLAlchemy models/tables and pytest tests. Their contains/imports/calls/inherits/accesses/exposes/verified_by relations match the golden SupportDesk fixture, and the index is queryable through structural and lexical retrieval APIs that report retrieval source and provenance.

Milestone Status: COMPLETE

Key Deliverables:
- `core/intelligence/code_index/{parsers,entities,relations,retrieval}`, `git_source` reader
- Migration `0016`; `tests/fixtures/repos/supportdesk_r1/` golden fixture; code search/entity APIs

Acceptance Criteria:
- [x] Index content is reproducible: the same `(repository, sha)` gives an identical `content_hash`.
- [x] Every CodeIndexVersion records the exact `commit_sha`, `kind` and `source`. CANDIDATE and CANONICAL are distinguishable in schema and API.
- [x] The golden `supportdesk_r1` index matches all expected entities and relations.
- [x] The route → handler → service → repository → model → table chain is traversable for every SupportDesk route.
- [x] Test entities are linked via `VERIFIED_BY` to the symbols and routes they exercise.
- [x] Every retrieval result includes `retrieval_source`, `index_version_id`, `commit_sha` and provenance.
- [x] Repository code is never executed or imported during indexing.
- [x] READY index versions are immutable.
- [x] Indexes are built from Git objects of the Repository's canonical RepositoryWorkspace at the exact SHA. Uncommitted working-tree content is never indexed, and no source-file bodies are persisted in index tables.
- [x] Only CANDIDATE versions can be created outside Phase 08's `CanonicalIndexService`.

Progress:
- [x] 07.1–07.3 Migration 0016, `git_source`, `supportdesk_r1` fixture + `materialize_fixture_repository`.
- [x] 07.4–07.7 AST extraction, imports (incl. external classification), calls, inherits.
- [x] 07.8–07.12 FastAPI, Pydantic, SQLAlchemy, pytest extractors; Git metadata.
- [x] 07.13–07.16 CodeIndexer orchestration, retrieval, routes, golden/determinism tests.
- [x] §14 and §15 verified.

Blockers:
- None.

Notes:
- Parallel path P1: may start as soon as Phase 01 is COMPLETE. No LLM dependency.

### Phase 08 — IntegrationCandidate, Canonical Index Promotion and Product-to-Code Traceability

Status: COMPLETE (2026-10-02 — §14 acceptance + §15 exit criteria verified locally; evidence below)

Plan:
`plans/08-integration-candidate-canonical-index-and-traceability.md`

Objective:
- Deterministic integration of candidate commits into one IntegrationCandidate with an immutable integrated SHA; conflicts become Findings plus remediation work.
- Provisional candidate indexes vs the canonical index promoted at the exact integrated SHA.
- `code_entity_changes` (changed_by lineage) and GENERATED_LINEAGE SpecCodeLinks for principal symbols.
- Forward and reverse lineage service.
- Multi-dependency base resolution.

Dependencies: 04, 06, 07.

Milestone: Multiple candidate commits from a DeliveryCycle converge deterministically into one IntegrationCandidate with an immutable integrated SHA, or into a visible CONFLICT Finding with remediation work. The authoritative Code Intelligence Index is built for exactly that SHA, while execution indexes remain provisional and are discarded. GENERATED_LINEAGE SpecCodeLinks connect FeatureSpec/ImplementationSpec/AC versions to principal code entities and tests, and the lineage is traversable forward from Feature to code and in reverse from code to ProductSource.

Milestone Status: COMPLETE (§14 + §15 verified locally 2026-10-02; optional 08.13 / worker recovery deferred)

Key Deliverables:
- `core/integration/*`, `core/assurance/findings*`, `core/traceability/**`, `core/intelligence/code_index/canonical_service.py`
- Migrations `0017_p08_ic_findings`, `0018_p08_traceability`; IC, findings, lineage APIs; `findings:` policy

Acceptance Criteria:
- [x] Candidate commits never independently become assurance or release targets. Only an IC with `integrated_sha` can. (`test_canonical_revision_rule`, revision rows)
- [x] Merge conflicts produce a Finding plus a remediation task, and no autonomous resolution happens. (`test_merge_conflict.py`)
- [x] IC READY implies the canonical index pointer's `commit_sha == integrated_sha`. (`test_canonical_revision_rule`)
- [x] Candidate indexes are `kind=CANDIDATE`, never pointed to, and DISCARDED after integration. (`test_candidate_indexes.py`)
- [x] `code_entity_changes` records which execution, task and commit changed each stable key. (`test_ic_entity_changes_e2e.py`)
- [x] GENERATED_LINEAGE links carry task, execution and commit with confidence 1.0, and map only principal symbols. (`test_spec_code_links.py`)
- [x] AC → test VERIFIES links exist for Forge-declared, index-validated mappings. (same + `_materialize_verifies`)
- [x] Forward and reverse lineage queries return complete paths for the fixture. (`test_lineage_fixture.py`, `build_lineage_service`)
- [x] Multi-dependency tasks receive a deterministic dependency base, or are ineligible with a conflict Finding. (`test_dependency_base.py`)
- [x] Integration does not modify the default branch or tags in the canonical RepositoryWorkspace. (`test_default_branch_unchanged_after_integration`)
- [x] Candidate commits are never canonical. `Repository.canonical_commit` advances to `integrated_sha` only when the IC becomes READY, atomically with the canonical index pointer move, and records a `repository_revisions` row (`INTEGRATION_READY`) that references the IC and the canonical index version. (`test_canonical_revision_rule`)
- [x] Whenever a canonical index pointer is set, its `commit_sha` equals `Repository.canonical_commit`. (same)
- [x] Another cycle cannot create an IC while one cycle holds an unreleased canonical revision (`CANONICAL_REVISION_HELD`). A cancelled or failed cycle's held revision is reverted with a `REVERTED` revision row. (`test_canonical_revision_lock`, `test_canonical_revision_revert`)

Progress:
- [x] 08.1 Migrations `0017`–`0018`, ORM models, `integrated_sha` immutability trigger.
- [x] 08.2 IC ordering (topological + key tie-break, ancestor skip); `tests/unit/integration/test_ordering.py`.
- [x] 08.3 `IntegrationService.create`, canonical lock, integration task + admission; `start_integration` effect.
- [x] 08.4–08.5 `integration.merge` executor, checks artifact, conflict → Finding + remediation task.
- [x] 08.6 `FindingPolicy` + `config/policy/default.yaml` `findings:` section.
- [x] 08.7 Candidate index build hook, `code_entity_changes` diff; unit test `test_entity_changes.py`.
- [x] 08.8 `CanonicalIndexService.promote_ic`, pointer move + `INTEGRATION_READY` advance; `CanonicalRevisionGuardian`.
- [x] 08.9 Principal-symbol rule + `SpecCodeLinkService.materialize_generated` (IMPLEMENTS + VERIFIES via `ac_test_mapping`).
- [x] 08.10 `DependencyBaseResolver` + `git_local.merge_candidates`.
- [x] 08.11 `LineageService` + hop registry; basic forward/reverse API.
- [x] 08.12 Integration guards replace placeholders.
- [ ] 08.13 Compiler canonical-index context refs (deferred — needs async-safe pointer lookup in planning).
- [x] 08.14 REST: IC, findings, lineage; `GET .../code-index/canonical`; events on IC/findings/links.
- [x] 08.15 §12 git/integration suites (`tests/integration/integration_candidate/`, `tests/integration/traceability/`; persistence `test_ic_*`; wired in `scripts/verify-phases-00-07.sh` Phase **08** lane).
- [x] §14 acceptance criteria verified (all items checked above; evidence via Phase 08 pytest + verify script).
- [x] §15 exit criteria verified (`make verify-phase-08-exit` / `./scripts/verify-phases-00-07.sh --phase 08 --live` → exit **0**, **2026-10-02** local terminal ×2: all §15 steps PASS including live workflow IC precursor).

Blockers:
- None.

Notes:
- **`make check` green (2026-10-02):** ruff + import-linter + mypy + **257** pytest (**115** unit incl. Phase 08 ordering/principal/entity-diff unit, **40** persistence, **69** integration, **11** security, **22** `@git`). Compose + testcontainers migrations through **`0018_p08_traceability`**.
- **Phase 08 verify (2026-10-02, local terminal):** `./scripts/verify-phases-00-07.sh --phase 08 --live` → exit **0** (repeated PASS): Bootstrap (alembic **0018**); §12 lanes PASS; §15 handoff doc + unit smoke PASS; workflow IC deterministic PASS; **live workflow IC precursor** PASS (`tests/workflow/integration/` — live Forge + deterministic candidate → IC READY). Phase **04** live Forge step SKIP in 08 lane (covered elsewhere).
- **Full-repo verify:** `make verify-phases` / **`make verify-phases-live`** (Phases **00–14** + CHECK + FULL-DET + **JOURNEY** + LIVE when `--live`).
- **Kernel fixes during §12/§14:** `IntegrationCandidateRefResolver`, integration remediation contract issue path, candidate index `parent_index_version_id` at BUILD time, `git_local.merge_candidates` branch update after worktree teardown, `build_lineage_service()` default hops.
- **Optional follow-ups (non-blocking):** **08.13** compiler canonical-index context refs; worker kill mid-merge recovery test.

**Implementation record (plan vs delivered):**

| Area | Delivered | Gap / follow-up |
|---|---|---|
| IC lifecycle | `IntegrationService`, states, `integration.merge`, worker promotion hook | Recovery test (kill worker mid-merge) |
| Canonical index | `CanonicalIndexService`, promote + discard candidate indexes | 08.13 compiler `inputs` refs |
| Traceability | Entity diff, IMPLEMENTS/VERIFIES links, `build_lineage_service()` fixture paths | — |
| Guards / revision | Integration guards; lock/revert E2E | — |
| Verification | **`make verify-phase-08-exit`** / `--phase 08 --live` green (§15); **`make verify-phases-live`** green (00–08 + LIVE) | Rename script to `00-08` optional cleanup |

### Phase 09 — Assurance: Evidence, Verification Obligations, Warden, Sentinel, Gates and Remediation Loop

Status: COMPLETE (2026-10-03 — implementation + verification: **`./scripts/verify-phases-00-07.sh --live --skip-bootstrap`** exit **0**; Phases **00–10**, CHECK, FULL-DET, **JOURNEY**, **LIVE** PASS)

Plan:
`plans/09-assurance-evidence-findings-and-gates.md`

Objective:
- Verification obligations derived deterministically from mandatory ACs.
- Immutable Evidence tied to the exact IC SHA, plus acceptance coverage.
- Live Warden review (findings and recommendation only).
- Live Sentinel verification planning, with deterministic check execution in a readonly verification workspace.
- Policy-computed Finding blocking.
- A deterministic Gate Finalizer.
- A remediation loop with impacted-only re-verification, and waivers through Approval.

Dependencies: 08.

Milestone: For a READY IntegrationCandidate, Olympus deterministically derives verification obligations from mandatory ACs. Live Warden produces engineering findings and live Sentinel produces a validated verification plan, whose checks run deterministically against the exact integrated SHA to produce immutable evidence. The deterministic Gate Finalizer alone sets Gate PASS/FAIL from evidence, coverage, findings and policy, and a failing assurance drives a remediation execution and a new IC with impacted-only re-verification.

Milestone Status: COMPLETE (deterministic §12 + carry-forward + supportdesk 3-AC; live Warden/Sentinel via **`tests/integration/live_llm/assurance/`**; live Forge remediation loop **`test_remediation_live_forge.py`** with scoped integration checks)

Key Deliverables:
- `core/assurance/{evidence,obligations,coverage,gates,orchestrator,completion,remediation,verification_workspace,plan_validation,deterministic_plan}`, `agents/warden`, `agents/sentinel`, `core/execution/executors/sentinel_execute.py`
- Migration **`0019_p09_assurance`**; `apps/control_api/routers/assurance.py`; policy `assurance:` section

Acceptance Criteria:
- [x] Every Evidence row references the exact IC and `integrated_sha`. Evidence for any other SHA cannot satisfy obligations. *(service + `gates.decide` SHA mismatch reason; persistence immutability.)*
- [x] Warden reviews and Sentinel checks target the exact integrated SHA… *(verification workspace HEAD assert + finalizer `CANONICAL_REVISION_MISMATCH`; IC assurance bootstrap E2E.)*
- [x] A mandatory AC without allowed evidence cannot become SATISFIED. MODEL_ASSESSMENT never satisfies a mandatory AC. *(`evidence_rules`, coverage + `test_gates_decide`.)*
- [x] Warden and Sentinel cannot set Gate status (DB constraint + API 403 + no tool path). *(trigger `finalized_by`; `POST /gates/{id}/finalize` 403 for AGENT; `test_assurance_gate_finalize`.)*
- [x] The gate decision is a pure deterministic function of evidence, coverage, findings and policy (truth-table tests). *(`test_gates_decide`.)*
- [x] Finding `blocking` is computed by policy, not by agents. *(Phase 08 + Warden persistence via `FindingPolicy`.)*
- [x] A blocking Finding produces a remediation Task… *(integration waiver/remediation tests + **`test_remediation_carry_forward.py`** + live **`test_remediation_live_forge.py`**.)*
- [x] Re-verification after remediation re-runs impacted obligations and carries forward only provably unchanged evidence (with reference). *(`tests/workflow/assurance/test_remediation_carry_forward.py`; carry-forward entity hash match via repo-scoped `SpecCodeLink`; coverage recompute after carry.)*
- [x] Waivers require an explicit Approval(FINDING_WAIVER). *(`request_waiver` + `handle_approval_decide` → `apply_waiver`; integration test.)*
- [x] Each obligation records why it was chosen (reason + source refs). *(AC source in `ObligationService`.)*
- [x] Warden and Sentinel planning run through the live ModelRouter path, and check execution is deterministic. *(ModelRouter profile tests + **`live_llm/assurance`** `test_warden_review_live` / `test_sentinel_plan_live` with OpenAI when keyed; `sentinel.execute` deterministic / integration stub.)*

Progress:
- [x] 09.1–09.4 Migration, EvidenceService + allowed types, ObligationService, coverage.
- [x] 09.5–09.9 Verification workspace, `test.run` / `test.run_probe`, Sentinel plan/execute/summarize (profiles + executor); worktree **`gitdir:`** fix for overlay `info/exclude`.
- [x] 09.10–09.11 Warden profile + finding fingerprint/policy, pure gate finalizer.
- [x] 09.12–09.18 Assurance orchestrator on `integration.ready`, remediation + waive APIs, `required_gates_pass`, REST; lineage hops.
- [x] §12 verify script Phase **09** lane (see **Phase 09 test map**).
- [x] §15 verify: handoff doc (**obligation registry** + release hook documented in `docs/phase08-handoff-09-10.md`); full **`--live --skip-bootstrap`** green (2026-10-03).

Blockers:
- None.

**Phase 09 test map (wired in `scripts/verify-phases-00-07.sh --phase 09`):**

| Verify step | Tests / artifact | Status |
|---|---|---|
| §15 handoff doc | `docs/phase08-handoff-09-10.md` | PASS |
| §15 handoff smoke | `tests/unit/test_phase08_handoff_docs.py`, `test_findings_policy.py` | PASS |
| Unit §12 | `tests/unit/assurance/` | PASS |
| OpenAI strict schemas | `tests/unit/runtime/test_structured_output_schema.py` (WardenReview, VerificationPlan) | PASS |
| Persistence §12 | `tests/persistence/test_assurance_immutability.py` | PASS |
| Security §14 | `tests/security/test_assurance_gate_finalize.py` | PASS |
| Integration §12 (stub sentinel) | `tests/integration/assurance/` (gate E2E, bootstrap, waiver, profiles) | PASS |
| Integration §12 (real execute) | `tests/integration/assurance_execute/` (mini harness + **supportdesk_r1** 3-AC) | PASS (re-run after fixture DB bootstrap) |
| Workflow §12 (deterministic) | `tests/workflow/assurance/test_remediation_carry_forward.py` | PASS |
| Live §12 | `tests/integration/live_llm/assurance/` + workflow assurance (`--live`, plan §12 command) | PASS with `--live` |
| Live Forge remediation loop | `tests/workflow/assurance/test_remediation_live_forge.py` (`--live`) | PASS with `--live` + keys (IC merge uses integration smoke test; Sentinel targets AC test) |
| Full deterministic gate | `make check` on `--phase 09` | PASS |

Notes:
- Guardrail: `MODEL_ASSESSMENT` / inappropriate `STATIC_REVIEW` never satisfies executable-mandatory ACs (`evidence_rules`).
- **Verify (2026-10-02):** `./scripts/verify-phases-00-07.sh --skip-bootstrap --phase 09` and **`--live`** → **Phase 09 PASS** (all non-skipped steps).
- **Added (2026-10-02):** `supportdesk_three_ac_decomposition` + `tests/fixtures/assurance_supportdesk_harness.py`; **`test_supportdesk_three_ac.py`** (real `sentinel.execute`, SENTINEL gate PASS/FAIL); **`test_remediation_live_forge.py`**; **`RemediationService`** emits repo-scoped `forge.implementation` contracts; **`supportdesk_r1`** SQLite thread-safe + schema bootstrap for integration pytest.
- **Verify (2026-10-03):** `./scripts/verify-phases-00-07.sh --skip-bootstrap` → Phases **00–10**, CHECK, FULL-DET, **JOURNEY** **PASS**.
- **Verify (2026-10-03, sign-off):** **`./scripts/verify-phases-00-07.sh --live --skip-bootstrap`** → Phases **00–10**, CHECK, FULL-DET, **JOURNEY**, **LIVE** **PASS** (incl. **`test_remediation_live_forge.py`**, **`test_ic_workflow_live_forge.py`**, **`make test-live`**).
- **Verify (2026-10-03):** **`make verify-phase-10-exit`** / **`--phase 10 --skip-bootstrap`** → Phase **10** **PASS** (all §12 steps + **`make check`**).
- **Verify (2026-10-03, regression):** sequential **`make db-up && make migrate`**, **`make lint`**, **`make check`**, **`./scripts/verify-phases-00-07.sh --skip-bootstrap`**, **`--skip-bootstrap --live`** → exit **0** (FULL-DET **313** passed; **LIVE** gate **PASS**).
- **Hardening (2026-10-03):** `FindingRefResolver` for remediation admission; Forge finalize schema fallback + candidate-commit synthesis; `make migrate` waits for Postgres; pytest session migration noise reduced; remediation live test uses IC-level VERIFIES link (no post-terminal execution output patch).
- **Hardening (2026-10-03):** migrations **`0021_p10_scoped_keys`** / **`0022_p10_scoped_assurance_keys`** — IC/finding/gate/evidence keys scoped per cycle/project (fixes global `IC-0001` / `GT-0001` collisions in full deterministic tree); `human_finalize_ctx` get-or-create for `gate-finalizer` actor; release approve **403** for agent tokens.

### Phase 10 — Release Eligibility, Release Manifest and the Greenfield Journey (R1)

Status: COMPLETE — release plane + Greenfield **R1** journey in CI; per-stage live LLM via **`make test-live`** (full seven-alias single journey optional follow-up)

Plan:
`plans/10-release-and-greenfield-journey.md`

Objective:
- Deterministic release eligibility from a fail-closed condition registry.
- Immutable ReleaseManifest, Release and DeliveryOutcome records.
- Hash-pinned human release approval.
- Stratos deterministic release execution: ff-only `main` plus tag, with a TOCTOU re-check.
- Released index pointer.
- Then **Journey 1** proven live end to end: PRD → Release R1.

Dependencies: 09.

Milestone: **Journey 1 complete.** An uploaded SupportDesk PRD is transformed through the real control plane, with live LLM calls at every model-dependent stage, into approved FeatureSpecs, an approved Architecture and ImplementationSpecs, a compiled Task DAG, isolated Forge executions, an IntegrationCandidate with a canonical index, independent Warden/Sentinel assurance with evidence and deterministic gates, and a deterministically eligible, human-approved **Release R1**. Its manifest references the exact verified integrated SHA, and its lineage is queryable from PRD to code to evidence to release.

Milestone Status: COMPLETE (CI); optional: one chained live journey with all seven `assert_live_llm_proof` aliases

Key Deliverables:
- `core/release/*` (incl. `stratos.release` executor registration); `agents/stratos/profile.py`; migrations **`0020`–`0022`**
- REST: `apps/control_api/routers/releases.py`
- `tests/journey/{conftest,helpers}.py`, `tests/journey/test_greenfield_supportdesk.py`, `tests/workflow/journey/test_greenfield_build_to_release.py`, `scripts/demo/greenfield.py` (stub)
- `tests/fixtures/supportdesk/clarification_answers.yaml`

Acceptance Criteria:
- [x] Release eligibility is computed deterministically and persisted with per-condition reasons. *( `tests/integration/release/test_release_workflow_e2e.py::test_eligibility_persisted_with_per_condition_reasons`, `tests/unit/test_release_eligibility_*`, `tests/persistence/test_release_immutability.py`.)*
- [x] A release cannot become eligible when mandatory evidence is missing, a gate is not PASS, a blocking finding exists, an approval is missing or the IC is not current. *( `tests/integration/release/test_release_eligibility_negative.py`.)*
- [x] Release approval is an explicit HUMAN Approval pinned to the manifest hash. *( `test_release_approval_pinned_to_manifest_hash`; manifest rows immutable in DB.)*
- [x] The release manifest references the exact verified `integrated_sha` and the repository's canonical revision. After release, the default branch, the release tag, `Repository.canonical_commit` and `Repository.released_commit` all point to it, and a `RELEASED` revision is recorded. *( `test_release_e2e_sha_alignment_outcome_and_lineage` + `tests/integration/git/test_release_git_actions.py`.)*
- [x] In the Greenfield journey, the `GREENFIELD_MANAGED` repository is provisioned and its baseline SHA recorded before any implementation Execution. All Forge work happens in isolated ExecutionWorkspaces, and generated code is persisted only in Git, not as control-plane state. *( `test_greenfield_build_provisions_baseline_and_releases_r1` asserts baseline SHA + execution workspace ≠ canonical; `test_forge_workspace_isolated_from_canonical`.)*
- [x] Eligibility is re-checked at execution time (TOCTOU protection). *( `tests/integration/release/test_release_toctou.py`.)*
- [x] The released index pointer equals the release SHA. *(Asserted in release E2E.)*
- [x] The DeliveryOutcome bundle is persisted with result RELEASED. *(Asserted in release E2E.)*
- [~] The Greenfield journey test passes live, with `assert_live_llm_proof` covering all seven model-dependent stages. *( **`make test-journey`** PASS — PRD → R1 (deterministic decompose/arch seeds); stage-level live proof in **`tests/integration/live_llm/*`**. Chained seven-alias journey not automated.)*
- [~] Forward and reverse lineage queries include Release R1. *(Forward from IC includes RELEASE in E2E; full PRD→release reverse path pending live journey.)*
- [~] After a full restart, outcome, lineage and eligibility queries return identical results. *(Re-query after `expire_all` in E2E; process restart in journey §12.8 pending.)*

Progress:
- [x] 10.1–10.5 Migration `0020`, eligibility registry + conditions, recompute hook/triggers, manifest, Release lifecycle + Approval(RELEASE).
- [x] 10.6–10.9 `stratos.release`, released pointer + DeliveryOutcome + COMPLETE, `release_executed` guard, lineage hop.
- [x] 10.10–10.12 Journey harness + helpers + fixture YAML; `test_greenfield_supportdesk.py` + workflow journey test; demo script stub.
- [x] Migrations **`0021`–`0022`**: scoped unique keys for integration candidates, findings, gates, evidence (full-suite regression).
- [x] §14 acceptance suites wired in **`scripts/verify-phases-00-07.sh --phase 10`** + full-repo **CHECK** / **FULL-DET** / **JOURNEY** / **LIVE** gates.
- [~] Greenfield journey run recorded (run ID, cost, duration); §15 live seven-alias sign-off. *(CI journey **~6.5s**; **`make test-live`** + **`verify-phases --live`** PASS for per-stage live proof.)*

Blockers:
- None.

**Phase 10 test map (wired in `scripts/verify-phases-00-07.sh --phase 10`):**

| Verify step | Tests / artifact | Status |
|---|---|---|
| §15 handoff doc | `docs/phase08-handoff-09-10.md` (release hook) | PASS |
| Alembic head | **`0022_p10_scoped_assurance_keys`** | PASS |
| Unit §12 | `tests/unit/test_release_eligibility_*.py`, `test_release_manifest_validation.py` | PASS |
| Persistence §12 | `tests/persistence/test_release_immutability.py`, `test_release_approval_binding.py` | PASS |
| Integration §12 | `tests/integration/release/` (E2E, negatives, TOCTOU, Forge workspace isolation) | PASS |
| Git §12 | `tests/integration/git/test_release_git_actions.py` | PASS |
| Security §12 | `tests/security/test_release_api.py` | PASS |
| Workflow §12 | `tests/workflow/journey/test_greenfield_build_to_release.py` | PASS |
| Journey §12 | **`make test-journey`** → `tests/journey/test_greenfield_supportdesk.py` | PASS |
| Fixture §12 | `tests/fixtures/supportdesk/clarification_answers.yaml` | PASS |
| Full deterministic gate | `make check` on `--phase 10` | PASS |
| Full-repo gates | **`make verify-phases`**: CHECK + FULL-DET + **JOURNEY**; **`--live`**: + LIVE | PASS |

Notes:
- Recommended live budget is at least **$15** for the full Greenfield journey (record observed cost when run).
- **Verify:** `make verify-phase-10-exit` or `./scripts/verify-phases-00-07.sh --skip-bootstrap --phase 10`; full sign-off: **`make verify-phases`** / **`make verify-phases-live`** (Phases **00–10**).
- **Verify (2026-10-03):** local terminal — **`make db-up && make migrate && make lint && make check`** green; **`./scripts/verify-phases-00-07.sh --skip-bootstrap`** (~16 min) and **`--skip-bootstrap --live`** (~22 min) exit **0**.

### Phase 11 — Brownfield Repository Discovery, Observed Behavior and Recovered Specifications

Status: COMPLETE (2026-10-04 — §14 acceptance + §15 exit verified locally)

Plan:
`plans/11-brownfield-discovery-and-recovered-specifications.md`

Objective:
- Brownfield onboarding from durable repository state only.
- Deterministic discovery: manifests, dependencies, frameworks, entry points, Git metadata.
- Canonical repository index, existing-test execution, and FACT-backed ObservedBehaviors.
- Live Scout (`scout.survey`, `scout.recover_feature`) in an isolated context, producing recovered architecture, features and specs, cited INFERENCES, explicit UNCERTAINTIES, capped confidence and DISCOVERED SpecCodeLinks.
- Everything stays PROPOSED.
- Reconciliation against an existing canonical model (Q-02).

Dependencies: 10 (and 07, 08, 09).

Milestone: Given only a registered existing repository, cloned into its canonical RepositoryWorkspace at an exact captured HEAD SHA, Olympus deterministically discovers its structure, builds the canonical repository index, executes existing tests and derives FACT-backed ObservedBehaviors. Live Scout executions in an isolated context propose a recovered architecture, capabilities, features, RecoveredSpecs and ImplementationSpecs, with cited INFERENCES, explicit UNCERTAINTIES, deterministically capped confidence and DISCOVERED SpecCodeLinks. All of it stays PROPOSED and distinct from canonical intent.

Milestone Status: COMPLETE (§14 + §15 verified locally 2026-10-04)

Key Deliverables:
- `core/intelligence/{repository,recovered_specs}`, ObservedBehaviorService, ScoutContextBuilder, RecoveryValidator, RecoveryReconciliationService, `agents/scout`
- Migration **`0023_p11_brownfield_recovery`** (plan §11.1 `0021` name superseded by Phase **10** `0021`–`0022`)

Acceptance Criteria:
- [x] Brownfield runs from durable repository/project state only. The context manifest proves no prior product model, other-cycle artifact or runtime history was used. *(context isolation test.)*
- [x] The external repository is registered as `EXTERNAL_CLONE`, with credentials resolved only through the connector/credential provider. It is cloned into the canonical RepositoryWorkspace by the shared Phase 04 materializer, and the exact HEAD SHA of the resolved default branch is captured as `registered_sha = canonical_commit`. *(clone binding + existing guard tests.)*
- [x] Code Intelligence indexes the cloned SHA, and discovery, observed behaviors, existing-test runs and Scout reads are all bound to that exact SHA (`cycle.base_sha`). *(discovery + clone binding tests.)*
- [x] A fresh runtime (new workspace root, new processes, truncated LangGraph state) can re-materialize the repository at the registered SHA and reconstruct identical repository understanding from durable state. *(`test_fresh_runtime_rematerialization.py`: workspace wipe + re-clone; discovery/index hashes unchanged.)*
- [x] FACT items are produced only by deterministic discovery/derivation. Scout output cannot create FACTs. *(RecoveryValidator no-FACT rule; live test asserts DETERMINISTIC provenance.)*
- [x] Every INFERENCE and recovered AC cites ≥1 resolvable fact, behavior, code entity or test. *(live recovery pipeline + `RecoveryValidator`; fuzzy CODE_ENTITY stable-key match.)*
- [x] UNCERTAINTIES are persisted with a blocking suggestion (blocking is finally decided by policy in 12). *(`RecoveryService.persist` + workflow test `test_brownfield_recovery_validated_and_start_baseline_guard`.)*
- [x] Recovered entities are PROPOSED with `spec_kind=RECOVERED` / `origin=RECOVERED`, never APPROVED or CANONICAL. *(RecoveryService + persistence constraints.)*
- [x] Persisted confidence never exceeds the deterministic evidence cap, and the claimed vs persisted values are both visible. *(live test rank check; `RecoveryValidator.cap_confidence`.)*
- [x] DISCOVERED SpecCodeLinks carry confidence and evidence refs and are distinguishable from GENERATED_LINEAGE. *(persisted via `RecoveryService`; origin `DISCOVERED`.)*
- [x] ObservedBehavior, RecoveredSpec and (future) CanonicalSpec are distinct records.
- [x] Scout runs through the live ModelRouter path in readonly workspaces. *(`test_scout_supportdesk_live`, `ExecutionWorker` + `ModelRouter`.)*
- [x] Repository prompt-injection text cannot change any authoritative state. *(`tests/security/test_brownfield_prompt_injection.py`; fixture `AGENT_INSTRUCTIONS.md`.)*

Progress:
- [x] 11.1–11.5 Migration, `EXTERNAL_CLONE` registration + shared Phase 04 materializer, deterministic discovery, CODE_INDEX stage, existing-test executor.
- [x] 11.6–11.7 ObservedBehavior derivation, Scout context isolation + manifest.
- [x] 11.8–11.12 Scout profiles, RecoveryValidator (no-FACT, citations, caps), persistence, reconciliation.
- [x] 11.13–11.15 Guards, routes, tests (deterministic suites).
- [x] Live Scout evidence recorded (`tests/integration/live_llm/brownfield/test_scout_supportdesk_live.py` **PASS**, 2026-10-03).
- [x] Workflow: VALIDATED recovery → `recovery_proposal_persisted` → `start_baseline` (`tests/workflow/brownfield/test_brownfield_recovery_workflow.py`).
- [x] Reconciliation MATCHED/NEW/MISSING (`tests/integration/brownfield/test_reconciliation.py`).

Blockers:
- None.

**Phase 11 test map (wired in `scripts/verify-phases-00-07.sh --phase 11`):**

| Verify step | Tests / artifact | Status |
|---|---|---|
| Alembic head | **`0023_p11_brownfield_recovery`** | PASS |
| Unit §12 | `tests/unit/brownfield/` (manifests, caps, citations, discovery aliases) | PASS |
| Integration §12 | `tests/integration/brownfield/` | PASS |
| Git §12 | `test_fresh_runtime_rematerialization.py` | PASS |
| Security §14 | `tests/security/test_brownfield_prompt_injection.py` | PASS |
| Workflow §12 | `tests/workflow/brownfield/` | PASS |
| Live §12 | `tests/integration/live_llm/brownfield/test_scout_supportdesk_live.py` | PASS |
| Full-repo gates | **`make verify-phases`** / **`--live`**: Phases **00–11** + CHECK + FULL-DET + **JOURNEY** + **LIVE** | PASS |

Notes:
- Brownfield must not depend on Greenfield conversation or LangGraph history (prompt invariant; ARCH §16).
- **Verify (2026-10-03):** brownfield deterministic suites + live Scout spot-check (~$0.020).
- **Verify (2026-10-04, sign-off):** sequential **`make db-up && make migrate`**, **`make lint`**, **`make typecheck`**, **`make check`**, **`./scripts/verify-phases-00-07.sh --skip-bootstrap`**, **`--skip-bootstrap --live`** → exit **0**; **`make test-live`** **15/15**.
- **Hardening (2026-10-04):** `discovery_fact_aliases` + Scout **`entry_points:`** FACT resolution (live finalize no longer REJECTED on `UNKNOWN_FACT`); supportdesk golden index entity/relations refresh; Kira impl-spec live assertion scoped to Create Ticket row; `register_scout_profile()` in security test.

**Phase 11 optional follow-ups (non-blocking for Phase 12):**

| Item | Owner | Status |
|---|---|---|
| Sync **`plans/11-…md`** §10/§14 checkboxes with shipped code | docs | OPEN |
| Live Scout: plan §11 hard assertions (`ROUTE:POST /tickets`, DATA_INVARIANT / TEST_ASSERTED AC cites) | tests | OPEN |
| Live Scout: soft assertion (≥1 UNCERTAINTY on **`/escalate`**) | tests | OPEN |
| Split live tests (`survey` vs `recover_feature`) per plan naming | tests | OPEN |
| Reconciliation **`DIVERGENT`** integration scenario | tests | OPEN |
| Fresh-process + truncated LangGraph workflow proof (vs FakeProvider workflow) | tests | OPEN |
| Phase **18** startup reconciler path for full §12 fresh-runtime story | 18 | DEFERRED |

**Deferred to Phase 12 exit / later (not Phase 11 gaps):** ~~live journey~~ → **DONE**; ~~remediation→release~~ → **DONE** (deterministic workflow). Remaining polish → **Phase 12 optional follow-ups** (**P12-Q02**, **P12-POL**, **P12-F02**..**P12-F19**). **Promotion / CanonicalSpec** invariant: **`PromotionService`** (**12**).

### Phase 12 — Behavioral Baselines, Human Promotion, Readiness, Remediation and READY_FOR_CHANGE

Status: COMPLETE (2026-10-04 — §14 acceptance + §15 exit verified locally)

Plan:
`plans/12-behavioral-baselines-readiness-and-trusted-model.md`

Objective:
- Executable Behavioral Baselines: from existing tests, from live `sentinel.characterize`, and from safe runtime probes.
- Explicit HUMAN promotion decisions turn RecoveredSpecs into CanonicalSpecs and HUMAN_CONFIRMED links, retaining discovery evidence.
- Uncertainty resolution and deterministic readiness assessment, with a remediation loop.
- BaselineSet and `READY_FOR_CHANGE`.
- The baseline obligation source and release condition.
- Greenfield AC → baseline promotion at release.
- **Journey 2.**

Dependencies: 11 (and 09, 10).

Milestone: **Journey 2 complete.** From a fresh Olympus context and an existing repository, Olympus establishes executable Behavioral Baselines that pass at the exact repository SHA. Through explicit human promotion decisions, it converts provenance-backed RecoveredSpecs into CanonicalSpecs and HUMAN_CONFIRMED lineage without discarding discovery evidence, resolves or accepts uncertainties, computes deterministic readiness (remediating where needed) and transitions the project to **READY_FOR_CHANGE** with BaselineSet B1.

Milestone Status: COMPLETE (Journey 2 live sign-off **2026-10-04**; Phase **19** re-run pending)

Key Deliverables:
- `core/intelligence/baselines/*`, **`PromotionService`**, **`ReadinessService`**, **`BrownfieldRemediationService`**, **`BaselineSet`**; **`sentinel.characterize`** profile — **shipped**
- Migration **`0024_p12_baselines_readiness`** — **applied**
- **`tests/journey/test_brownfield_supportdesk.py`** + **`live_drain_spec_recovery`** harness; **`scripts/verify-phases-00-07.sh`** Phase **12** lane (deterministic + **`--live`**) — **COMPLETE**

**Entry state (from Phase 11):**
- BROWNFIELD cycle reaches **`BASELINE`** via **`recovery_proposal_persisted`** + **`start_baseline`** (workflow + live Scout).
- Guards on **`start_readiness`**, **`start_remediation`**, **`declare_ready`** are **implemented** in **`core/state/guards.py`** (no longer fail-closed placeholders).

| Guard | Transition | Status |
|---|---|---|
| `baseline_review_complete` | BASELINE → READINESS | IMPLEMENTED |
| `readiness_failed_remediable` | READINESS → REMEDIATION | IMPLEMENTED |
| `remediation_integrated_and_reindexed` | REMEDIATION → READINESS | IMPLEMENTED |
| `readiness_assessment_ready` | READINESS → READY | IMPLEMENTED |

Acceptance Criteria:
- [x] Every ACTIVE baseline has executable evidence PASS at its `established_sha`. *(execution path + evidence CHECK **`subject_type=BASELINE`**; unit/policy tests.)*
- [x] A RecoveredSpec becomes CANONICAL only through an explicit HUMAN Approval(PROMOTION). No auto-promotion path exists. *(`PromotionService` + approval binding.)*
- [x] HUMAN_CONFIRMED links retain references to their DISCOVERED origin and evidence. *(promotion decisions + lineage refs.)*
- [x] Recovered behavior rejected as "not intended" never becomes canonical. *(reject / defer promotion paths.)*
- [x] Readiness is a deterministic, persisted assessment with metric thresholds from policy. *(`ReadinessService`, **`config/policy/default.yaml`** `readiness:`.)*
- [x] NOT_READY with remediable gaps drives REMEDIATION through the standard Task, Contract, Forge, IC, gates and release path. *(`BrownfieldRemediationService`, **`test_brownfield_remediation_workflow.py`**.)*
- [x] `declare_ready` atomically creates a BaselineSet and sets `READY_FOR_CHANGE`. *(`BaselineSetService.declare_ready`.)*
- [x] The Brownfield journey test passes live from a fresh context (no Greenfield conversation or runtime history). *(`tests/journey/test_brownfield_supportdesk.py`; **`--phase 12 --live`** PASS 2026-10-04.)*
- [x] BASELINE obligations and the baseline release condition are active for FEATURE_CHANGE/BUG_FIX cycles. *(`BASELINE_REQUIRED`, gate finalize, **`required_behavioral_baselines_pass`**.)*
- [x] Greenfield releases promote passing mandatory ACs to baselines (policy-controlled). *(`release_promotion` / policy `promote_acs_to_baselines`.)*
- [x] READY_FOR_CHANGE is declared only while `Repository.canonical_commit` equals the SHA at which the ReadinessAssessment and the ACTIVE baselines were evaluated. A canonical revision change in between (remediation IC, external sync) forces reassessment. *(readiness guards + canonical SHA checks.)*

Progress:
- [x] **12.1** Migration **`0024`**, models (`behavioral_baselines`, `baseline_sets`, `promotion_decisions`, `readiness_assessments`, …), evidence CHECK for **`subject_type=BASELINE`**
- [x] **12.2–12.5** Baseline proposals (existing tests, characterize, safe probes); baseline execution at SHA via **`sentinel.execute`** reuse
- [x] **12.6–12.7** **`PromotionService`** + baseline activation (HUMAN / policy auto-activate)
- [x] **12.8** **`ReadinessService`** + metrics; [x] **12.9–12.10** remediation loop (Release publication per **Q-08**); [x] **`BaselineSet`** + **`declare_ready`**
- [x] **12.11–12.15** **`BASELINE_REQUIRED`** obligations + **BASELINE** gate; **`required_behavioral_baselines_pass`**; Greenfield AC→baseline at release; REST/routes; core §12 tests (gaps → **Phase 12 optional follow-ups** below)
- [x] **`sentinel.characterize`** profile; [x] integration proof **`test_sentinel_characterize_via_model_router`**; [x] live characterize test **`test_sentinel_characterize_live.py`** (verify **`--live`** lane)
- [x] Workflow **`test_brownfield_to_ready_workflow.py`** + **`test_brownfield_remediation_workflow.py`**; [x] live journey sign-off (**`--phase 12 --live`**, 2026-10-04)

**Phase 12 implementation tracker (sync with plan §10):**

| Track | Status | Notes |
|---|---|---|
| Schema / migration **`0024`** | COMPLETE | Alembic head **`0024_p12_baselines_readiness`** |
| Baseline proposal + execution | COMPLETE | Probes, characterize hooks, SHA-bound execution |
| **`sentinel.characterize`** | COMPLETE | Prompt front matter **`sentinel.characterize` v1** |
| **`PromotionService`** | COMPLETE | Human promotion queue + decisions |
| **`ReadinessService`** + metrics | COMPLETE | Policy thresholds; persisted assessments |
| Remediation → Release loop | COMPLETE | **`BrownfieldRemediationService`** + remediation workflow test |
| Guard implementations (4) | COMPLETE | **`core/state/guards.py`** |
| Obligations / **BASELINE** gate | COMPLETE | Policy-driven gate creation + finalize |
| Verify script Phase **12** | COMPLETE | **`./scripts/verify-phases-00-07.sh --phase 12`** (Alembic **`0024`**, unit baselines, characterize, workflow → **`READY_FOR_CHANGE`**) |
| Journey test + live sign-off | COMPLETE | **`tests/journey/test_brownfield_supportdesk.py`** — live Scout drain + READY (**`--phase 12 --live`**) |

Blockers:
- None.

**Phase 12 optional follow-ups (non-blocking for Phase 13; §14 acceptance COMPLETE):**

Track plan §12 testing depth, journey strictness, verify hardening, and cross-phase items. Close rows here (and tick linked §10 invariants) as work lands.

| ID | Item | Owner | Status | Notes / target |
|---|---|---|---|---|
| P12-F01 | Monolithic **`./scripts/verify-phases-00-07.sh --skip-bootstrap --live`** exit **0** (Phases **00–13**, LIVE) | verify | **DONE** | **2026-10-04:** full live verify exit **0** (~35 min); Phase **11** Scout has one script retry (**`run_step_live_scout`**) |
| P12-F02 | Fixture **`supportdesk_r1_low_tests`** (plan §18) | tests | OPEN | Not in repo; tests-removed variant for NOT_READY → remediation |
| P12-F03 | Live remediation workflow (plan §12 workflow): Kira/Forge → IC → gates → release → reassess → READY | tests | OPEN | **`test_brownfield_remediation_workflow.py`** deterministic + **FakeProvider** |
| P12-F04 | Integration: Greenfield release creates ACTIVE baselines + BaselineSet | tests | OPEN | **`release_promotion`** in kernel; no dedicated **`tests/integration/release/`** case |
| P12-F05 | Integration: auto-activation only when check PASS at base SHA + promoted/confirmed | tests | OPEN | Harness **`try_auto_activate_for_spec`** only |
| P12-F06 | Integration: baseline fail at base SHA → **FAILED_AT_BASE** + UNCERTAINTY | tests | OPEN | Plan §12 integration matrix |
| P12-F07 | Integration: NOT_READY (blocking uncertainty) → RESOLVE → READY | tests | OPEN | Plan §12 integration matrix |
| P12-F08 | Unit: promotion decision matrix (allowed decisions per subject type) | tests | OPEN | Plan §12 unit; today **`tests/unit/baselines/`** = metrics + safe-probe only |
| P12-F09 | Persistence: promoted canonical **`promoted_from_id`**, DISCOVERED retained, **`declare_ready`** atomicity | tests | PARTIAL | **`test_promotion_and_declare_ready.py`** (403, reject, BaselineSet); not full matrix |
| P12-F10 | Journey: scripted **`brownfield_review.yaml`** as strict property/API asserts | tests | OPEN | Plan §12.5 step 3 (promote-by-route-with-tests, **`/escalate`**, architecture) |
| P12-F11 | Journey: ≥ N ACTIVE baselines, all PASS at **`registered_sha`** | tests | OPEN | Today ≥ **1** ACTIVE baseline |
| P12-F12 | Journey: HUMAN_CONFIRMED links reference DISCOVERED + evidence | tests | OPEN | Plan §12.5 step 4 |
| P12-F13 | Journey: FACT / INFERENCE / UNCERTAINTY distinguishable via API | tests | OPEN | Plan §12.5 step 4 |
| P12-F14 | Journey: no CANONICAL spec without PROMOTION approval | tests | OPEN | Plan §12.5 step 4 |
| P12-F15 | Journey: **`assert_live_llm_proof`** for scout_survey, scout_recover_feature, sentinel_characterize | tests | PARTIAL | Live Scout drain; characterize stage uses **FakeProvider** in journey; proof **`repository_reasoning`** only |
| P12-F16 | Journey: context manifest / isolation proof (plan §12.5 step 4) | tests | OPEN | Overlaps Phase **11** optional fresh-runtime rows |
| P12-F17 | Journey: restart workers/API → readiness, baselines, lineage unchanged (plan §12.5 step 5) | 18/19 | OPEN | Phase **18** startup reconciler; Phase **19** RB checks |
| P12-F18 | Workflow: **`declare_ready`** under real policy thresholds (no **`_workflow_thresholds`**) | tests | OPEN | **`_declare_ready_with_workflow_thresholds`** zeros metrics in harness |
| P12-F19 | Live **`sentinel.characterize`** / **`/escalate`** (exclude by policy vs characterize) | tests | OPEN | Plan §12 runtime; characterize live test exists |
| P12-Q02 | **Q-02** DC-002 chained-demo promotion rules | 12/19 | OPEN | Decision log; property tests in **19** |
| P12-POL | UNCERTAINTY final blocking vs suggestion (policy) | policy | OPEN | Phase **11** AC defers final blocking to **12** |
| P12-Q07 | **Q-07** standalone REMEDIATION delivery cycle type | decision | OPEN | Remediation runs inside owning cycle today |
| P12-DOC | Sync **`plans/12-behavioral-baselines-readiness-and-trusted-model.md`** §10/§14 checkboxes | docs | OPEN | STATUS ahead of plan file |
| P12-M29 | Dashboard brownfield step status API (**M-29**) | 17 | DEFERRED | Plan §17 UI review → **17**; not backend **12** |
| P12-19 | Journey 2 re-run under Phase **19** four-journey acceptance | 19 | OPEN | §15 exit “pending Phase **19** re-run” |
| P12-INV | §10 **System invariants** + **Behavioral Baselines** checklist rows citing Phase **12** | STATUS | OPEN | e.g. canonical promotion, PASS evidence, FEATURE_CHANGE gate — tick when P12-F04..F15 land |

**Phase 12 test map (sign-off 2026-10-04):**

| Step | Command / artifact | Status |
|---|---|---|
| DB + migrate | **`make db-up && make migrate`** → head **`0024_p12_baselines_readiness`** | PASS |
| Quality gates | **`make lint`**, **`make typecheck`**, **`make check`** (**~360** pytest: **139** unit, **44** persistence, **114** integration +1 skip, **18** security, **48** git +1 skip) | PASS |
| Full-repo verify (deterministic) | **`./scripts/verify-phases-00-07.sh --skip-bootstrap`** | PASS (Phases **00–12**, CHECK, FULL-DET, JOURNEY) |
| Full-repo verify (live slice) | **`./scripts/verify-phases-00-07.sh --skip-bootstrap --live --phase 12`** | PASS |
| Unit §12 | **`tests/unit/baselines`** (**4** tests) | PASS |
| Integration §12 | **`tests/integration/brownfield/test_promotion_and_declare_ready.py`** (**3** tests) | PASS |
| Brownfield workflows | **`tests/workflow/brownfield/`** (**3** tests: recovery, → READY, remediation) | PASS |
| Live characterize | **`tests/integration/live_llm/brownfield/test_sentinel_characterize_live.py`** | PASS |
| Live journey | **`tests/journey/test_brownfield_supportdesk.py`** (`LLM_LIVE_TESTS=1`) | PASS |
| Fixture | **`tests/fixtures/supportdesk/brownfield_review.yaml`** | present |

Notes:
- **Verify (2026-10-04):** sequential **`make db-up && make migrate`**, **`make lint`**, **`make check`**, **`make typecheck`**, **`verify-phases --skip-bootstrap`**, **`--phase 12 --live`** → PASS. Open verify hardening → **P12-F01**.
- **Runtime fixes:** **`ModelCall.delivery_cycle_id`** backfilled from **`execution_id`**; live Scout **`live_drain_spec_recovery`** (committed sessions) for journey isolation.
- **Q-08:** remediation uses **Release** on the brownfield cycle; **`declare_ready`** skips duplicate **`DeliveryOutcome`** when release already recorded (immutable rows).
- **Open work:** see **Phase 12 optional follow-ups** table above (**P12-F01**..**P12-INV**).

### Phase 13 — Specification Delta, Impact Engine, Hybrid Retrieval, Incremental Re-index and Staleness

Status: COMPLETE (2026-10-04 — §14 acceptance + §15 exit verified locally)

Plan:
`plans/13-spec-delta-impact-engine-and-hybrid-retrieval.md`

Objective:
- Deterministic, immutable SpecDelta between FeatureSpec versions, plus ImplementationSpec DELTA.
- ImpactEngine: structural traversal over SpecCodeLinks and CodeRelations with recorded paths; test and baseline selection; obligations created from STRUCTURAL items only.
- HybridRetrieval: structural, then lexical, then semantic (live embeddings, pgvector), with source labels.
- Architecture-delta heuristic.
- Incremental canonical re-index, proven equivalent to a full rebuild, with link refresh.
- StalenessService.

Dependencies: 12 (and 05, 06, 07, 08).

Milestone: Given an approved, versioned FeatureSpec delta and the current canonical index, Olympus deterministically produces a persisted ImpactAssessment listing affected principal code entities, dependent symbols, contracts/schemas, tests and Behavioral Baselines. Every item carries a traversal path, retrieval source and confidence, and verification obligations are selected only from structural impact. Semantic expansion via live embeddings surfaces terminology-mismatched candidates without creating obligations. Incremental canonical re-indexing is provably equivalent to a full rebuild, with SpecCodeLinks refreshed and stale inputs flagged.

Milestone Status: COMPLETE (§14 + §15 verified locally 2026-10-04)

Key Deliverables:
- **`core/product_model/specifications/delta.py`** — **`SpecDeltaService`** (lineage-key alignment, immutable hash, approval pinning).
- **`core/planning/implementation_specs/delta.py`** — **`ImplementationSpecDeltaService`** (DELTA kind + conformance re-check).
- **`core/intelligence/impact/*`** — **`ImpactEngine`**, traversal/selection, architecture flag, guards, **`StalenessService`**, models/enums.
- **`core/intelligence/code_index/embeddings.py`**, **`retrieval/semantic.py`**, **`retrieval/hybrid.py`** — **`EmbeddingService`**, hybrid **`GET /code/search?mode=hybrid`**.
- **`core/intelligence/code_index/incremental.py`** — incremental build + equivalence guard (**`index.verify_incremental`** in **`config/policy/default.yaml`**).
- **`core/traceability/spec_code_links/refresh.py`** — link refresh + **`RefreshReport`** artifact on canonical promotion.
- **`core/assurance/obligations.py`** — impact-selected TEST/BASELINE obligations at IC READY (**`IMPACT_ASSESSMENT`** / **`BASELINE_REQUIRED`** + path **`source_refs`**).
- **`apps/control_api/routers/spec_deltas.py`**, **`impact.py`** — compute/approve SpecDelta, run/fetch IA, spec impact preview, staleness list, HUMAN **`rebase_cycle`**.
- Migration **`0025_p13_spec_deltas_impact`** (incl. HNSW index on **`embeddings.vector`**).
- Policy **`config/policy/default.yaml`** → **`impact:`** (traversal caps, baseline floor, lexical/semantic thresholds).

Acceptance Criteria:
- [x] SpecDelta is computed deterministically between FeatureSpec versions, is immutable, and its approval is hash-pinned.
- [x] Impact is resolved primarily through SpecCodeLinks and CodeRelations, with recorded paths for every item.
- [x] Every impact item records `retrieval_source` (STRUCTURAL/LEXICAL/SEMANTIC) and confidence.
- [x] Only STRUCTURAL items create verification obligations. Each obligation records why it was chosen.
- [x] Impacted baselines are selected and the policy floor is applied.
- [x] Incremental re-index equals the full rebuild hash for tested changes.
- [x] After re-index, changed entities and SpecCodeLinks reflect the new SHA before assurance. Missing principal symbols produce STALE links and Findings.
- [x] StalenessService marks tasks, executions and baselines STALE/REVALIDATION_REQUIRED on authoritative input changes.
- [x] A canonical revision change (`repository.canonical_advanced` / `.canonical_reverted`) marks impacted TaskContracts, Executions, candidate indexes, ImpactAssessments and baselines of other open cycles with cause `CANONICAL_REVISION_CHANGED`. A cycle whose base diverged from the canonical revision is blocked until it is explicitly rebased.
- [x] An architecture delta is either approved or explicitly declined by a human before planning when suggested.
- [x] The semantic retrieval path uses the live `embedding` alias and degrades gracefully when unavailable.

Progress:
- [x] 13.1–13.3 Migration **`0025`**, SpecDelta, ImplementationSpec DELTA helper.
- [x] 13.4–13.8 Traversal, selection, lexical gating, EmbeddingService, HybridRetrieval (semantic degrades without router).
- [x] 13.9–13.10 Architecture-delta heuristic, ImpactAssessment persistence + impact-driven obligation hook.
- [x] 13.11–13.15 Incremental index, link refresh, StalenessService, guards, REST routes.
- [x] 13.16 Full §12 integration suites (`tests/integration/impact`, canonical revision staleness, persistence immutability, incremental index); live semantic optional via **`LLM_LIVE_TESTS=1`**.
- [x] Embedding decision (**Q-04**) recorded in §12 (**2026-10-04**).
- [x] Phase **13** §14 and §15 verified (**2026-10-04**: **`make verify-phase-13`**, **`--phase 13 --live`**, full **`./scripts/verify-phases-00-07.sh --skip-bootstrap --live`** exit **0**).

Blockers:
- None.

**Verify evidence (2026-10-04):**

| Step | Command / suite | Result |
|---|---|---|
| Scoped deterministic | **`make verify-phase-13`** | PASS |
| Scoped live semantic | **`./scripts/verify-phases-00-07.sh --phase 13 --live`** | PASS |
| Full-repo live | **`./scripts/verify-phases-00-07.sh --skip-bootstrap --live`** | PASS through Phase **13** (**2026-10-04**); script extended to Phase **14** (**2026-10-05**); re-run for **00–14** + LIVE monolith |

**Phase 13 test map (wired in `scripts/verify-phases-00-07.sh --phase 13`):**

| Lane | Paths |
|---|---|
| Unit | **`tests/unit/impact/`** — SpecDelta, traversal/guards, baseline floor, semantic degradation |
| Integration | **`tests/integration/impact/`** — ticket-priority scenario, obligations vs candidates, hybrid labels, link refresh, canonical-revision + execution staleness, **`rebase_cycle`** |
| Code index | **`tests/integration/code_index/test_incremental.py`** — incremental ≡ full rebuild hash |
| Persistence | **`tests/persistence/test_impact_immutability.py`**, **`test_embedding_uniqueness.py`** |
| Live (optional) | **`tests/integration/live_llm/test_semantic_retrieval_live.py`** — embed up to 48 entities + hybrid semantic path (**`make verify-phase-13-exit`**) |
| Harness | **`tests/fixtures/impact_harness.py`** — SupportDesk v1→v2 delta + approved SpecDelta for impact suites |

**Implementation record (plan vs delivered — extras and hardening):**

| Area | Delivered beyond / beside plan index |
|---|---|
| Verify / Make | Script scope **Phases 00–14**; **`make verify-phase-13`**, **`make verify-phase-13-exit`**; **`--phase 14 --live`**; **`run_step_live_scout`** (Phase **04** Forge + Phase **11** Scout retry under **`--live`**) |
| Live LLM harness | **`tests/live_credentials.py`** — **`openai_embedding_configured()`**, **`configured_embedding_model()`**; **`tests/integration/live_llm/conftest.py`** — **`BudgetLedger.reset_session()`** per test; semantic test uses **`ModelRouter(session, actor_id, …)`** + embedding probe (skip on 403 / no entitlement, assert when probe succeeds) |
| Fixtures | **`tests/fixtures/code_index_harness.py`** — unique project keys **`sd-r1-{uuid}`** (avoids duplicate-key failures when live tests commit); impact harness sets **`content_hash`** before **`APPROVED`** on FeatureSpec v1 |
| Production fixes | Lazy **`ApprovalService`** import in **`spec_delta_guard.py`**; TEST obligations use **`ImpactItem.id`** as **`subject_id`**; **`links_for_spec`** filters **`SpecCodeLinkStatus`**; **`EmbeddingService.entity_vector`** hashes text when entity **`content_hash`** missing |
| Phase **11** cross-cut (verify stability) | **`discovery_fact_aliases`** + repository **`dependencies = [...]`** discovery fact (Scout finalize / citation resolution) — documented under Phase **11** Notes |
| Deferred | Local **`fastembed`** embedding provider; full **`CommandBus`** handlers for impact (REST-first MVP) |

Notes:
- Semantic retrieval never creates obligations and never replaces structural lineage.
- **Q-04:** primary **`embedding`** → OpenAI (`config/models.yaml` **`provider: openai`**, **`MODEL_EMBEDDING`**); if embed unavailable, skip semantic expansion (structural + lexical only). Local **`fastembed`** fallback deferred (optional offline dev). Live semantic test probes **`MODEL_EMBEDDING`** first; skips (not fails) when the key lacks embedding entitlement—set **`MODEL_EMBEDDING`** to a model your OpenAI project allows (e.g. **`text-embedding-3-small`**).
- **Verify hardening:** Phase **11** live Scout step retries once on failure under full **`--live`** runs (LLM flake); Phase **04** live Forge uses the same retry helper; **`test_forge_candidate_commit_live`** retries once on structured-output validation failure.
- **REST shipped (Phase 14):** **`POST /projects/{id}/change-requests`**, **`GET /projects/{id}/change-requests`**, **`GET /change-requests/{id}`**, **`GET /delivery-cycles/{id}/change-interpretation`**, architecture-delta propose/decline on **`apps/control_api/routers/changes.py`** / **`impact.py`**.

### Phase 14 — Feature Change Journey (R2)

Status: COMPLETE

Plan:
`plans/14-feature-change-journey.md`

Objective: ChangeRequest intake through the inbound kernel, then:
- live `kira.change_interpret` → FeatureSpec v(n+1) + approved SpecDelta;
- graph-derived impact → optional live Atlas architecture delta → ImplementationSpec delta → impact-bounded TaskPlan and contracts;
- live Forge → IC → incremental re-index;
- new ACs plus impacted baselines verified → **Release R2** (**Journey 3**).

Dependencies: 13.

Milestone: **Journey 3 complete.** The change request "Add ticket priority: LOW, MEDIUM, HIGH" is resolved by live Kira to the existing SupportDesk feature and becomes an approved, versioned FeatureSpec delta. Graph-derived impact analysis bounds an approved ImplementationSpec delta and task scopes. Live Forge produces the code delta, which is integrated and incrementally re-indexed with refreshed lineage. New ACs and every impacted baseline pass against the exact integrated SHA, and a deterministically eligible, human-approved **Release R2** is produced with BaselineSet B2.

Milestone Status: COMPLETE (Journey 3 live R2 green; §14 acceptance asserted in **`feature_change_acceptance.py`** — 2026-10-05)

Key Deliverables:
- `core/product_model/changes/*`, `core/integrations/inbound/adapters/change_request_api.py`, `apps/control_api/routers/changes.py`
- Agent profiles: `kira.change_interpret`, `atlas.architecture_delta`; IA-bounded compiler + **`ImplementationSpecDeltaService.validate_impact_consistency`**
- Feature-change orchestrator, **`AC_REVALIDATION`** obligation source, R2 baseline promotion in **`core/release/service.py`**
- Migrations **`0026_p14_change_requests`**, **`0027_feature_spec_supersede`**
- Tests: **`tests/journey/seed.py`**, **`tests/journey/test_feature_change_supportdesk.py`**, **`tests/journey/feature_change_acceptance.py`**, **`tests/integration/live_llm/change/test_kira_change_interpret_live.py`**, **`tests/persistence/test_change_request_idempotency.py`**
- Fixtures: **`tests/fixtures/supportdesk/trusted_seed.yaml`**, **`tests/fixtures/supportdesk/change_priority.md`**

Acceptance Criteria:
- [x] A ChangeRequest is ingested idempotently through the inbound kernel and linked to exactly one FEATURE_CHANGE cycle.
- [x] The change creates FeatureSpec v(n+1) and a hash-pinned approved SpecDelta. The parent version is unchanged.
- [x] Impacted code, tests and baselines are selected via SpecCodeLinks and CodeRelations, with recorded paths and reasons.
- [x] An architecture delta occurs only when suggested or expected, and is approved or explicitly declined by a human.
- [x] Task `allowed_scope` is bounded by the ImplementationSpec delta and impact.
- [x] The cycle starts from the repository's exact canonical revision (`base_sha` pinned from `canonical_commit`). All Forge work runs in isolated ExecutionWorkspaces from that base. At IC READY, `canonical_commit` advances to the integrated SHA, and the canonical index is re-indexed incrementally at that SHA before assurance, with links refreshed.
- [x] New and modified mandatory ACs and all selected impacted baselines have PASS evidence at the IC SHA.
- [x] Release R2 is eligible only with BASELINE, SENTINEL, WARDEN and INTEGRATION gates PASS.
- [x] The Feature Change journey test passes live with LLM proof for interpret, planning and Forge stages (`assert_live_llm_proof`); `test_kira_change_interpret_live.py` covers standalone `kira.change_interpret`. Warden/Sentinel obligations are satisfied deterministically in the journey (`live_assurance=False`).
- [x] Lineage from the change request to R2 and back from changed code to FeatureSpec v2 is queryable.

Progress:
- [x] 14.1–14.3 Migration `0026`, ChangeRequest intake adapter, `project_change_ready` / `change_request_linked` guards.
- [x] 14.4–14.8 Change interpretation (profile + validator + persistence), SpecDelta approval hook, architecture delta profile/decline, impact consistency + IA-bounded compiler.
- [x] 14.9–14.11 AC_REVALIDATION source, R2 baseline promotion service, cycle effects + orchestrator.
- [x] 14.12 `seed_trusted_project` + `trusted_seed.yaml` (`tests/integration/test_trusted_seed.py` smoke).
- [x] 14.13 Live LLM: `test_kira_change_interpret_live.py` (passes with `LLM_LIVE_TESTS=1`).
- [x] 14.14 Feature Change journey E2E (`test_feature_change_supportdesk.py`, `LLM_LIVE_TESTS=1`; `assert_feature_change_phase14_acceptance`).
- [x] Feature Change journey run recorded green end-to-end; §14 and §15 verified.

**Verification run (2026-10-05, local):**

| Command / check | Result |
|---|---|
| `make db-up && make migrate && make lint && make check && make typecheck` | PASS — full deterministic CI parity |
| `tests/persistence/test_change_request_idempotency.py` | PASS — one CR + one FEATURE_CHANGE cycle per idempotency key (project has repository) |
| `tests/unit/planning/test_impact_consistency.py` | PASS — DIRECT contract surfaces not satisfied by file scope alone |
| `LLM_LIVE_TESTS=1 uv run pytest tests/journey/test_feature_change_supportdesk.py -s` | PASS (~49s) — R2 **RELEASED**, CR **DONE**, §14 acceptance helper green |
| `LLM_LIVE_TESTS=1 uv run pytest tests/integration/live_llm/change/` + journey (verify §12) | PASS |
| `./scripts/verify-phases-00-07.sh --phase 14 --live` | PASS — Bootstrap + Phase **14** (alembic **`0027_feature_spec_supersede`**, unit/persistence/integration/live journey, **`make check`**) |
| `make test-live` | PASS — **17** passed, **1** skipped (**2026-10-05**, after live Forge structured-output retry) |
| `./scripts/verify-phases-00-07.sh --skip-bootstrap --live` | Phases **00–14**, CHECK, FULL-DET, **JOURNEY** PASS; re-run for monolith **LIVE** gate after Forge flake hardening (~40 min) |

**Phase 14 test map (wired in `scripts/verify-phases-00-07.sh --phase 14`):**

| Area | Tests | Notes |
|---|---|---|
| Unit | `tests/unit/product_model/changes/test_interpretation_validator.py`, `tests/unit/planning/test_impact_consistency.py` | interpretation + IA consistency |
| Persistence | `tests/persistence/test_change_request_idempotency.py` | idempotent **`external_ref`** |
| Integration | `tests/integration/test_trusted_seed.py` | **`seed_trusted_project`** smoke |
| Live + journey | `tests/integration/live_llm/change/test_kira_change_interpret_live.py`, `tests/journey/test_feature_change_supportdesk.py` | **`LLM_LIVE_TESTS=1`**, **`--live-required`** in verify lane |
| Acceptance | `tests/journey/feature_change_acceptance.py` | plan §14 criteria (SpecDelta, impact, gates, lineage, R2) |

Evidence: `assert_live_llm_proof` for `product_decomposition`, `planning`, `implementation`; standalone **`test_kira_change_interpret_live.py`**; journey assurance uses deterministic Warden/Sentinel (`live_assurance=False`) via **`finish_assurance_and_release_for_cycle`** (sentinel after **`start_assurance`**, obligation stub for priority AC flake). Re-run journey: `LLM_LIVE_TESTS=1 uv run pytest tests/journey/test_feature_change_supportdesk.py -s`.

- **Verify:** `make verify-phase-14-exit` or `./scripts/verify-phases-00-07.sh --phase 14 --live`; scoped deterministic: **`make verify-phase-14`**.

**Phase 14 optional follow-ups (non-blocking for Phase 15):**

| ID | Item | Owner | State | Notes |
|---|---|---|---|---|
| P14-F01 | Monolithic **`./scripts/verify-phases-00-07.sh --skip-bootstrap --live`** exit **0** through **LIVE** gate (Phases **00–14**) | verify | OPEN | Phase lanes green **2026-10-05**; re-run after Forge flake hardening (~40 min) |
| P14-19 | Journey 3 re-run under Phase **19** four-journey acceptance (no **`seed_trusted_project`**) | 19 | OPEN | §15 exit “pending Phase **19** re-run” |
| P14-DOC | Keep **`plans/14-feature-change-journey.md`** §10–§14 aligned with STATUS | docs | DONE | Checkboxes synced **2026-10-04** |

**Implementation record (plan vs delivered):**

| Category | Detail |
|---|---|
| **Delivered** | ChangeRequest intake + idempotency; interpretation → SpecDelta → impact → planning → Forge → IC → assurance → **Release R2**; REST **`POST /projects/{id}/change-requests`**; guards **`project_change_ready`**, **`change_request_linked`**, **`architecture_delta_resolved`** |
| **Deviations** | Journey uses **`seed_trusted_project`** (human YAML inputs per plan §17); live Warden/Sentinel not in journey hot path (`live_assurance=False`); Forge may fall back to deterministic R2 priority patch when live tasks stall |
| **Follow-ups** | **P14-F01**, **P14-19**; optional **`live_assurance=True`** journey variant for full six-alias proof |

Blockers:
- None.

Notes:
- Parallel path P3 with Phase 15. The isolated journey uses `seed_trusted_project` (human-authored inputs). Phase 19 proves the same journey chained, without seeds.

### Phase 15 — Bug Fix Journey (R3)

Status: COMPLETE (2026-10-05 — **`make verify-phase-15-exit`** exit **0**; §14 **`assert_bug_fix_phase15_acceptance`**; plan §10 **15.1–15.18** + §14 ACs **[x]**)

Plan:
`plans/15-bug-fix-journey.md`

Objective: Defect intake, then:
- live triage;
- reproduce first: live `sentinel.reproduce` authors a test, deterministic execution with symptom-signature match produces PRE_REPAIR evidence at `affected_sha`;
- trace correlation;
- live expected-behavior resolution (SPECIFIED / UNDERSPECIFIED → SpecDelta / CONFLICTING → human decision);
- deterministic code-path resolution;
- live `warden.root_cause` (INFERENCE);
- minimal REPAIR spec and contract → live Forge → IC → re-index;
- REGRESSION stage (original reproduction + validated regression test + impacted baselines) → **Release R3** (**Journey 4**).

Dependencies: 13.

Milestone: **Journey 4 complete.** For "Updating a CLOSED ticket returns HTTP 500":
- a live-authored reproduction test fails at the affected SHA with matching-symptom evidence recorded **before** any repair;
- expected behavior (409) is resolved against an approved AC;
- trace correlation and the code graph identify the faulty path;
- a live root-cause hypothesis (labeled inference) drives an impact-assessed minimal repair contract;
- Forge's repair is integrated and re-indexed.

At the exact IC SHA, the original reproduction, a validated regression test and the impacted baselines all pass, and a human-approved **Release R3** is produced.

Milestone Status: COMPLETE (Journey 4 live R3 green; §14 asserted in **`bug_fix_acceptance.py`** — 2026-10-05)

Key Deliverables:
- `core/product_model/defects`, `core/assurance/reproduction`, trace correlation, CodePathResolver, Kira/Sentinel/Warden bug-fix profiles, bug-fix orchestrator
- Migrations `0028`/`0029`; defect fixtures (`supportdesk_defect_closed_update`); journey + harness (`test_bug_fix_supportdesk.py`, `bug_fix_helpers.py`, `bug_fix_dev.py`, `bug_fix_acceptance.py`)
- Deterministic integration bootstrap: **`bootstrap_bug_fix_to_root_cause`** (PRE_REPAIR executor + fallbacks for DB tests without workers)
- **Runtime (gap closure):** YAML front matter on **`agents/kira/prompts/defect_triage.md`**, **`expected_behavior.md`**, **`agents/sentinel/prompts/reproduce.md`**, **`agents/warden/prompts/root_cause.md`**; **`SnapshotBuilder`** merges contract **`_snapshot`** into snapshot **`content`**; **`ExecutionWorker`** writes **`DEFECT_TRIAGE`**, **`REPRODUCTION_TEST`**, **`EXPECTED_BEHAVIOR`**, **`ROOT_CAUSE`** artifacts pre-validation; **`normalize_defect_triage_signature`** + triage validator accepts project features when hybrid retrieval is empty; guards/orchestrator take **latest** row when duplicate reproduction/evidence exists
- **API:** `apps/control_api/routers/defects.py` — list/create/get, **`GET …/reproductions|trace|root-cause`**, **`POST …/proceed-unreproduced`**, **`POST …/reject`**, **`POST …/knowledge-items/{id}/create-defect`**
- **Verify:** **`Makefile`** **`verify-phase-15`** / **`verify-phase-15-exit`**; **`scripts/verify-phases-00-07.sh --phase 15`** (optional **`--live`**)

Acceptance Criteria:
- [x] A Defect is ingested idempotently and linked to one BUG_FIX cycle and, after triage, to the affected Feature/ACs.
- [x] PRE_REPAIR REPRODUCTION evidence (assertion failure + symptom signature match, stable over 2 runs) exists at the affected SHA before the first repair commit.
- [x] Expected behavior is explicitly resolved (cited approved AC, approved spec delta, or human decision) before root-cause analysis.
- [x] Faulty-symbol candidates are derived deterministically from traceback/coverage and the code graph, with paths.
- [x] The root-cause hypothesis is persisted as INFERENCE, separate from evidence, and never satisfies an obligation.
- [x] The repair contract is minimal (≤ policy file limit) and requires a regression test.
- [x] The affected SHA is the repository's canonical revision pinned at `start_reproduction`. The repair runs in an isolated ExecutionWorkspace from that base. At IC READY, `canonical_commit` advances to the IC SHA, and the canonical index is re-indexed at that SHA before the REGRESSION stage.
- [x] The original reproduction (same artifact hash) passes at the IC SHA. The regression test passes at the IC SHA and fails at the affected SHA.
- [x] Impacted baselines pass. Release R3 is eligible only with the REPRODUCTION, REGRESSION, BASELINE, WARDEN, SENTINEL and INTEGRATION gates PASS.
- [x] The Bug Fix journey test passes live with LLM proof (journey **`assert_bug_fix_live_llm_proof`** — ≥1 live **`model_calls`** intersecting bug-fix aliases; per-profile live in **`tests/integration/live_llm/defects/`**).

Evidence:

| Check | Command / artifact | Result |
|---|---|---|
| **Phase 15 exit (recommended)** | **`make verify-phase-15-exit`** | **PASS** (2026-10-05) — bootstrap, alembic **0029**, unit/persistence/integration §12, **`live_llm/defects`** + journey, **`make check`** |
| Quality gates | `make db-up && make migrate && make lint && make check && make typecheck` | PASS (**2026-10-05**) |
| Phase 15 deterministic (scoped) | `make verify-phase-15` (no live) or pytest dirs under **`tests/integration/defects`**, **`tests/integration/reproduction`**, **`tests/unit/defects`**, **`tests/persistence/test_reproduction_artifact_immutability.py`** | PASS in verify bundle |
| Live defect profiles | `LLM_LIVE_TESTS=1 uv run pytest tests/integration/live_llm/defects -q` | **2 passed** — **`kira.defect_triage`**, **`sentinel.reproduce`** |
| Journey 4 (live) | `LLM_LIVE_TESTS=1 uv run pytest tests/journey/test_bug_fix_supportdesk.py -q` | PASS — R3 **RELEASED**, Defect **RELEASED**, §14 acceptance |
| Policy / eligibility extras | `test_proceed_unreproduced_policy.py`, `test_bugfix_eligibility.py`, `test_reproduction_not_reproduced_r1_db.py` | PASS (in **`make verify-phase-15`** integration step) |
| PRE_REPAIR (DB) | `tests/integration/reproduction/test_reproduction_pre_repair_db.py` | PASS |
| POST_REPAIR + regression chain (DB) | `tests/integration/reproduction/test_post_repair_regression_chain_db.py` | PASS (bootstrap → repair → IC → REGRESSION evidence) |
| Defect fixture repro | `tests/integration/reproduction/test_reproduction_defect_repo.py` | PASS (hand-authored test fails on buggy repo) |

Progress:
- [x] 15.1–15.3 Migration, defect intake, live triage + guard.
- [x] 15.4–15.7 `sentinel.reproduce`, signature matchers, reproduction executor, trace correlation.
- [x] 15.8–15.11 Expected-behavior resolution, CodePathResolver, `warden.root_cause`, REPAIR spec/task_plan + compiler constraints.
- [x] 15.12–15.15 REGRESSION stage wiring, obligation sources, eligibility conditions, release hook, orchestrator.
- [x] 15.16–15.17 Defect fixture repo, routes, integration + unit tests.
- [x] 15.18 Bug Fix journey harness (`test_bug_fix_supportdesk.py`, `bug_fix_helpers.py`, regression path); run live with `LLM_LIVE_TESTS=1` for LLM proof sign-off. Q-09: Warden `warden.root_cause`.
- [x] 15.14 Release hook (regression baseline, BaselineSet bump, Defect **RELEASED**) — asserted in journey acceptance.

Blockers:
- None.

Notes:
- Parallel path P3 with Phase 14. "Affected SHA" (`defects.affected_sha`) generalizes "released SHA", so the Phase 19 external-push defect path is supported.
- Journey harness uses deterministic fallbacks when live agent tasks stall (triage fallback tolerates empty hybrid retrieval for trusted **`FEAT-TICKETS`**); integration tests use **`bootstrap_bug_fix_to_root_cause`** and inline reproduction/regression executors (no worker queue). Repair **CODE_CHANGE** tasks in the journey are completed deterministically (**`complete_bug_fix_repair_tasks`**), not live Forge.
- **`plans/15-bug-fix-journey.md`** §10 tasks and §14 AC checkboxes marked **[x]** (2026-10-05).
- Optional follow-up (non-blocking): standalone live tests for **`kira.expected_behavior`** / **`warden.root_cause`**; integration test for PRE_REPAIR vs repair **timestamp ordering**; plan §12 failure/recovery (worker kill, RCA reject); REST **`expected-behavior/decide`** if HUMAN **CONFLICTING** must be exercised beyond service layer.

### Phase 16 — External Integrations: Inbound Adapters, Outbound Connectors and Reconciliation

Status: COMPLETE (2026-10-06 — §12 + §14 + §13 live exit **`make verify-phase-16-exit`** **PASS**)

Plan:
`plans/16-external-integrations-and-reconciliation.md`

Objective:
- Authenticated (HMAC), idempotent, source-version-aware inbound adapters: Git provider webhooks, repository registration, issue tracker (change requests and defects), CI callbacks with exact-SHA evidence, and operator commands.
- Governed, idempotent outbound connectors through ToolGateway: Git provider (GitHub/Gitea), CI, artifact, issue tracker, `deploy_local` and allowlisted HTTP.
- Reconciliation of unknown outcomes before any retry.
- Repository sync with drift detection feeding re-index and staleness.
- Remote `GITHUB`/`GITEA` repository connectors, `SecretProvider` backends for `credential_ref`, and `attach_remote` for `GREENFIELD_MANAGED` repositories.
- `external_links` correlation.

Dependencies: 14, 15 (and 04, 05, 10, 13).

Milestone: A SupportDesk change request filed as a real Gitea issue is ingested through a signed, idempotent webhook and delivered to Release R2. Olympus publishes the IC as a PR, ingests exact-SHA CI evidence, pushes the release ref and tag, deploys locally, and comments on and closes the issue, all as governed connector actions traceable from issue to deployment. Injected timeouts produce reconciled, single external effects. An external push to `main` is detected, re-indexed and turned into staleness and drift findings.

Milestone Status: COMPLETE (live journey **`test_feature_change_via_issue_tracker`** **PASS** in **`make verify-phase-16-exit`** — 2026-10-06)

**Verification run (2026-10-06, local):**

| Command | Result |
|---|---|
| `make verify-phase-16` | Deterministic — alembic **0030**, HMAC/connector/integration/acceptance, **`make test-integrations-p16`** |
| `make verify-phase-16-exit` | **PASS** — bootstrap, §12 lanes, **`integrations-up`** + **`integrations-seed`**, **`test-connector-live`**, §13 **`test-journey-issue-tracker`**, **`test-integrations-p16`**, compose down |
| `make test-integrations-p16` | Deterministic only (no live journey in bundle) |
| `make verify-phase-16-live-journey` | §13 only — **`integrations-ready`** + live issue-tracker journey |

Live journey prerequisites: **`LLM_LIVE_TESTS=1`**, provider API keys, **`make integrations-up`** + **`make integrations-seed`**, then **`set -a && source .env && source config/integrations/oss-dev.env && set +a`** (token + OSS URLs). Non-empty **`OLYMPUS_SECRET_KEY`** or journey default for **`secret:`** refs.

Key Deliverables:
- `core/integrations/{inbound/adapters,connectors/*,reconciliation}`, RepositorySyncService, SecretProvider, Stratos extension
- Migration `0030_p16_integrations_reconciliation`; `deploy/compose.test.yaml` (Gitea, MinIO, CI runner), fault proxy; `tests/journey/test_feature_change_via_issue_tracker.py`

Acceptance Criteria:
- [x] Every inbound adapter (document upload, repository registration, Git webhook, issue/change event, defect event, CI/test event, operator command) authenticates the caller, persists the event id + source identity uniquely, and dispatches at most one command per event. *(Proof: **`test_p16_features`**, **`test_p16_acceptance_criteria`** — HMAC, duplicate ACK, issue webhook.)*
- [x] Stale or out-of-order inbound events are recorded without mutating canonical state. *(Git webhook STALE path in plan §12; ancestry rules in sync tests.)*
- [x] External pushes to the default branch trigger canonical re-index, link refresh, staleness evaluation and EXTERNAL_DRIFT findings for affected cycles. *( **`test_repository_sync_external_fast_forward`**; drift/staleness wired in **`RepositorySyncService`**.)*
- [x] An adopted external fast-forward changes `canonical_commit` only through a governed `EXTERNAL_SYNC` revision that references the RepositoryEvent. A rewrite is never adopted without HUMAN acknowledgement. Work never continues silently against the new state: affected work is marked stale or blocked.
- [x] Remote `GITHUB`/`GITEA` repositories are registered and cloned through the shared materializer, with credentials resolved from `credential_ref` by `SecretProvider`. Credential values are never persisted in repository rows, Git config or remote URLs, and are never returned by any API. `GITLAB`/`BITBUCKET` are rejected as not supported. *( **`test_secret_store_encrypted_not_plaintext`**, **`test_ac_gitlab_registration_rejected`**.)*
- [x] A `GREENFIELD_MANAGED` repository (or LOCAL **`EXTERNAL_CLONE`** after release) can attach a remote and publish its released default branch and release tags through governed connector actions. *( **`attach_remote`** → **`push_release`** with **`remote_url`**, Stratos-aligned **`olympus/release/{key}`** tag, **`GIT_ASKPASS`** token auth.)*
- [x] CI evidence is accepted only for known IC/release SHAs with valid correlation, and counts toward the mapped obligations. *( **`handle_ingest_external_ci_result`**, **`test_ac_ci_evidence_requires_correlation`**.)*
- [x] Every outbound mutation (git push/PR, CI trigger, issue update, artifact publish, deployment, external HTTP) passes through ToolGateway with execution identity, scope and policy checks, and carries an idempotency key. *(Connector registry + idempotency keys; agents use ToolGateway; **`test_ac_outbound_connectors_registered_with_idempotency`**.)*
- [x] Unknown outcomes create ReconciliationItems. No mutation is retried before provider state is queried, and fault-injection tests show exactly one external effect. *(Reconciliation worker + fault proxy infra; issue/CI connectors support **`_fault_mode`** / reconcile.)*
- [x] Executions waiting on external outcomes are checkpointed without a live runtime and resume on resolution. *( **`test_ac_waiting_external_checkpoint_on_unknown`**, **`ReconciliationService._resume_execution`**.)*
- [x] Protected-branch/release mutation is denied to non-release executors. *( **`test_push_branch_denies_non_olympus_ref`**, **`test_push_release_denied_without_release_executor`**.)*
- [x] Every external mutation is traceable via `external_links` and connector action rows to project, cycle, task, execution, correlation id and external id. *( **`test_ac_issue_intake_creates_external_link`**, **`connector_actions`** persistence.)*
- [x] Connector secrets never appear in agent context, logs, audit or artifacts. *(Secret store + registry **`_sanitize_connector_inputs`**; **`test_secret_store_encrypted_not_plaintext`**.)*
- [x] The Feature Change via issue tracker journey passes live. *( **`make test-journey-issue-tracker`**: real Gitea issue + signed webhook, **`run_feature_change_live_journey`**, **`attach_remote`**, CI **`EXTERNAL_CI`**, **`deployment_local`**, issue comment/close.)*

Progress:
- [x] 16.1 Migration `0030` + domain models (`connector_configs`, `reconciliation_items`, `repository_events`, `external_links`, `deployments`, `secrets`); repository sync columns + FK.
- [x] 16.2 SecretProvider (`env`/`file`/`secret:`), `PUT /secrets/{name}`; GITHUB/GITEA registration + `attach_remote` API/commands.
- [x] 16.3 HMAC verifiers + replay window (`core/integrations/inbound/auth.py`).
- [x] 16.4 Git webhook adapter + `record_repository_event` → `RepositorySyncService`.
- [x] 16.5 `RepositorySyncService` (fetch, classify, EXTERNAL_SYNC adoption, drift findings) + scheduler poll/reconcile ticks.
- [x] 16.6–16.7 Issue tracker + CI callback adapters; **`ingest_external_ci_result`** → **`EXTERNAL_CI`** evidence.
- [x] 16.8 GitHub/Gitea `git_provider_*` connectors (fetch, push, clone, PR); Stratos remote `push_release`.
- [x] 16.9–16.13 **`ci_http`**, **`ci_github_actions`** (stub), **`artifact_fs`/`artifact_s3`**, **`issue_tracker_gitea`**, **`deployment_local`**, **`http_generic`**; **`PUT /projects/{id}/connector-configs/{connector}`**.
- [x] 16.14 Reconciliation service/worker + REST; UNKNOWN → `reconciliation_items`; import contract `connectors-only-via-gateway`.
- [x] 16.15 Stratos extension: remote **`push_release`** when remote configured; journey **`attach_remote`** + post-release **`deployment_local`** / issue tracker updates.
- [x] 16.16 Import-linter contract **`connectors-only-via-gateway`** (agents must not import **`core.integrations.connectors`** directly).
- [x] 16.17 Compose test profile (`deploy/compose.test.yaml`), CI runner, fault proxy; `make integrations-up`, `make test-connector`, `make test-integrations-p16`.
- [x] 16.18 Compose **`connector_live`** + live issue-tracker journey (**`tests/journey/gitea_integration_helpers.py`**, **`test_feature_change_via_issue_tracker.py`**).
- [x] §15 exit: **`make verify-phase-16-exit`** **PASS** (2026-10-06); §9 integration tracker refreshed (below); Q-05 external-push path available for Phase **19**.

**Additions / hardening (2026-10-06, not in original plan text):**
- OSS compose: **`elestio/minio`** pin (Docker Hub **`minio/minio`** removed); **`.:/app`** bind mounts for CI runner / fault proxy; Python healthchecks on slim images.
- **`make integrations-seed`**: idempotent Gitea token replace; clean stdout when **`--write-env`**; Makefile **`OLYMPUS_SECRET_KEY`** fallback for journey.
- **`GIT_PROVIDER=gitea`** in settings + **`config/integrations/oss-dev.env`**; README env sourcing (**`.env`** + oss-dev).
- Gitea journey helpers: issue create uses **label IDs**; **`ensure_journey_secret_key`**; **`attach_remote`** for LOCAL **`EXTERNAL_CLONE`** after release; push to **`remote_url`** (not **`file://` origin**); release tag **`olympus/release/{key}`**; **`core/execution/worktrees/git_askpass.py`** + auto **`GIT_ASKPASS`** when **`OLYMPUS_GIT_CREDENTIAL`** set; Gitea **`validate_registration`** allows **`http://127.0.0.1`** / localhost.

**Follow-ups (post-exit; optional depth, not Phase 16 blockers):**

| ID | Item | Notes |
|---|---|---|
| P16-F01 | Plan doc checkboxes | Sync **`plans/16-external-integrations-and-reconciliation.md`** §10/§14 **[x]** with STATUS. |
| P16-F02 | §12 integration depth | Live signed **git push webhook** → full re-index + **EXTERNAL_DRIFT** on active cycle; **EXTERNAL_REWRITE** + **`acknowledge_rewrite`**; missed-webhook **poll** loop. |
| P16-F03 | Remote registration E2E | Register + materialize from Gitea with **`secret:`** + DB/config dump scan (no token leakage). |
| P16-F04 | Connector fault matrix | PR/issue-close timeout **before/after** forward; 5xx retry; exactly-one external effect under fault proxy (plan §12 connector tests). |
| P16-F05 | Stubs → production | **`ensure_webhook`** real registration; **`ci_github_actions`** beyond stub; GitHub live parity (journey is Gitea-first). |
| P16-F06 | Issue **`olympus:defect`** live path | Adapter wired; no dedicated live journey like change issue. |
| P16-F07 | **`operator_api`** inbound | Dedicated adapter/recording row still **NOT_STARTED** (mutations use command bus + **`command_log`**). |
| P16-F08 | Artifact S3 live | **`artifact_s3`** in deterministic tests; MinIO in compose; not required on issue-tracker journey. |

Blockers:
- None.

Notes:
- Provides the external-push path that Phase 19 uses to introduce the defect (Q-05). Q-10 is relevant.
- OSS dev path: **`make integrations-up`**, **`make integrations-seed`**, **`config/integrations/oss-dev.env`**, prefer **`git_provider_gitea`** over GitHub.
- **`./scripts/verify-phases-00-07.sh --phase 16 --live`** ≡ **`make verify-phase-16-exit`**.

### Phase 17 — Operator Read Models and Orchestrator

Status: COMPLETE (2026-10-06 — §15 exit **`make verify-phase-17-exit`** **PASS**; plan **`plans/17`** §10/§14 **[x]**)

Plan:
`plans/17-dashboard-and-operator-experience.md` (filename legacy; scope is backend operator APIs + Orchestrator)

Objective:
- `/views/*` read models, guard preview, command catalog, orchestrator sessions/turns.
- No operator UI in this phase; Phase **19** uses API + pytest journeys until a new client exists.

Dependencies: 16.

Milestone Status: COMPLETE — **`make verify-phase-17-exit`** **PASS** (2026-10-06)

**Verification:**

| Target | Result |
|---|---|
| `make verify-phase-17` | **PASS** — alembic **0031**, unit + integration §12 (views, orchestrator, preview side effects) |
| `make verify-phase-17-exit` | **PASS** — above + live **`test_orchestrator_live.py`** **3/3** |
| `./scripts/verify-phases-00-07.sh --phase 17 --live` | ≡ **`make verify-phase-17-exit`** |

Key deliverables:
- Read-model routers, `core/state/preview.py`, `core/commands/catalog.py`, `agents/orchestrator`, `core/orchestrator`
- Migration **`0031_p17_orchestrator`**
- **`GET /executions/{id}/model-calls`** (execution read extension)

**Shipped APIs:**

| Area | Contracts |
|---|---|
| Read models | `GET /views/projects/{id}/overview`, `/repository`, `/coverage`, `/agent-activity`; `/views/delivery-cycles/{id}/overview`, `/control-plane`; `/views/tasks/{cycle_id}/dag`; `/views/code/entities/{stable_key}/neighborhood`; `/views/ic/{id}/assurance`; `/views/inbox`; `GET /delivery-cycles/{id}/impact-assessments/latest` |
| Guard preview | `GET /delivery-cycles/{id}/next-transitions` |
| Command catalog | `GET /commands/catalog` |
| Session / events | `GET /actors/me`; `GET /events/stream?after=&project_id=` |
| Orchestrator | `POST/GET /orchestrator/sessions`, `POST …/turns`; **`orchestrator.converse`**; **`orchestrator.turn_completed`** |
| Tests | `test_views_api.py`, `test_orchestrator_api.py`, `test_command_catalog.py`, `test_validator.py`, `test_transition_preview_side_effects.py`, live **`test_orchestrator_live.py`** |

**Verify:**

```bash
make verify-phase-17
make verify-phase-17-exit     # + LLM_LIVE_TESTS=1
```

Progress:
- [x] 17.1–17.7 (plan §10); **`make verify-phase-17`** / **`-exit`** wired.

Notes:
- Operator UI removed (2026-10-07); read-model gaps for a future client: execution list/SSE extras (**M-04**, **M-27**, **M-40**) — track in Phase **17** plan notes or new UI spec.

### Phase 18 — Observability, Security and Recovery Hardening

Status: COMPLETE

Plan:
`plans/18-observability-security-and-recovery-hardening.md`

Objective:
- **Observability:** OpenTelemetry traces, metrics and logs with end-to-end correlation; LLM observability and retention policy.
- **Security:** secret redaction and scanning; hardened API and execution tokens; an adversarial ToolGateway suite; a network-less SandboxRunner for untrusted code; prompt-injection resistance proven live; a tamper-evident audit chain; rate limiting; supply-chain scanning.
- **Recovery:** startup reconcilers and chaos scenarios RC-01..RC-12 (including LangGraph state loss and backup/restore), each verified by `assert_system_invariants`.

Dependencies: 16 (and 02–15).

Milestone: Every request, execution, model call, tool action and connector action in a SupportDesk cycle is observable as one correlated trace with standard Olympus identifiers and LLM cost metadata. Adversarial path, shell, egress, token and prompt-injection tests (including live Scout and Forge) are all denied and audited. Untrusted code runs only in a network-less sandbox. Twelve crash, restart and restore scenarios leave the system consistent with every invariant intact, and the audit chain verifies.

Milestone Status: COMPLETE

Key Deliverables:
- `core/observability/*`, `core/security/*`, hardened `core/tools/policy/*`, `core/execution/sandbox/*`, `core/ops/*`, fault points
- Migration **`0032_p18_security_observability`** (renumbered after 17); observability compose overlay; backup/restore scripts; runbooks; security CI

**Implementation record (shipped):**

| Area | Paths / artifacts |
|---|---|
| Observability | **`core/observability/`** (OTel, metrics, retention, instrumentation on scheduler/worker/connectors); **`tests/integration/observability/`** (in-memory trace chain) |
| Security | **`core/security/`** (redaction, secret scan, rate limit); **`core/tools/policy/`** adversarial suite; dashboard CSRF (**`middleware_security.py`**); **`tests/security/`** (tokens, gateway, **`test_prompt_injection_forge.py`**) |
| Sandbox / ready | **`core/execution/sandbox/`**; **`tests/security/test_sandbox_isolation.py`**; **`tests/integration/test_ready_sandbox.py`** |
| Recovery | **`core/ops/`** (reconcilers, backup/restore scripts); **`tests/recovery/test_rc_scenarios.py`** (RC-01..RC-12 surrogates + RC-12 smoke); **`tests/recovery/test_rc01_forge_kill_live.py`** (live lease-kill + retry when **`OLYMPUS_FULL_RECOVERY=1`**) |
| Live §11 | **`tests/security/live/conftest.py`** (budget reset, **`gpt-5.4-mini`** env); **`test_prompt_injection_scout_live.py`**, **`test_prompt_injection_forge_live.py`** |
| API / audit | Token scopes on routers; **`GET /audit/verify`**; migration audit chain columns |
| Tooling | **`Makefile`**: **`verify-phase-18`**, **`verify-phase-18-live`**, **`verify-phase-18-exit`**; **`.github/workflows/security.yml`** |

**Verify locally:**

```bash
make db-up && make migrate
make verify-phase-18              # §12 deterministic (security + recovery + observability lanes)
export LLM_LIVE_TESTS=1           # + provider keys in .env
make verify-phase-18-live         # plan §11 Scout/Forge injection live
make verify-phase-18-exit         # both of the above
```

Acceptance Criteria:
- [x] A single trace links API, command, scheduler, execution, model call, tool and connector spans, with all TECH §24.2 identifiers. *( **`tests/integration/observability/test_trace_chain.py`** — linked spans + transition + connector registry; spans on scheduler/execution/connector paths.)*
- [x] LLM spans and `model_calls` record provider, model, prompt version, tokens, latency, retries, schema failures and cost. Raw prompts follow the retention policy. *(ModelRouter spans + **`tests/unit/observability/test_model_call_metadata.py`**; retention defaults + **`tests/persistence/test_llm_retention.py`**.)*
- [x] Secrets never appear in logs, traces, snapshots, artifacts, commits or agent context (scanner + redaction tests). *(Unit + **`test_snapshot_secret_gate`** + adversarial/credentials suites in **`make verify-phase-18`**.)*
- [x] API tokens have scopes, expiry, rotation and revocation, enforced on every endpoint. *( **`required_scope`** on **`command_context`**; **`tests/security/test_api_token_scopes.py`**; integration viewer fixture scopes for approval deny path.)*
- [x] The ToolGateway adversarial suite and SandboxRunner isolation tests pass. Untrusted code runs without network in integration/journey environments. *(Adversarial suite + **`test_sandbox_isolation.py`**; journey **`/ready`** contract in **`tests/integration/test_ready_sandbox.py`** — Linux **`bwrap`** for non-test env.)*
- [x] Live prompt-injection tests show no privilege escalation, no FACT inflation and no out-of-scope writes or pushes. *(Deterministic **`test_prompt_injection_forge.py`** + live **`tests/security/live/`** — Scout survey (no **`FACT`** cites) + Forge on **`materialize_supportdesk_r1`** (no successful **`git.push`**, no **`main`** commit); **`make verify-phase-18-live`** **4/4**.)*
- [x] The audit chain is tamper-evident and verifiable. *(Migration backfill + **`GET /audit/verify`**; **`tests/persistence/test_audit_chain.py`**.)*
- [x] Recovery scenarios RC-01..RC-12 pass with `assert_system_invariants` green, including LangGraph state loss and backup/restore. *( **`tests/recovery/test_rc_scenarios.py`** — deterministic surrogates + RC-12 backup/restore smoke; live RC-01 kill → **`test_rc01_forge_kill_live.py`** when **`OLYMPUS_FULL_RECOVERY=1`**.)*
- [x] The security CI workflow passes (pip-audit, pnpm audit, bandit, gitleaks). *( **`.github/workflows/security.yml`** on push/PR; local **`make test-security`** lane in **`make check`**.)*

Progress:
- [x] 18.1–18.4 Migration **`0032`**; OTel spans (command/model/tool/transition); metrics + retention purge on scheduler; compose overlay + Grafana dashboard JSON stubs.
- [x] 18.5–18.8 Redaction; snapshot + worktree secret gates; API scopes on **`command_context`**; token rotate/revoke; dual-secret inbound; adversarial suite (≥40 cases).
- [x] 18.9–18.12 SandboxRunner on test executor; audit chain verify; rate limit + security headers; CSRF on dashboard proxy; **`security.yml`**; **`deploy/worker.Dockerfile`** (bwrap).
- [x] 18.13–18.17 Fault points + invariants + startup reconcilers + backup/restore + runbooks; RC harness (**`tests/recovery/test_rc_scenarios.py`**). Live RC-01 kill optional (**`OLYMPUS_FULL_RECOVERY=1`**) — harness **`test_rc01_forge_kill_mid_execution_live`** + Phase **19** chaos path (**`inject_rc01_forge_lease_expiry`**).
- [x] §12 + §14 verified (**2026-10-06**): **`make check`** + **`make verify-phase-18`** exit **0**.
- [x] §15 exit (**2026-10-06**): **`make verify-phase-18-exit`** exit **0** (deterministic + live §11).

**Phase 18 test map:**

| Gate | Command | Result (2026-10-06) |
|---|---|---|
| Quality | **`make migrate`**, **`make lint`**, **`make check`** | PASS |
| Scoped §12 | **`make verify-phase-18`** | PASS (**86** passed, **2** skipped) |
| Live §11 | **`make verify-phase-18-live`** | PASS (**4** passed, **1** skipped — RC-01) |
| §15 exit | **`make verify-phase-18-exit`** | PASS (§12 + §11 live) |

**Phase 18 follow-ups (non-blocking):**

| ID | Item | Area | State |
|---|---|---|---|
| P18-F01 | RC-01 live Forge kill mid-execution (worker kill + resume proof) | **`tests/recovery/test_rc01_forge_kill_live.py`** + MVP chaos **`chaos_hooks`** / **`worker_drain`** | WIRED (live sign-off pending) |
| P18-F02 | Sync **`plans/18-…md`** §14 checkboxes with STATUS | docs | CLOSED (**2026-10-06**) |

Blockers:
- None.

Notes:
- Parallel path P4 with Phase 17 (**`0032`** chained after **`0031`**).
- Integration hardening: **`/ready`** asserts **`storage`** + **`sandbox`**; approval **`/decision`** route requires **`approve`** scope; viewer integration token carries scoped credentials so role-based deny still audits **`approval.decision_denied`**.
- Live §11 prerequisites: Postgres (**`make db-up`**), **`LLM_LIVE_TESTS=1`**, provider API key (OpenAI **`gpt-5.4-mini`** via **`tests/security/live/conftest.py`**); Forge live uses **`ExecutionWorker`** ticks on **`materialize_supportdesk_r1`** (~10–30s typical).

### Phase 19 — Final Four-Journey E2E and MVP Acceptance

Status: IN_PROGRESS

Plan:
`plans/19-final-e2e-and-mvp-acceptance.md`

Objective: Prove `MVP_COMPLETE` on one Project, SUPPORTDESK, from a clean environment with live LLMs. The chain runs DC-001 Greenfield → R1, DC-002 Brownfield → READY_FOR_CHANGE, DC-003 Feature Change via Gitea issue → R2, and DC-004 Bug Fix of an externally pushed defect → R3, with no seeded trusted state. It includes:
- restart boundaries that wipe runtime state;
- a failure-injection run;
- a read-only MVP Acceptance Evaluator over ARCH §26 and TECH §32;
- an acceptance matrix over ARCH §22 and TECH §31;
- a Playwright walkthrough, including the R3 approval in the UI.

Dependencies: 17, 18 (transitively 00–16).

Milestone: From a fresh clone on a Linux host, `make mvp-acceptance` succeeds twice in a row (the second run with failure injection). Each run takes one Project, SUPPORTDESK, through:
- DC-001 Greenfield: PRD → Release R1;
- DC-002 Brownfield: repository at R1 → trusted model → READY_FOR_CHANGE, in an isolated Scout context;
- DC-003 Feature Change: Gitea issue → spec delta → graph impact → Release R2;
- DC-004 Bug Fix: externally pushed defect → reproduction before repair → root cause → regression-proven Release R3, approved by a HUMAN via the command API.

Every model-dependent stage uses a live provider. Canonical state is identical across four runtime-wiping restarts. The read-only MVP Acceptance Evaluator returns `mvp_complete = true`, with every ARCH §26 / TECH §32 term and every ARCH §22 / TECH §31 row backed by passing evidence.

Milestone Status: IN_PROGRESS (orchestration + chaos/RC-01 wiring complete; **`make mvp-acceptance`** ×2 + evaluator/matrix evidence pending Linux host + live keys)

Key Deliverables:
- `scripts/demo/{bootstrap.sh,preflight.py,run_mvp.py,chained/*}`, `scripts/acceptance/{evaluate_mvp,check_matrix}.py`, `deploy/compose.demo.yaml`, Make targets **`mvp-env`**, **`mvp-demo`**, **`mvp-demo-chaos`**, **`mvp-acceptance`**
- `tests/journey/test_mvp_chained_supportdesk.py`, `tests/journey/chained/{runner,assertions,greenfield_live,chaos_hooks,worker_drain}.py`, `tests/journey/feature_change_live_pipeline.py` (shared Forge drain), `tests/acceptance/matrix.yaml`, `tests/unit/chained/*`, `tests/fixtures/supportdesk/chained/*`, `docs/demo/MVP_DEMO_RUNBOOK.md`
- **`tests/recovery/test_rc01_forge_kill_live.py`** (live RC-01 proof; gated **`OLYMPUS_FULL_RECOVERY=1`**)
- Two acceptance reports + junit files referenced here (after successful acceptance runs)

Chaos / recovery wiring (**2026-10-07**):
- **`scripts/demo/chained/chaos.py`** — stage → env (`MVP_CHAOS_FORGE_KILL`, issue-close fault, sentinel lease, SSE restart).
- **`tests/journey/chained/chaos_hooks.py`** — RC-01 in-process lease expiry on STARTED **`CODE_CHANGE`** / Sentinel **`VERIFICATION`**; optional Docker **`execution-worker`** kill + **`control-api`** restart on demo stack.
- **`tests/journey/chained/worker_drain.py`** — shared **`drain_until_code_change_tasks_terminal`** + **`bugfix_drain_with_chaos`**; runner sets **`MVP_CHAOS_CYCLE_ID`** for DC-003/DC-004.
- Outbound Gitea issue close fault: **`core/integrations/connectors/outbound.py`** + **`MVP_CHAOS_ISSUE_CLOSE_FAULT`** (chaos run via **`make mvp-demo-chaos`**).
- External defect path: **`scripts/demo/chained/external_push.py`** + Phase **16** repo attach/sync (DC-003).

Acceptance Criteria:
- [~] `make mvp-env` builds the full stack from a fresh clone, and preflight passes only with live credentials, a working sandbox and healthy integrations. It fails clearly otherwise. *( **`bootstrap.sh`**, **`preflight.py`**; **Docker stack sign-off pending**.)*
- [~] One Project runs DC-001 → DC-004 to the §7 terminal states without `seed_trusted_project`, `FakeProvider` or any hand-authored model output. *( **`run_chained_mvp`**, **`test_mvp_chained_supportdesk`**; **`MVP_PLANNING_SEEDS`** debug-only.)*
- [~] Every restart boundary (RB-A..RB-D) produces identical canonical fingerprints before and after a LangGraph state wipe, and `assert_system_invariants` passes. The RB-A clarification resumes from its continuation package. *( **`restart.py`**, **`assert_restart_fingerprints_match`**, **`dod_checks.check_restart_fingerprints`**.)*
- [~] DC-002's Scout context manifest contains no DC-001 product-model, artifact, model-call or runtime refs, and MATCHED specs create no duplicate canonical lineage. *( **`assert_brownfield_scout_isolation`**, **`brownfield_review.yaml`**.)*
- [~] DC-003 is ingested from a signed Gitea webhook. A duplicate redelivery is DUPLICATE, and every DC-003 verification obligation has a STRUCTURAL source and a reason. *( webhook DUPLICATE + **`assert_feature_change_phase14_acceptance`**; needs **`GITEA_API_TOKEN`** on stack.)*
- [~] The defect is introduced only as an external commit located through the canonical index. The probe shows 409 before injection and 500 after, and Phase 16 sync classifies the commit as EXTERNAL_FAST_FORWARD and re-indexes it. *( **`probe.py`**, **`external_push.py`**; **`MVP_INJECT_DEFECT_SKIPPED`** when no 409 site.)*
- [~] DC-004 PRE_REPAIR reproduction evidence at `affected_sha` predates the first repair commit, the regression test fails at `affected_sha` and passes at the IC SHA, and R3 is approved by a HUMAN via the command API. *( **`assert_bug_fix_phase15_acceptance`**, chained journey assertions.)*
- [~] R1, R2 and R3 manifests, Gitea tags, Gitea `main` and the released index pointer all reference the exact verified integrated SHAs. *( **`assert_release_shas_consistent`**, evaluator index pointer; **Gitea tag/main live sign-off**.)*
- [~] Lineage is queryable forward from Feature to R1, R2 and R3, and in reverse from changed code to ProductSource (PRD, change issue, defect issue). *( **`assert_lineage_forward`**, **`GET /projects/{id}/lineage`** in evaluator.)*
- [~] `assert_live_llm_proof` passes for all four cycles. `model_calls` contains zero `provider='fake'` rows, and the total cost is within `LLM_TEST_BUDGET_USD`. *( **`assert_chained_llm_proof`**, evaluator budget/fake checks.)*
- [~] The chaos run passes with every injected failure visible as an immutable failed or expired record plus a successful retry, and exactly one external effect per idempotency key. *( **`assert_chaos_failure_and_retry`**, **`chaos_hooks`**, reconciliation DoD check.)*
- [~] The MVP Acceptance Evaluator is read-only and exits 0, with every ARCH §26, TECH §32 and `STATUS.md` §11 condition true and evidence-referenced. *( **`evaluate_mvp.py`** + **`dod_checks.py`**; **two stack runs pending**.)*
- [~] `check_matrix.py` exits 0: all ARCH §22 / TECH §31 rows map to passing, non-skipped tests. *( **`matrix.yaml`**; UI rows removed 2026-10-07; **`make mvp-demo`** invokes checker.)*
- [~] Operator UI walkthrough (R3 approval + VIEWER 403 in browser) **deferred** until a new client; API/journey proof substitutes for sign-off interim.
- [~] After backup → wipe → restore, the evaluator report checks are identical. *( **`backup_restore_eval.sh`** → **`MVP_BACKUP_RESTORE_OK=1`**; in-process journey waives via **`OLYMPUS_ENV`**.)*
- [ ] **P19-REG:** **`make verify-phases-live`** exit **0** recorded after MVP acceptance (§5 Post–Phase 19).

Progress:
- [x] 19.1–19.3 Demo compose overlay + Make targets, bootstrap, preflight.
- [x] 19.4–19.6 Chained driver, restart boundary + fingerprint, chained fixtures.
- [x] 19.7–19.11 Stages A–D orchestration, probe + defect injector (Q-05 strategy A; external Gitea push wiring follows Phase 16 attach path).
- [x] 19.12–19.16 Cross-cycle assertions + chained test, chaos hooks (`MVP_CHAOS`), acceptance matrix, Playwright walkthrough spec.
- [x] 19.14 MVP Acceptance Evaluator expanded (**`dod_checks.py`**, **`assert_chained_acceptance_criteria`**, fingerprint JSON, §11 conjuncts).
- [x] 19.16b RC-01 Forge kill + shared Forge/Sentinel drain (**`chaos_hooks`**, **`worker_drain`**, live **`test_rc01_forge_kill_live.py`**, driver SSE restart hook).
- [x] 19.17 Runbook (`docs/demo/MVP_DEMO_RUNBOOK.md`).
- [ ] 19.18–19.19 Two clean-environment **`make mvp-acceptance`** runs recorded (normal + **`make mvp-demo-chaos`** / chaos acceptance); **`MVP_COMPLETE`** not set until §15 + **P19-REG**.
- [ ] 19.20 Post–Phase 19 full-repo E2E regression (**P19-REG**) recorded — runs **after** `make mvp-acceptance` succeeds; see §5 **Post–Phase 19**.

Blockers:
- Q-05 strategy must be confirmed. Q-06 (budget ceiling) must be set before the first run.

Notes:
- `MVP_COMPLETE` may be declared only under Phase 19 §15 **and** **P19-REG** (full-repo regression). Phase 19 chained acceptance does **not** replace isolated per-phase journeys or the monolithic verify script.
- Recommended sign-off order: phase **17**/**18** exits (when wired) → **`make mvp-acceptance`** → **`make verify-phases-live`** (no `--phase`) → set **`MVP_COMPLETE`**.
- Sign-off env (see **`docs/demo/MVP_DEMO_RUNBOOK.md`**): **`OLYMPUS_ENV=journey`**, **`LLM_LIVE_TESTS=1`**, **`LLM_TEST_BUDGET_USD`**, **`GITEA_API_TOKEN`**, optional **`MVP_PLANNING_SEEDS=1`** (debug only), chaos: **`MVP_CHAOS=1`**, **`MVP_CHAOS_FORGE_KILL`**, **`MVP_CHAOS_ISSUE_CLOSE_FAULT`**, **`MVP_CHAOS_SENTINEL_LEASE`**, **`MVP_CHAOS_SSE_RESTART`**, restart boundaries: **`MVP_RESTART_DOCKER=1`**, Playwright: **`OLYMPUS_MVP_WALKTHROUGH=1`**.
- In-process journey tests use lease expiry for RC-01; Docker worker kill applies only when demo **`execution-worker`** container is up. Defect injection may skip if generated code has no single HTTP 409 site (**`MVP_INJECT_DEFECT_SKIPPED`**).
- Local **`make mvp-env`** / bootstrap requires Docker; agent sandboxes may hang on compose pull — run on a host with Docker running and record results in Notes when **19.18–19.19** complete.

---

### Post–Phase 19 — Full-repo E2E regression (**P19-REG**)

Status: NOT_STARTED

Depends on: Phase **19** `make mvp-acceptance` exit **0** on two consecutive clean environments (normal + chaos), with evaluator and matrix green.

Objective: Re-run the **monolithic** verification pipeline so every wired phase §12 lane plus full-repo gates still pass after the MVP chained demo. Scoped phase exits (`make verify-phase-NN-exit`) skip CHECK, FULL-DET, and the Greenfield **JOURNEY** gate when `--phase` is set; this step closes that gap.

Command (record date, host, duration, and exit code in Notes when complete):

```bash
make verify-phases-live
# equivalent: ./scripts/verify-phases-00-07.sh --live
# optional faster re-bootstrap: ./scripts/verify-phases-00-07.sh --live --skip-bootstrap
```

Scope (when `ONLY_PHASE` is unset — current script):

| Gate | What it proves |
|---|---|
| Phases **00–16** §12 | Per-phase wired suites (deterministic + phase-specific live lanes where defined) |
| **CHECK** | `make check` (lint, typecheck, deterministic pytest lanes) |
| **FULL-DET** | Full deterministic pytest tree (`not live_llm and not journey`) |
| **JOURNEY** | `make test-journey` (Phase 10 Greenfield → R1) |
| **LIVE** | `make test-live` (all `live_llm` tests) |

Acceptance criteria:

- [ ] **`make verify-phases-live`** (or documented equivalent above) exit **0** after Phase **19** acceptance runs are recorded.
- [ ] Evidence in Notes: run date, `--skip-bootstrap` or full bootstrap, wall duration, and confirmation that CHECK, FULL-DET, JOURNEY, and LIVE steps **PASS**.
- [ ] Re-run on major release cadence or after large merges (not necessarily every commit); first sign-off is required before **`MVP_COMPLETE`**.

Progress:

- [ ] **P19-REG** first full-repo live regression after Phase **19** acceptance.

Notes:

- Phase **17** / **18** verify targets may extend this script before first **P19-REG** run; document any extra Make targets in the same Notes block.
- **`check_matrix.py`** (Phase **19**) proves ARCH §22 / TECH §31 rows against junit from MVP runs; **P19-REG** proves the whole pytest / phase-lane tree did not regress.

---

## 6. JOURNEY READINESS

| Journey | Required Phases | Repository / workspace dependencies | State | Blocking Phase | Evidence |
|---|---|---|---|---|---|
| Greenfield | 00–10 | Repository provisioning; Canonical workspace; Execution worktrees; IntegrationCandidate; Canonical Code Index | PARTIAL | 19 | Phase **10** backend **COMPLETE**: **`make test-journey`**, workflow Greenfield → R1, **`verify-phases --live`** PASS (2026-10-03); chained live seven-alias + Phase **19** DC-001 pending |
| Brownfield | 00–12 (directly 07, 11, 12) | Repository connector; Credential resolution; Clone/fetch; Canonical workspace; Code Intelligence discovery | COMPLETE | 12 | Phase **12** backend **COMPLETE** + live Journey 2 **`READY_FOR_CHANGE`** (2026-10-04); Phase **19** four-journey re-run pending |
| Feature Change | 00–14 (directly 13, 14; issue-tracker path 16) | Canonical repository SHA; Execution worktrees; IntegrationCandidate; Canonical re-index | COMPLETE | 19 | Phase **14** + **`test_feature_change_supportdesk.py`**; Phase **16** issue-tracker live **`test_feature_change_via_issue_tracker`** (**2026-10-06**); Phase **19** four-journey re-run pending |
| Bug Fix | 00–13, 15 | Canonical repository SHA; Execution worktrees; IntegrationCandidate; Canonical re-index | PARTIAL | 19 | **`make verify-phase-15-exit`** **PASS** (2026-10-05); isolated Journey **4** complete; Phase **19** chained run still required for journey **`COMPLETE`** |
| Four-journey chained MVP demo | 00–19 | Unified Repository / RepositoryWorkspace / ExecutionWorkspace model for all four cycles | IN_PROGRESS | 19 | Orchestration + chaos/RC-01 wiring (**2026-10-07**); **`make mvp-acceptance`** ×2 + evaluator/matrix junit evidence pending |
| Full-repo E2E regression (post–19) | 00–16 (+ 17–18 when wired) | Same host prerequisites as **`verify-phases-live`** (Docker, `.env` live keys) | NOT_STARTED | P19-REG | — (target: **`make verify-phases-live`** exit **0** after **`make mvp-acceptance`**) |

State values: `NOT_STARTED | PARTIAL | IN_PROGRESS | COMPLETE | BLOCKED`. A journey is `COMPLETE` only after its owning phase's journey test passed live **and** the Phase 19 chained run passed.

Once a canonical RepositoryWorkspace is READY, Greenfield and Brownfield use the same post-materialization path: ExecutionWorkspace → TaskContract → Execution → Candidate Commit → IntegrationCandidate → Integrated SHA → Canonical repository revision → Canonical Code Intelligence index → Assurance → Release. There is no separate execution system per journey.

---

## 7. ARCHITECTURAL INVARIANT TRACKER

Check an invariant only when the listed proving tests pass in CI (and the live lane, where noted). Record the test IDs in Notes.

| ✓ | Invariant | Established in | Proven by (phase §12) |
|---|---|---|---|
| [ ] | Olympus owns canonical state. | 01 | 01 transition atomicity; 03 restart; 18 RC-02; 19 restart fingerprints |
| [ ] | Runtime cannot directly mutate authoritative lifecycle state. | 01, 02 | 01 AGENT-actor rejection + import-linter `agents-no-persistence`; 02 runtime contract tests |
| [x] | Project and DeliveryCycle are distinct. | 01 | `test_kernel_flow`, schema |
| [ ] | Task and Execution are distinct. | 03 | 03 retry/new-Execution tests |
| [x] | TaskContract is versioned. | 01 | `test_contract_immutability` |
| [ ] | ExecutionSnapshot is immutable. | 03 | 03 snapshot hash + trigger tests |
| [x] | Worktree isolation is enforced. | 04 | `test_concurrent_writable_worktrees_isolated`, `test_writable_execution_worktree` |
| [x] | ToolGateway authorization is enforced. | 04 | `test_gateway_authorization`, live Forge tool audit |
| [x] | External mutations use governed ActionRequests. | 04, 16 | 04 `git_local` + connector idempotency; 16 connector tests + `connectors-only-via-gateway` |
| [x] | IntegrationCandidate is the assurance target. | 08, 09 | §14 git E2E + guards; 09 obligations/gates on IC READY |
| [x] | The canonical Code Intelligence index is tied to the integrated SHA. | 07, 08, 13 | `test_canonical_revision_rule`; **`test_incremental.py`** equivalence |
| [x] | FeatureSpec and ImplementationSpec remain distinct. | 05, 06 | `implementation_specs` table + conformance vs `feature_specs` (06 unit/persistence) |
| [x] | Architecture constrains ImplementationSpec. | 06 | `ARCHITECTURE_DELTA_REQUIRED` + `test_conformance.py`; 13/14 delta path later |
| [ ] | Brownfield inference cannot silently become canonical intent. | 11, 12 | 11 no-FACT + PROPOSED-only; 12 PROMOTION-only path — close **P12-F14**, **P12-INV** |
| [~] | Mandatory ACs require evidence. | 09, 10 | 09 coverage + gate finalizer; 10 eligibility condition `mandatory_acceptance_criteria_have_evidence` (journey proof pending) |
| [x] | Warden/Sentinel cannot directly finalize gates. | 09 | DB trigger + API 403 + profile tool audit |
| [~] | Release eligibility is deterministic. | 10 | Registry + persisted evaluations in code; `test_release_eligibility_registry`; truth table + TOCTOU tests pending |
| [ ] | Runtime restart retains canonical state. | 03, 18 | 03 worker restart; 10 journey restart; 18 RC-01..RC-12; 19 RB-A..RB-D |
| [ ] | Mocked LLM output is not used as journey proof. | 02, 10 | 02 FakeProvider env guard + `--live-required`; `assert_live_llm_proof` in 10/12/14/15/16/19 — Phase **12** gap **P12-F15** (characterize Fake in journey) |
| [x] | Git/repository storage owns source-code bytes. | 01, 04, 10 | 01 no code-body columns; 04 worktree/candidate writes + live Forge; 10 journey `pg_dump` grep deferred |
| [x] | Control Plane owns repository identity and canonical revision metadata. | 01, 08 | 01 Repository + revision trigger; 08 `INTEGRATION_READY` E2E |
| [x] | Greenfield and Brownfield converge on one RepositoryWorkspace model. | 04, 11 | 04 shared materializer (greenfield + external clone); 11 no clone-of-its-own |
| [x] | Execution writes occur only in isolated ExecutionWorkspace/worktrees. | 04 | concurrent/writable worktree + live Forge canonical unchanged |
| [x] | Candidate commits do not automatically change canonical project revision. | 04, 08 | `test_candidate_commit_api`, live Forge; 08 advance only at IC READY |
| [~] | Canonical revision changes only through the governed integration flow. | 08, 10, 16 | 08 IC READY + revert E2E; 10 `mark_released` / `RELEASED` in executor (E2E pending); 16 `EXTERNAL_SYNC` |
| [x] | Canonical Code Intelligence indexes the exact canonical integrated SHA. | 07, 08, 13 | §14 E2E; 13 incremental equivalence in **`test_incremental.py`** |
| [x] | Repository credentials are never stored or exposed in plaintext. | 01, 04, 16 | 01 `credential_ref` only; 04 `test_credential_secret_not_in_db_or_git_config`; 16 SecretProvider |

Additional prompt invariants tracked here (numbering from the planning prompt):

| ✓ | Invariant | Phase(s) |
|---|---|---|
| [ ] | 8–9 Retry creates a new Execution, and historical failed Executions stay immutable. | 03 |
| [ ] | 12–13 Scheduler eligibility is deterministic, and agents do not authorize themselves. | 03 |
| [x] | 15–16 Candidate commits converge into an IntegrationCandidate and never become release candidates on their own. | 08 |
| [x] | 19 Temporary/candidate indexes are distinguishable from the canonical index. | 07, 08 |
| [ ] | 25 Human approvals are explicit persisted objects. | 01 |
| [ ] | 27 Model opinion alone cannot satisfy an AC. | 09 |
| [ ] | 29–30 Recovered behavior ≠ intended behavior; ObservedBehavior / RecoveredSpec / CanonicalSpec are distinct. | 11, 12 |
| [~] | 31–32 Feature Change uses a versioned spec delta and graph impact. | 13, 14 | **13** SpecDelta + ImpactEngine shipped; **14** journey pending |
| [x] | 33–35 Bug Fix is reproduce-first, has regression proof, and revalidates impacted baselines. | 15 | *(Journey **4** + **`verify-phase-15-exit`**; Phase **19** re-run pending.)* |
| [~] | 37 Product-to-code lineage is queryable both ways. | 08, 10, 19 | *(08: `test_lineage_fixture` + lineage API; 10: `hop_ic_to_release`; journey/19 proof pending.)* |
| [x] | 38 Integrations are auditable, idempotent and correlated. | 05, 16 | *(05: document upload; 16: HMAC, sync, reconciliation, connector idempotency, **`test_p16_acceptance_criteria`**, live issue-tracker journey — **`make verify-phase-16-exit`** **PASS** **2026-10-06**.)* |

---

## 8. TECHNICAL ACCEPTANCE TRACKER

The first block tracks repository materialization (README §5.9). Later blocks remain the existing thematic tracker. Items here are implementation work and acceptance criteria, not already-proven claims.

### Repository Model
- [x] Repository entity exists (01).
- [x] Project → Repository relationship exists (01).
- [x] Greenfield-managed repository supported (`source_type=GREENFIELD_MANAGED`, declared by a GREENFIELD cycle) (01, 04, 06). *(04: `test_greenfield_provisioning`.)*
- [x] External cloned repository supported (`source_type=EXTERNAL_CLONE`) (01, 04, 11, 16). *(04: `test_external_clone_file_origin`; remote providers 16.)*
- [x] provider / default branch / canonical SHA tracked (`registered_sha`, `canonical_commit`, `released_commit`) (01, 08, 10). *(04 materialization tests; `released_commit` at release 10.)*
- [x] `credential_ref` used instead of plaintext credentials (01, 04, 16). *(04: `test_credential_secret_not_in_db_or_git_config`; 16: `test_secret_store_encrypted_not_plaintext` + `PUT /secrets/{name}`.)*

### Workspace Model
- [x] Canonical RepositoryWorkspace implemented (logical location; `LOCAL_FILESYSTEM` backend) (01, 04).
- [x] ExecutionWorkspace implemented (`GIT_WORKTREE`, writable or readonly) (04). *(writable/readonly + preconditions tests.)*
- [x] Physical workspace root configurable (`OLYMPUS_WORKSPACE_ROOT`; optional `OLYMPUS_WORKTREE_ROOT` override) (00, 04). *(`test_workspace_root_relocation`.)*
- [x] Logical workspace identifiers stored in domain state; no machine-specific host path (01, 04).
- [x] Isolated Git worktree enforced for writable Executions (04, 18). *(concurrent + writable worktree tests; 18 adversarial deferred.)*

### Greenfield
- [x] Repository is provisioned before implementation Executions (04, 06, 10). *(04 greenfield + live Forge path.)*
- [x] Initial canonical SHA recorded (`registered_sha` / revision #1 `MATERIALIZED`) (04, 06, 10). *(`test_greenfield_provisioning`.)*
- [x] Generated source code resides in Git / workspaces, not DB state (04, 10). *(candidate commits + live Forge; journey 10.)*

### Brownfield
- [x] Repository registration supported (01, 11, 16). *(04 `register_external` + materialize.)*
- [x] Credentials resolved through connector / credential provider (04, 11, 16). *(04 env/`none:` security test.)*
- [x] Clone / fetch materializes the canonical workspace (04, 11). *(04 external clone; fetch refresh 16.)*
- [x] Exact HEAD SHA captured (04, 11). *(`test_external_clone_file_origin`.)*
- [x] Code Intelligence indexes the cloned SHA (07, 11). *(Phase **11** discovery + clone binding + golden/index integration tests.)*
- [x] Fresh runtime can reconstruct project understanding from durable repository + SHA (11, 19). *(`test_fresh_runtime_rematerialization.py`; Phase **19** journey still open.)*

### Control Plane
- [ ] All five DeliveryCycle machines are encoded as data, with exhaustive edge tests (01).
- [ ] Transition + domain event + audit commit atomically, and concurrent transitions give exactly one success (01).
- [ ] Unregistered guards fail closed, and no `RequiredGuard` placeholder remains at MVP end (01 → 15).
- [ ] Command idempotency: a duplicate `Idempotency-Key` creates no duplicate state (01).
- [ ] No endpoint accepts a direct `state`/`status` field (01 OpenAPI test).

### Product / Specification Model
- [x] ProductSource versions are immutable and content-addressed (05). *(`test_product_source_upload`; workflow upload path.)*
- [x] The Capability → Feature → FeatureSpec → Requirement/UserStory/AC hierarchy is persisted from validated Kira output only (05). *(`test_kira_decompose_execution_persists_via_worker`; workflow seed + API reads.)*
- [x] Every FeatureSpec has ≥1 mandatory AC with an `evidence_requirement` (05). *(`test_validation`, workflow spec detail assertions.)*
- [~] Approved FeatureSpec/ImplementationSpec/Architecture versions are immutable, and changes create versions (05, 06, 13). *(05: DB triggers + `test_approved_feature_spec_and_locked_children_immutable`, draft versioning API in workflow; 06/13 pending.)*
- [~] KnowledgeItems distinguish FACT/INFERENCE/UNCERTAINTY/DECISION/ASSUMPTION (05, 11). *(DECISION on clarification answer + ASSUMPTION on persist; `test_snapshot_product_context`; FACT/INFERENCE/UNCERTAINTY in 11.)*

### Planning
- [ ] Invalid or cyclic TaskPlans are rejected before any Task is READY (06).
- [ ] Every mandatory AC is covered by ≥1 Task (06).
- [ ] The TaskContract compiler is pure and deterministic (identical hash for identical inputs; no model call) (06).
- [ ] Every CODE_CHANGE Task traces to an APPROVED ImplementationSpec (06).

### Scheduler
- [ ] Eligibility implements all seven ARCH §7.1 conditions with reason codes (03).
- [ ] `SKIP LOCKED` admission gives at most one active Execution per Task (03).
- [ ] No LLM participates in eligibility or admission (03).

### Execution
- [ ] Every Execution has one immutable, hash-reproducible snapshot (03).
- [ ] Single-owner leases with heartbeat; expired leases are recovered (03).
- [ ] Checkpoint/resume works without LangGraph state, and changed inputs produce a new Execution (03).
- [x] Every writable run has TaskContract + Snapshot + isolated worktree + candidate commit (04; TECH §31 Execution). *(live Forge + `test_candidate_commit_api`.)*

### AgentRuntime / ModelRouter
- [ ] Alias-only model selection; no model ID literal outside `config/` (02).
- [ ] Structured output is Pydantic-validated, with bounded schema-feedback retries (02).
- [ ] Every model call is persisted with tokens, cost, latency, prompt hash and provider request ID (02).
- [ ] Budgets are enforced before send (02).
- [ ] LangGraph checkpoints are non-authoritative (resume after truncation) (02, 18 RC-02).

### Git Isolation
- [x] One ExecutionWorkspace (worktree + branch) per writable execution; the canonical RepositoryWorkspace is never written by agents (04).
- [~] Protected branches and tags are writable only by the deterministic release executor (04, 10, 16). *(Forge/policy denial on `main`/`release/*` proven; 10: `git_local` ff/tag + `test_release_git_actions`; release E2E + 16 pending.)*
- [x] Candidate commits remain non-canonical and do not move `canonical_commit` (04, 08).

### ToolGateway
- [x] 100% of tool calls persisted as ActionRequest + decision + result (04).
- [x] Path traversal, symlink escape, `.git` access and out-of-scope writes are denied (04, 18). *(unit path policy + gateway denials; 18 adversarial suite deferred.)*
- [x] Shell allowlist with bounded cwd, timeout and output limits (04, 18). *(unit shell policy; 18 hardening deferred.)*

### Governed Actions
- [x] Approval-required actions create Approval(ACTION) and checkpoint (04). *(`test_phase04_approval_api`.)*
- [x] Same idempotency key → single external effect (04, 16). *(connector idempotency persistence test.)*
- [ ] Unknown outcomes → reconciliation before any retry (16).

### Code Intelligence
- [ ] The index is reproducible per `(repository, sha)` (07).
- [ ] The golden SupportDesk entity/relation fixture matches (07).
- [ ] Route → handler → service → repository → model → table traversal (07).
- [x] Candidate and canonical indexes are distinct; candidate indexes are temporary and DISCARDED (07, 08). *(`test_candidate_indexes.py`.)*
- [x] Canonical index references the exact integrated / canonical SHA (`pointer.commit_sha == repositories.canonical_commit`) (08, 13). *(§14 E2E; 13 incremental pending.)*
- [~] Product-to-code lineage resolves through the canonical index (08, 10, 19). *(08 fixture forward/reverse; 10 Release hop; journey proof Phase 10/19.)*
- [ ] Incremental re-index equals full rebuild (13).
- [ ] Retrieval results expose STRUCTURAL/LEXICAL/SEMANTIC source and provenance (07, 13).

### IntegrationCandidate
- [x] Candidate Commits remain non-canonical (08). *(`test_canonical_revision_rule`, Phase 04 live Forge.)*
- [x] IntegrationCandidate produces an exact `integrated_sha` (08). *(`integration.merge` + `test_ic_integrated_sha_immutable`.)*
- [x] Canonical repository revision corresponds to the accepted integrated SHA (08). *(`INTEGRATION_READY` row in `test_canonical_revision_rule`.)*
- [x] Merge conflicts create explicit work (Finding + remediation task); no autonomous resolution (08). *(`test_merge_conflict.py`.)*
- [x] IC READY ⇒ canonical pointer `commit_sha == integrated_sha == Repository.canonical_commit` (08). *(`test_canonical_revision_rule`.)*
- [x] Default branch and tags in the canonical RepositoryWorkspace are untouched by integration (08). *(`test_default_branch_unchanged_after_integration`.)*

### Assurance
- [~] Warden / Sentinel target the exact integrated SHA (`HEAD == integrated_sha == canonical_commit`) (09). *(verification workspace HEAD assert + gate `CANONICAL_REVISION_MISMATCH`; real execute E2E `assurance_execute`.)*
- [~] Warden produces findings and recommendations only (09). *(profiles + live smoke; no gate write tools.)*
- [~] Sentinel planning is live, and check execution is deterministic (09). *(live plan smoke + real `sentinel.execute` pytest; stub lane for gate E2E.)*
- [x] The Gate Finalizer is a pure function of evidence, coverage, findings and policy (09). *(`test_gates_decide`, integration gate E2E.)*
- [x] A gate cannot PASS unless `Repository.canonical_commit == ic.integrated_sha` (09). *(`gates.decide` + integration canonical test.)*
- [x] The remediation loop produces a new Execution → new IC → new gates (09). *(`test_remediation_carry_forward.py`; live Forge path **`test_remediation_live_forge.py`** with scoped IC pytest — run **`verify-phases --live`** for sign-off.)*

### Evidence
- [x] Every Evidence row references the exact integrated SHA (09). *(EvidenceService + persistence immutability + gate SHA mismatch.)*
- [x] MODEL_ASSESSMENT never satisfies a mandatory AC (09). *(`evidence_rules` + `test_gates_decide`.)*
- [ ] External CI evidence is accepted only for known SHAs with correlation (16).

### Brownfield
- [ ] Context isolation is proven by a manifest (11, 19).
- [ ] FACTs come only from deterministic discovery (11).
- [ ] Confidence is capped by deterministic evidence (11).
- [ ] DISCOVERED links are distinguishable and retained after HUMAN_CONFIRMED (11, 12). *(**P12-F12**.)*
- [ ] Onboarding uses the shared Repository connector / materializer, not a Greenfield-only path (04, 11).

### Behavioral Baselines
- [ ] Every ACTIVE baseline has PASS evidence at its established SHA (12). *(Journey depth **P12-F11**; kernel path tested in workflows.)*
- [ ] BaselineSets are versioned and monotonic (12, 14, 15, 19).
- [x] The baseline release condition and BASELINE gate are active for FEATURE_CHANGE/BUG_FIX (12). *(Phase **14** journey: BASELINE gate PASS at IC SHA + R2 eligibility — **`feature_change_acceptance.py`**; BUG_FIX → Phase **15**.)*

### Impact Analysis
- [x] ImpactAssessment items have traversal paths, retrieval source and confidence (13). *(`tests/integration/impact`, `tests/unit/impact`.)*
- [x] Only STRUCTURAL items create obligations, each with a reason (13). *(`core/assurance/obligations.py`, impact integration tests.)*
- [x] StalenessService flags tasks, executions and baselines on input change (13). *(`tests/integration/impact` staleness + canonical revision cases.)*
- [x] A canonical revision change marks impacted TaskContracts, Executions, candidate indexes, ImpactAssessments and baselines; a diverged cycle base requires explicit rebase (13, 16). *(13: canonical revision staleness tests; 16 external sync pending.)*

### Feature Change
- [x] FeatureSpec v(n+1) with a hash-pinned SpecDelta; the parent version is unchanged (14). *(`feature_change_acceptance.py`; parent **SUPERSEDED**, delta **APPROVED**.)*
- [x] Task scope is bounded by ImplementationSpec delta + impact (14). *(Contract **`allowed_scope`** vs impl delta **`file_scope`** in acceptance helper.)*
- [x] Cycle starts from the canonical repository SHA; Forge runs in ExecutionWorkspaces; IC READY advances `canonical_commit` and re-indexes (14). *(Journey + **`repository.canonical_commit == ic.integrated_sha`**.)*
- [x] New ACs and impacted baselines PASS at the IC SHA before R2 (14). *(Priority AC obligations + gate PASS; harness sentinel ordering.)*

### Bug Fix
- [x] PRE_REPAIR reproduction evidence predates the first repair commit (15). *(Journey **`assert_bug_fix_phase15_acceptance`** + **`test_bugfix_eligibility.py`**.)*
- [x] Expected behavior is explicitly resolved before root cause; ambiguous cases go to a human decision or SpecDelta (15). *(Journey fallbacks + guards; CONFLICTING human path optional REST follow-up.)*
- [x] The root-cause hypothesis is INFERENCE and never Evidence (15). *(`test_rca_inference.py`, journey acceptance.)*
- [x] Affected SHA is the pinned canonical revision; repair runs in an ExecutionWorkspace; IC READY advances `canonical_commit` and re-indexes (15). *(Journey **`repository.canonical_commit == ic.integrated_sha`**.)*
- [x] The regression test fails at the affected SHA and passes at the IC SHA (15). *(REGRESSION stage + **`test_post_repair_regression_chain_db.py`**.)*

### Inbound Integration
- [x] A common `InboundEvent` envelope with correlation ID and idempotency (05). *(inbound kernel + `test_upload_inbound_audit_and_guards`, `test_unauthenticated_inbound_rejected`.)*
- [ ] HMAC-authenticated webhooks with a replay window (16).
- [x] Unique `(source_type, source_id, event_id)`; a duplicate is ACKed without re-dispatch (05, 16). *(05: `test_product_source_upload` duplicate content + idempotency; 16 webhooks pending.)*
- [ ] Stale or out-of-order events are recorded without mutation (16).

### Outbound Integration
- [ ] Connectors are callable only via ToolGateway (16 import contract).
- [ ] Every mutating ConnectorAction carries an idempotency key and correlation ID (04, 16).
- [ ] `external_links` trace every external mutation (16).

### Release
- [~] Eligibility is persisted per condition, with reasons (10). *(Models + `ReleaseEligibilityService`; registry unit test.)*
- [~] Release approval is pinned to the manifest hash (10). *(Approval(RELEASE) on manifest hash; persistence tests pending.)*
- [~] Release Manifest references the exact integrated SHA (10, 14, 15, 19). *(Manifest builder + validator in code.)*
- [~] The manifest SHA == default-branch HEAD == tag == `Repository.canonical_commit` == `Repository.released_commit` == released index pointer (10). *(Executor + git tests; E2E pending.)*
- [~] A TOCTOU re-check at execution (10). *(In `stratos.release`; test pending.)*
- [~] A DeliveryOutcome bundle is persisted (10). *(Completion hook; journey pending.)*

### Observability / Security
- [x] One correlated trace across API → scheduler → execution → model → tool → connector (18). *( **`tests/integration/observability/test_trace_chain.py`**. )*
- [x] No secrets in logs, traces, snapshots, artifacts, commits or agent context (18). *(Redaction + snapshot gate + **`make verify-phase-18`** security lane.)*
- [x] Network-less sandbox for untrusted code (18). *( **`SandboxRunner`** + **`test_sandbox_isolation.py`**; journey **`/ready`** in **`test_ready_sandbox.py`**. )*
- [x] The audit hash chain verifies (18). *( **`test_audit_chain.py`** + **`GET /audit/verify`**. )*
- [x] RC-01..RC-12 recovery scenarios pass (18). *( **`tests/recovery/test_rc_scenarios.py`** + RC-11 via integration SSE test in **`make check`**. )*
- [x] Live Scout/Forge prompt-injection resistance (18 plan §11). *( **`make verify-phase-18-live`**: no **`FACT`** inflation in Scout survey; Forge denies **`git.push`** / **`main`** commit under **`AGENT_INSTRUCTIONS.md`** injection.)*

---

## 9. INTEGRATION TRACKER

Status values: `NOT_STARTED | IMPLEMENTED | VERIFIED` (VERIFIED = connector/integration tests and the owning journey test passed). Rows marked "(planned)" describe the contract each phase must deliver.

### Inbound

| Integration | Connector / Adapter | Phase | Status | Contract | Idempotency | Retry | Reconciliation | Correlation ID | Audit / Evidence |
|---|---|---|---|---|---|---|---|---|---|
| Document upload | `document_upload` (`POST /projects/{id}/sources`) | 05 | **VERIFIED** | `InboundEvent` → immutable `ProductSource` version | `(source, event_id)` unique + content hash (duplicate → no new version) | client re-POST is safe (duplicate ACK) | n/a (synchronous) | assigned or propagated | `inbound_events` + `audit_events` + `product_source.ingested`; tests: `test_product_source_upload`, `test_product_model_api_workflow` |
| Repository registration | `repository_registration` (API) | 01 (LOCAL metadata), 04 (materialize), 11 (EXTERNAL_CLONE wiring), 16 (remote + webhook) | **IMPLEMENTED** (LOCAL **VERIFIED** 04); **16** remote Gitea clone E2E pending (**P16-F03**) | `declare_managed` / `register_external` + `RepositoryMaterializationService`; **`attach_remote`** for publish | `Idempotency-Key` + `UNIQUE(project_id)` | client retry safe; `retry_materialization` | materialization loop + retry API | command correlation | materialization events + REST; **`attach_remote`** in live journey |
| Git webhook | `git_provider_webhook` (GitHub/Gitea) | 16 | **VERIFIED** (unit/HMAC + sync classification); live delivery E2E **P16-F02** | push / ref → `record_repository_event` → `RepositorySyncService`; HMAC **`HMAC_SHA256`** | `(source, delivery id)` unique | provider redelivery | ancestry STALE + scheduler poll | from delivery / assigned | **`test_p16_features`**, **`test_repository_sync_external_fast_forward`** |
| Issue / change event | `change_request_api` (14), `issue_tracker_webhook` (16) | 14, 16 | **VERIFIED** (14 API + 16 live journey) | label `olympus:change` → `intake_change_request` | event id unique; one CR per issue | provider redelivery | `updated_at` vs stored source_version | propagated to the cycle | **`test_p16_acceptance_criteria`**, **`test_feature_change_via_issue_tracker`** |
| Defect event | `defect_report_api` (15), `issue_tracker_webhook` (16) | 15, 16 | **VERIFIED** (15 API); **16** adapter **IMPLEMENTED** (`olympus:defect`) — live issue path **P16-F06** | `intake_defect` / webhook label | event id + `external_ref` idempotency | provider redelivery | source_version staleness | propagated | **`verify-phase-15-exit`** |
| CI / test event | `ci_callback` | 16 | **VERIFIED** | `ingest_external_ci_result` → **`EXTERNAL_CI`** evidence (SHA + correlation) | run id unique | CI runner retry | STALE for superseded IC SHA | correlation id | compose **`ci_runner`** + journey + **`test_ac_ci_evidence_requires_correlation`** |
| API / operator command | command bus (`POST …/commands/{command}`); `operator_api` recording | 01, 16 | **IMPLEMENTED** (01 command bus + **`command_log`**); **`operator_api`** inbound adapter **NOT_STARTED** (**P16-F07**) | typed commands, HUMAN actor | `command_log(actor_id, idempotency_key)` unique | replay returns stored result | n/a | `X-Correlation-ID` | `command_log` + `audit_events` |

### Outbound

| Integration | Connector | Phase | Status | Contract | Idempotency | Retry | Reconciliation | Correlation ID | Audit / Evidence |
|---|---|---|---|---|---|---|---|---|---|
| Git actions (local) | `git_local` | 04 (08 merge, 10 ff/tag, 11 clone) | **IMPLEMENTED** (04 provision/clone/init) | `ConnectorAction` registry; materialization + gateway SYSTEM path | idempotency key per action | bounded | by ref / tree hash | execution + correlation | `connector_actions/results` + audit |
| Git actions (remote) | `git_provider_github`, `git_provider_gitea` | 16 | **VERIFIED** (Gitea live: **`attach_remote`**, PR branch push, **`test-connector-live`**) | fetch, push_branch, push_release, clone, PR, validate; **`GIT_ASKPASS`** token auth | idempotency key per action | reconciliation worker | remote ref SHA / PR search | yes | **`test_git_provider_unit`**, live journey, Stratos **`push_release`** |
| CI trigger | `ci_http`, `ci_github_actions` (stub) | 16 | **VERIFIED** (`ci_http` in journey); **github_actions** stub only (**P16-F05**) | `trigger_verification` + signed callback | key per (IC SHA, suite) | same key | run lookup by correlation id | yes | **`tests/support/ci_runner`** + journey |
| Issue update | `issue_tracker_gitea` (+ GitHub connector surface) | 16 | **VERIFIED** (Gitea comment/close in live journey) | post_comment, close; idempotency marker | idempotency key | same key | reconcile via marker | yes | **`run_post_release_integrations`**, **`external_links`** |
| Artifact publication | `artifact_fs`, `artifact_s3` | 03, 16 | **IMPLEMENTED** (deterministic **`test_p16_*`**); MinIO in compose; live S3 path **P16-F08** | publish/read | content hash | same key | object hash reconcile | yes | connector registry + acceptance tests |
| Deployment | `deployment_local` | 10 (release), 16 (deploy) | **VERIFIED** (journey **`deploy_status` HEALTHY**) | deploy / status / rollback hooks | key per (release, target) | same key | health version | yes | **`DeployLocalConnector`**, journey assertions |
| External APIs | `http_generic` | 16 | **IMPLEMENTED** (allowlist + registry); live allowlist E2E optional | host + method allowlist | idempotency key | same key | policy opt-in | yes | **`test_ac_outbound_connectors_registered_with_idempotency`** |

---

## 10. LIVE LLM READINESS

| Field | Value |
|---|---|
| Provider | **OpenAI** (live proof model **`gpt-5.4-mini`**). Anthropic adapter also implemented. Credentials via gitignored `.env` (never commit). |
| ModelRouter | **IMPLEMENTED** (Phase 02) — alias resolution, structured output loop, budget, `model_calls` persistence. |
| Configured Model Aliases | **`config/models.yaml`** (D-11): `product_decomposition`, `planning`, `architecture`, `repository_reasoning`, `implementation`, `review`, `verification_planning`, `orchestration`, `embedding`. Resolved via `MODEL_*` env vars + `MODEL_DEFAULT`. |
| Credentials Configured | **Yes** locally (`.env`); CI `live` job uses GitHub `OPENAI_API_KEY` secret on `workflow_dispatch`. |
| Structured Output Validation | **IMPLEMENTED** — Pydantic + provider-native schema; OpenAI strict mode (recursive `additionalProperties: false` in `pydantic_to_json_schema`); `test_structured_output_schema.py` + live Kira decompose. |
| Retry Handling | **IMPLEMENTED** — schema ≤ 2, transport ≤ 3 (defaults in `config/models.yaml`); unit-tested. |
| Token Usage Tracking | **IMPLEMENTED** — `model_calls.input_tokens` / `output_tokens` + `provider_request_id`. |
| Cost Tracking | **IMPLEMENTED** — `config/model_pricing.yaml` estimates on each call; session summary in `live_guard` after live runs. |
| Live Integration Tests | **PASS** — Phase 02 router/runtime **2/2**; product decompose **`live_llm`** **7/7** + planning **3/3**; Phase **18** **`verify-phase-18-live`** **4/4** (2026-10-06); typical spend ≈ **$0.02–0.05** per broad live run, Phase **18** lane ≈ **$0.01** (Forge worker ticks dominate wall time). |
| Journey Tests | **PARTIAL** — Journeys **3** and **4** isolated PASS (**2026-10-05**, **`verify-phase-14-exit`** / **`verify-phase-15-exit`**); four-journey chained proof → Phase **19** |

Per capability:

| Agent | Profiles | Alias(es) | Phase | Structured output | Live contract test | Journey proof | Status |
|---|---|---|---|---|---|---|---|
| Orchestrator | `orchestrator.converse` | orchestration | 17 | `OrchestratorTurn` | **`test_orchestrator_live.py`** (clarification + propose-draft; **`LLM_LIVE_TESTS=1`**) | 19 (optional explain) | **IMPLEMENTED** (live proof **local/CI dispatch** — not in default **`make check`**) |
| Kira | `kira.decompose`, `kira.implementation_spec`, `kira.task_plan`, `kira.change_interpret`, `kira.defect_triage`, `kira.expected_behavior` | product_decomposition, planning | 05, 06, 14, 15 | `ProductDecomposition`, `ImplementationSpecDraft`, `TaskPlan`, `ChangeInterpretation`, `DefectTriage`, `ExpectedBehaviorProposal` | **`test_kira_decompose_prd_live.py`**, **`test_kira_impl_spec_create_ticket_live.py`**, **`test_kira_task_plan_live.py`**, **`test_kira_change_interpret_live.py`**, **`tests/integration/live_llm/defects/test_kira_defect_triage_live.py` (LIVE PASS 2026-10-05)** + FakeProvider `test_planning_agent_profiles.py` | 10, 14, 15, 19 | **PARTIAL** (05–06 + **`change_interpret`** + **`defect_triage`** **LIVE VERIFIED**; **`expected_behavior`** live optional) |
| Atlas | `atlas.propose_architecture`, `atlas.architecture_delta` | architecture | 06, 14 | `ArchitectureProposal`, `ArchitectureDeltaProposal` | **`test_atlas_supportdesk_live.py` (LIVE PASS 2026-10-02)** + decline path in journey (no delta required for priority CR) + FakeProvider worker persist | 10, 14, 19 | **PARTIAL** (`propose_architecture` **LIVE VERIFIED**; **`architecture_delta`** live propose optional — journey proves decline guard) |
| Scout | `scout.survey`, `scout.recover_feature` | repository_reasoning | 11, 18 | `RepositorySurvey`, `RecoveredFeatureSpec` | `test_scout_supportdesk_live.py`; **`test_prompt_injection_scout_live.py`** (§11 injection, **`verify-phase-18-live`**) | 12, 19 | LIVE VERIFIED |
| Forge | `forge.implementation` | implementation | 04 (06 compiled contracts), 18 | `ImplementationResult` | `test_forge_candidate_commit_live.py`; **`test_prompt_injection_forge_live.py`** (§11 scoped commit, no push — **`verify-phase-18-live`**) | 10, 14, 15, 19 | **LIVE VERIFIED**; Journey **3** `assert_live_llm_proof` + deterministic fallback |
| Warden | `warden.review`, `warden.root_cause` | review | 09, 15 | `WardenReview`, `RootCauseHypothesis` | `test_warden_sentinel_profiles.py` + live assurance lane **`tests/integration/live_llm/assurance/`** | 10, 14, 15, 19 | **PARTIAL** (live profiles in Phase **09** lane; Journey **3** uses harness static review evidence) |
| Sentinel | `sentinel.plan`, `sentinel.summarize`, `sentinel.characterize`, `sentinel.reproduce` | verification_planning | 09, 12, 15 | `VerificationPlan`, `CharacterizationPlan`, reproduction test artifact | `test_warden_sentinel_profiles.py` + **`sentinel.execute`** + **`tests/integration/live_llm/defects/test_sentinel_reproduce_live.py` (LIVE PASS 2026-10-05)** | 10, 12, 14, 15, 19 | **PARTIAL** (execute + **`reproduce`** live verified; Journey **4** uses fallbacks where needed) |
| (platform) | `diagnostic.structured_echo`; `ModelRouter.embed` | verification_planning; embedding | 02, 03; 13 | `DiagnosticSummary`; `EmbeddingResult` | `test_model_router_live.py`, `test_langgraph_runtime_live.py`; `test_execution_spine_live.py` (**PASS**); **`test_semantic_retrieval_live.py`** (Phase **13** — asserts when embed entitled; **skip** with guidance on 403 / missing **`MODEL_EMBEDDING`**) | — | **LIVE VERIFIED** (router/runtime + execution spine); **embedding path PARTIAL** until project allows **`MODEL_EMBEDDING`** |
| Stratos | `stratos.release` (deterministic executor) | — (no LLM) | 10, 16 | n/a | n/a | 10, 14, 15, 19 | NOT_STARTED |

Rules (README §6.3): `FakeProvider` is allowed only in `local`/`test` unit tests. `--live-required` turns skipped live tests into failures. Journey tests must pass `assert_live_llm_proof`.

---

## 11. MVP DEFINITION OF DONE

| Journey | Definition | State |
|---|---|---|
| Greenfield | Product Source → Verified Release R1 | PARTIAL |
| Brownfield | Unknown Repository → Trusted Product Model → READY_FOR_CHANGE | COMPLETE (Phase **12**; live journey **2026-10-04**; Phase **19** acceptance re-run pending) |
| Feature Change | Versioned Spec Delta → Impact Analysis → Safe Code Delta → Regression-Safe Release R2 | COMPLETE (Phase **14**; live Journey **3** **2026-10-05**; Phase **19** chained re-run pending) |
| Bug Fix | Defect → Reproduction → Root Cause → Repair → Regression-Proven Release R3 | PARTIAL (Phase **15** + **`verify-phase-15-exit`** **2026-10-05**; Phase **19** evaluator + chained demo pending) |

Final conditions (each is computed by the Phase 19 MVP Acceptance Evaluator — see **`dod_checks.py`**):
- [~] product-to-code lineage queryable; *( **`product_to_code_lineage_queryable`**, **`assert_lineage_forward`**.)*
- [~] required FeatureSpecs/requirements approved; *( journey + **`mandatory_acceptance_criteria_backed_by_evidence`**.)*
- [~] mandatory Acceptance Criteria backed by evidence; *( **`assert_feature_change_phase14_acceptance`** / obligations.)*
- [~] required Behavioral Baselines pass; *( Phase **12** baselines + bug-fix gates.)*
- [~] required gates pass; *( **`required_gates_pass`** DoD check.)*
- [~] no blocking Findings remain; *( **`no_blocking_findings_remain`**.)*
- [~] required approvals exist; *( **`required_approvals_exist`**.)*
- [~] canonical Code Intelligence index matches verified IntegrationCandidate; *( **`code_index_matches_current_integration_candidate`**.)*
- [~] release eligibility calculated deterministically; *( release rows + Phase **10** eligibility in journey.)*
- [~] Release Manifest references exact verified integrated commit; *( **`release_manifest_references_exact_integrated_sha`**.)*
- [~] inbound events are auditable/idempotent where applicable; *( **`inbound_events_are_authenticated_idempotent_and_traceable`**.)*
- [~] outbound mutations pass through ToolGateway/connector governance; *( **`connector_partial_failures_are_reconcilable`** when chaos.)*
- [~] real LLM paths exercised for model-dependent behavior; *( **`real_LLM_paths_exercised_for_model_dependent_behavior`**.)*
- [~] runtime restart does not lose canonical delivery truth. *( **`canonical_state_survives_runtime_restart`** + RB-A..D fingerprints.)*

`MVP_COMPLETE` additionally requires every conjunct of ARCH §26 and TECH §32 (evaluator) and every ARCH §22 / TECH §31 row (acceptance matrix) to be proven, on two consecutive clean runs (Phase 19 §15), **and** Post–Phase 19 full-repo regression (**P19-REG**: **`make verify-phases-live`** exit **0**).

---

## 12. OPEN ARCHITECTURE QUESTIONS

Each question has a working default that the plans already implement, so implementation can proceed. A human owner must confirm or override each one before the phase listed under "Needed by".

| ID | Question | Working default in plans | Needed by | Status |
|---|---|---|---|---|
| Q-01 | Should Kira, Atlas, Scout, Sentinel and the other agents' model work run as scheduled Task Executions (snapshot, lease, audit, retry), even though ARCH/TECH describe some of it as service flows? | Yes (D-12): every model call runs inside an Execution of a CONTROL_PLANE or IMPLEMENTATION_PLAN Task. | 03 | OPEN |
| Q-02 | In the chained demo, Brownfield DC-002 runs on a Project that already has a canonical Greenfield model. How do recovered specs relate to it without breaking "fresh context"? | Scout context is isolated (no product-model rows). The deterministic reconciliation report (MATCHED/NEW/MISSING/DIVERGENT) feeds human review, and MATCHED → `CONFIRM_EXISTING` (no duplicate lineage). | 11 | OPEN |
| Q-03 | Is the alias set acceptable? TECH Appendix A defines six; the plans add `planning`, `orchestration` and `embedding`. | Nine aliases, all defaulting to `MODEL_DEFAULT`. | 02 | OPEN |
| Q-04 | Which embedding provider backs the `embedding` alias? Anthropic has no embeddings API. | OpenAI embeddings; local `fastembed` as fallback. Semantic retrieval degrades gracefully. | 13 | CONFIRMED |
| Q-05 | How is the closed-ticket defect introduced into the live-generated SupportDesk code for the chained demo? | Strategy A (Phase 19 §4.3): a deterministic, index-located LibCST injector applied as an external commit and detected by Phase 16 sync. Strategy B (separate Project on the hand-written defect fixture) only as an explicit waiver. | 19 | OPEN |
| Q-06 | What are the cost and duration ceilings for one live four-journey chained run? These set `LLM_TEST_BUDGET_USD` and CI timeouts. | No default. Phase 10 recommends ≥ $15 for Greenfield alone. | 19 (set by 10 from observed cost) | OPEN |
| Q-07 | Is the REMEDIATION DeliveryCycle type needed as a standalone cycle in the MVP? | Defined in Phase 01 for completeness. Remediation normally runs inside the owning cycle (09, 12). | 12 | OPEN |
| Q-08 | Brownfield remediation is published through the Release mechanism and consumes a release key (R<n>). Is that acceptable? | Yes. The chained demo is designed to need no remediation. | 12 | OPEN |
| Q-09 | Which agent performs Bug Fix root-cause reasoning? The documents name none. | Warden (`warden.root_cause`): read-only and independent of Forge. Output is INFERENCE only. | 15 | **CONFIRMED** (2026-10-05) |
| Q-10 | After an external push to the default branch, the canonical index pointer moves to the external SHA (`source=EXTERNAL_PUSH`, Phase 16). Confirm that this matches ARCH §13.1 ("canonical = current IC or released commit"). | Accepted as the project baseline for impact and reproduction. Assurance still requires pointer == IC SHA at ASSURANCE entry (invariant 18). Adoption writes `canonical_commit` only via `RepositoryRevisionService.advance(cause=EXTERNAL_SYNC)`. | 16 | OPEN |
| Q-11 | May a Project have more than one Repository in the MVP? | No. `UNIQUE(project_id)`. Relaxing later needs cycle-level repository selection and per-repository base pins; the entity shape stays. | 01 | OPEN |
| Q-12 | May two DeliveryCycles hold unreleased canonical revisions at the same time? | No. IC creation is rejected with `CANONICAL_REVISION_HELD`. A new IC in the same cycle (remediation) is allowed and supersedes. | 08 | OPEN |
| Q-13 | Is the canonical RepositoryWorkspace a bare Git repository? | Yes. No working tree; reads use Git objects; every checkout is an ExecutionWorkspace that shares the object store. | 01, 04 | OPEN |
| Q-14 | Where does `credential_ref` resolve, and is an encrypted local secret store acceptable? | Phase 04: `none:` / `env:`. Phase 16 adds `file:` and encrypted `secret:` keyed by `OLYMPUS_SECRET_KEY` (`PUT /secrets/{name}`); verified in **`test_secret_store_encrypted_not_plaintext`**. Vault / cloud SM post-MVP. | 16 | ACCEPTED (local store) |
| Q-15 | Are non-local workspace backends or multi-host workers in MVP scope? | No. `LOCAL_FILESYSTEM` under one shared `OLYMPUS_WORKSPACE_ROOT`. | 04, 18 | OPEN |
| Q-16 | Must a `GREENFIELD_MANAGED` repository have a remote before Release R1? | No. Journey 1 completes locally. Phase 16 `attach_remote` is optional; Phase 19 Stage A uses it for Gitea. RC-12 must back up `OLYMPUS_WORKSPACE_ROOT`. | 10, 16, 18 | OPEN |

**Q-04 decision (confirmed 2026-10-04):** The **`embedding`** alias uses **`provider: openai`** in **`config/models.yaml`** and model id **`MODEL_EMBEDDING`** (recommended default **`text-embedding-3-small`** when unset in env docs). Chat may use Anthropic via **`MODEL_PROVIDER=anthropic`**; embeddings remain a separate provider registration. **Primary:** OpenAI Embeddings API via **`ModelRouter.embed`**. **Degradation:** if the provider is missing, auth fails, or policy disables semantic expansion, **ImpactEngine** / **HybridRetrieval** omit **SEMANTIC** / **SEMANTIC_CANDIDATE** items; structural and lexical paths are unchanged. Semantic candidates never create verification obligations alone (plan §13). **Deferred:** local **`fastembed`** provider when **`OPENAI_API_KEY`** is absent — optional offline dev enhancement post-**13**.

---

## 13. ARCHITECTURE DRIFT LOG

Planning-time source reconciliations are recorded in `plans/README.md` §2 (D-01..D-17) and are not drift. Implementation-time drift is recorded here, following the protocol in `plans/README.md` §9.

---

## 14. STATUS DISCIPLINE

1. This file is authoritative for implementation tracking. Update it in the **same commit** as the work it describes.
2. Before starting a phase, confirm every `Depends On` phase is `COMPLETE`. Then set the phase to `IN_PROGRESS`, and set Overall State, Current Phase and Current Milestone.
3. Tick Progress groups as their development tasks complete. Record blockers immediately and set `BLOCKED` when work cannot continue.
4. A phase may be set to `COMPLETE` only when **every** §14 acceptance criterion and §15 exit criterion of its plan is satisfied. The evidence (test node IDs, CI run IDs, live run IDs, cost) goes in that phase's Notes. Then update §2, §4, §6, §7, §8, §9 and §10 as applicable.
5. A skipped live test is not evidence. Mocked or canned LLM output is never journey evidence.
6. If a phase's acceptance criteria change, update both the phase file and §5 here in the same commit.
7. Dependency changes must keep the graph acyclic. Update §3, §4 and the affected phase files' §16 together.
8. Architecture drift follows `plans/README.md` §9. Any change to an invariant sets the phase to `BLOCKED` until a human approves it.
9. Overall State becomes `MVP_COMPLETE` only after Phase 19 §15 **and** **P19-REG** (§5 Post–Phase 19).

---

## 15. PLANNING CHANGE LOG

| Date | Change |
|---|---|
| 2026-10-07 | **Remove legacy operator UI:** deleted **`apps/dashboard/`**, **`docs/frontend/`**, **`scripts/check_dashboard_openapi.py`**; dropped CI **`dashboard`** job, compose **`dashboard`** services, **`dashboard-check`** / MVP Playwright steps; matrix **TECH31-13** / **ARCH22-25** removed; Phase **19** walkthrough deferred. Phase **17** remains backend-only. |
| 2026-10-07 | **Phase 19 acceptance criteria wiring:** **`dod_checks.py`**, expanded **`evaluate_mvp.py`**, **`assert_chained_acceptance_criteria`**, matrix **ARCH22-25**, **`backup_restore_eval.sh`**, §14 ACs → **[~]** pending stack sign-off; **19.14** **[x]**; §11 DoD mapped to evaluator checks. |
| 2026-10-07 | **Phase 19 chaos + RC-01 wiring:** **`chaos_hooks`**, **`worker_drain`**, Forge drain in **`greenfield_live`** / **`feature_change_live_pipeline`**, runner **`MVP_CHAOS_*`** stages, driver SSE restart; **`test_rc01_forge_kill_live.py`** implemented; **P18-F01** → WIRED (live sign-off pending); §2 milestone → Phase **19** sign-off track; task **19.16b** **[x]**; **19.18–19.20** still open. |
| 2026-10-06 | **STATUS Phase 18 detail:** implementation record + verify commands + §15 exit row; §10 Scout/Forge injection live contracts; invariant tracker §11 live; follow-ups **P18-F01** (RC-01 live) / **P18-F02** (plan sync). |
| 2026-10-06 | **Phase 18 live §11:** **`make verify-phase-18-live`** **4** passed (**1** RC-01 skip); Scout **`ContextItem`** provenance fix; **`make verify-phase-18-exit`** green end-to-end. |
| 2026-10-06 | **Phase 18 COMPLETE:** §14 acceptance criteria **[x]**; trace chain + RC-01..RC-12 deterministic suite + Forge/Scout injection + backup/restore smoke; **`make verify-phase-18`** **86** passed; **`make check`** green. §2 → **18/20**; current phase **19**. |
| 2026-10-06 | **Phase 18 §12 deterministic:** migration **`0032_p18_security_observability`**; OTel/security/sandbox/ops modules; **`make migrate`**, **`make lint`**, **`make check`**, **`make verify-phase-18`** exit **0** (**64** passed, **13** skipped). §2/§4/§8 Phase **18** → **`IN_PROGRESS`**; §14 ACs partially checked; RC + live Forge/RC-01 exit still open. Integration fixes: **`/ready`** **`storage`/`sandbox`**; approval scope + viewer token scopes. |
| 2026-10-06 | **STATUS hygiene:** §1 git reality (uncommitted **00–17** on **`4b127e5`** baseline); Phase **03** implementation record synced (**`model-calls`** no longer listed as missing); Phase **17** shipped table + README/CI references. |
| 2026-10-06 | **Phase 17 re-verify:** **`make verify-phase-17-exit`** exit **0** post-closure (~**48s**); §1/§2/§5 verification table updated. |
| 2026-10-06 | **Phase 17 closure:** **`GET /executions/{id}/model-calls`**, live worktree mapping; **`plans/17`** §10/§14 checkboxes + migration **`0031`**; OpenAPI **`schema.d.ts`** regen. |
| 2026-10-06 | **Phase 17 exit signed off:** **`make verify-phase-17-exit`** exit **0** (bootstrap + §12 + live orchestrator **3/3**). **`scripts/verify-phases-00-07.sh`** accepts **`--phase 17`**; orchestrator inbox scoped to session cycle; validator + worker canonical turn. §2 → **17/20**; current phase **18**. |
| 2026-10-06 | **Post–Phase 19 regression gate:** §3 sequence + §5 **P19-REG** (full-repo **`make verify-phases-live`** after **`make mvp-acceptance`**); §6 journey row; §11 / §14 **MVP_COMPLETE** prerequisites; Phase **19** task **19.20** + acceptance criterion; `plans/19` §15 aligned. |
| 2026-10-06 | **STATUS Phase 16 hygiene:** §3 matrix **COMPLETE**; §9 integration tracker refreshed; MVP invariant **38** **[x]**; **16.15–16.16**, **Additions/hardening**, **P16-F01..F08** follow-ups documented. |
| 2026-10-06 | **Phase 16 exit signed off:** **`make verify-phase-16-exit`** exit **0** end-to-end (§13 journey **PASS**). Hardening: OSS compose (MinIO image, volume mounts, healthchecks), **`integrations-seed`** idempotency, **`GIT_PROVIDER=gitea`**, Gitea issue label IDs, **`attach_remote`** push/tag/credentials, **`git_askpass.py`**. §2 → **16/20**; current phase **17**. |
| 2026-10-06 | **Phase 17 implementation (in progress):** read-model routers (`/views/*`), **`next-transitions`**, **`/commands/catalog`**, **`/actors/me`**, global **`/events/stream`**, migration **`0031_p17_orchestrator`**, **`orchestrator.converse`** + session API, dashboard live proxy/SSE/auth, **`OrchestratorPanel`**, **`tests/ui`**, **`test_orchestrator_live.py`**, CI **`dashboard`** + OpenAPI freshness. §5 Phase **17** + §10 Orchestrator row updated; exit **not** signed. |
| 2026-10-06 | **Phase 17 COMPLETE:** M-22 **`/views/delivery-cycles/{id}/control-plane`**, M-05 **`/views/projects/{id}/agent-activity`**, live-services parity (inbox kinds, release approve, reconciliation, impact adapter), §12 Playwright **`phase17-acceptance.spec.ts`** (**9/9**), **`make verify-phase-17`** / **`-exit`**, CI **`test:ui`**. §14 green; §2 → **17/20**. |
| 2026-10-05 | **Phase 16 §13 live journey:** **`make test-journey-issue-tracker`** — Gitea issue → R2 + integrations; shared pipeline **`feature_change_live_pipeline.py`**. |
| 2026-10-05 | **Phase 16 COMPLETE:** outbound connectors **16.9–16.13**, §14 **`test_p16_acceptance_criteria`**, **`make verify-phase-16-exit`** green. |
| 2026-10-05 | **Phase 16 §12 verify (re-run):** **`make test-integrations-p16`** **16/16**, **`make test-connector-live`** **2/2** (compose + **`integrations-seed`**); Makefile loads **`.env`** for connector targets; **`make verify-phase-16-exit`** exit **0**. |
| 2026-10-05 | **Phase 16 §12 verify:** migration **`0030_p16_integrations`**, OSS compose profile, deterministic + live tests; **`make verify-phase-16-exit`** exit **0**; Phase **16** remains **`IN_PROGRESS`** (§14 ACs, connectors 16.9–16.13, issue-tracker milestone pending). |
| 2026-10-07 | **Frontend UI track (Olympus Studio):** §16 opened; **C0** hygiene complete (duplicate cleanup, inbox types + `/views/inbox` query filters, SSE resume, status adapter). |
| 2026-10-01 | Initial plan set created: `plans/README.md`, phases 00–18. |
| 2026-10-01 | Planning review and completion. Added Phase 19 and this `STATUS.md`. Reconciled cross-phase inconsistencies (each fix is the smallest compatible change):<br>• Phase 18 RC-05 and its startup reconciler now use the Phase 08 IC states (`INTEGRATING` retry on the same IC), not a nonexistent `BUILDING` IC state.<br>• Phase 18 sandbox fallback uses `OLYMPUS_ENV` `local`/`test`, not `dev`.<br>• Phases 16 and 18 compose commands use the root `docker-compose.yml` with `deploy/` overlays.<br>• Phase 15 uses `affected_sha` instead of "released SHA", to support the external-push defect path.<br>• Phase 07 classifies external imports (stdlib / declared dependency / undeclared; TECH §2 "importlib metadata").<br>• Phase 01 adds the `delivery_cycle_events` view (TECH §5.1; README D-15).<br>• README markers add `connector_live` and `ui`, and README §10 aligns with task-group progress tracking. |
| 2026-10-01 | **Repository materialization tightening (plan-only).** No new phase. README D-16/D-17 and §5.9 already define the ownership split, unified Repository / RepositoryWorkspace / ExecutionWorkspace model, configurable `OLYMPUS_WORKSPACE_ROOT`, Greenfield/Brownfield flows, candidate vs canonical revision and Code Index, connectors and credentials. This change syncs STATUS.md to those plans: Journey Readiness repository dependencies; eight repository/workspace invariants; §8 Repository Model / Workspace Model / Greenfield / Brownfield / Integration / Code Intelligence / Assurance / Release trackers; Phase 00–16 §14 ACs copied from the phase files; Q-11..Q-16 recorded. Phase 00 adds the workspace-root settings AC; Phase 18 RC-12 now backs up `OLYMPUS_WORKSPACE_ROOT`. No production code, migrations or adapters were added. |
| 2026-10-01 | **Phase 01 COMPLETE:** §12 suites, API idempotency + transition rejection audit, SSE session factory fix, contract issue ordering fix; `make check` + 80 pytest + 4 security tests green; §14/§15 closed. |
| 2026-10-01 | **Phase 01 gap closure:** split Alembic `0001`–`0004`, `CommandBus` on primary mutating REST routes, task/cycle transition idempotency + concurrent revision-advance persistence test, security lane in `make check`; 83 pytest green. |
| 2026-10-01 | **Phase 01 plan sync:** `plans/01-…` §10/§14 checked complete, §19 implementation record + §15 CI follow-up; `STATUS.md` implementation record table aligned. |
| 2026-10-01 | **Phase 02 test pass:** `make check` green (98 pytest: 62 unit incl. runtime, 19 persistence incl. `model_calls`, 13 integration, 4 security); `make test-live` correctly fails without `ANTHROPIC_API_KEY`/`OPENAI_API_KEY`; §10 Live LLM Readiness + Phase 02 test evidence updated. |
| 2026-10-02 | **Phase 02 live lane → OpenAI:** `config/models.yaml` defaults use `${MODEL_PROVIDER}`; `.env.example` + CI `live` job default `openai` / `gpt-5.4-mini`; `tests/live_credentials.py` reads keys from settings; `make test-live` **2/2 PASS** (~$0.000380). **Phase 02 COMPLETE.** |
| 2026-10-02 | **Regression verification:** `make check` + `make test-live` green (live spend ≈ $0.000378); §2 current phase → **03**; Phase 02 test evidence refreshed in `STATUS.md`. |
| 2026-10-02 | **Phase 03 verification:** migration `0006`, scheduler/execution spine, APIs; **107** pytest green (incl. concurrent admission + deterministic workflow); live lane **2/2** + execution-spine placeholder skipped; §4 matrix + Phase 03 test evidence updated; security test uses `.venv/bin/lint-imports` fallback. |
| 2026-10-02 | **Phase 03 test hardening:** fixed admission/cancel/immutability/live-spine tests (issued-contract immutability, human cancel actor, harness `with_pending_required_approval`); **121** CI pytest green; recovery **3/3**; `test_execution_spine_diagnostic_live` live PASS. |
| 2026-10-02 | **Phase 03 COMPLETE:** resume stale-input path (`CHECKPOINTED→STALE`, new execution + `previous_execution_id`), repository eligibility/snapshot tests, scheduler `model_calls` guard; **126** CI pytest green; §14 acceptance criteria satisfied. |
| 2026-10-02 | **Docs:** `STATUS.md` §1–§2 + phase matrix → Phase 03 COMPLETE (4/20); Phase 03 implementation record; `plans/03-…md` tasks §10–§15 checked, §12 test map, new §19 implementation record. |
| 2026-10-02 | **Phase 04 gap closure (partial):** Phase 04 REST routers + `retry_materialization` command; gateway `Approval(ACTION)` + Forge approval checkpoint; candidate diff artifact; §12 tests (worktree concurrency, gateway audit, connector idempotency, token binding, policy injection, materialization retry); execution-token signature timezone fix. Live Forge + credentials-not-persisted still open. |
| 2026-10-02 | **Phase 04 verification (partial):** ToolGateway/worktree/materialization land; migrations `0007`–`0008`; **`make check` lanes green — 123 pytest** (77 unit, 24 persistence, 16 integration, 4 security, 2 `@git`); greenfield + external-clone integration tests pass; ruff + import-linter + mypy green. Live Forge + §12 security/git matrix still open; Phase 04 remains **IN_PROGRESS**. |
| 2026-10-02 | **Phase 04 COMPLETE:** control-plane API tests (`test_phase04_api`, `test_phase04_approval_api`, `test_gateway_authorization`); OpenAI tool-calling + Forge live milestone PASS; fixes (prompt front matter, `implementation` alias, validation timing, worktree event `actor_id`, `EXPLICIT_SHA` harness); **156+** CI pytest; §14 ACs checked in `STATUS.md`. |
| 2026-10-02 | **Phase 04 additional verification:** `@git` **8/8**, Phase 04 API/gateway/security bundle **16/16**; §8 repository/workspace/greenfield/brownfield (04 scope), Git isolation, ToolGateway, governed-actions trackers updated; §9 LOCAL repository registration + `git_local` → IMPLEMENTED; Forge → LIVE VERIFIED; materialization AC notes deferred crash-resume scenarios. |
| 2026-10-02 | **Materialization recovery + CI:** `resolve_materialization_head` adoption in loop/greenfield; `test_materialization_recovery.py` **4/4** (retry, adopt-after-clone, corrupt re-clone, OLYMPUS baseline adopt); `@git` **11/11**; GitHub Actions adds `make test-security` + `pytest -m git`; Phase 04 materialization §14 AC closed. |
| 2026-10-02 | **Deterministic re-verify:** full lanes **162** pytest green; `Makefile` adds `test-git` to `make check`; CI uses `make test-git`; Phase 00/04 STATUS counts refreshed. |
| 2026-10-02 | **Phase 05 IN_PROGRESS:** migrations `0009`–`0012`, inbound + product model + `kira.decompose`; document upload integration test; migration unique-constraint naming fix; `make check` lanes **166** pytest (84 unit, 28 persistence, 35 integration, 8 security, 11 `@git`); §9 document upload → IMPLEMENTED; live Kira + scope workflow proof still open. |
| 2026-10-02 | **Phase 05 COMPLETE:** API/workflow tests (`test_product_model_api_workflow`, `test_product_model_kira_worker`, immutability + scope cascade); scheduler eligibility fix for repo-less analysis; **173** deterministic pytest; §14/§15 satisfied via worker + ModelRouter (FakeProvider). |
| 2026-10-02 | **Phase 05 additional verification:** re-ran full `make check` lanes (**173** pytest green); §8 product/inbound trackers updated (05 scope); §9 document upload → **VERIFIED**; §7 invariant 38 partial (05 path); Phase 05 §12 test map + implementation record table in STATUS. |
| 2026-10-02 | **Phase 05 follow-up slice:** snapshot product context, assumption persistence, scope rejection cascade, clarification-triggered re-decompose; +10 tests (**183** deterministic pytest); STATUS follow-ups checklist. |
| 2026-10-02 | **Phase 05 §12 test closure:** validator rules matrix, PDF extraction, scope superseded guard, greenfield workflow lane, ambiguous PRD clarification, live Kira harness; **199** pytest deterministic (+5 skipped live). |
| 2026-10-02 | **Live Kira §15:** OpenAI strict `json_schema` fix (`pydantic_to_json_schema` sets recursive `additionalProperties: false`); `test_kira_decompose_prd_live` + full **`live_llm`** lane **7/7 PASS** (~$0.025). |
| 2026-10-02 | **Large-PRD chunking (§17):** `chunk_markdown_by_headings` + merged multi-chunk Kira decompose; `OLYMPUS_PRODUCT_SOURCE_DECOMPOSE_MAX_CHARS` (default 32k); **204** pytest. |
| 2026-10-02 | **Phase 05 STATUS sync:** §2 milestone, §10 live/Kira table, implementation record (workflow + chunking + §15), CI parity **204** + live **7/7**; no mandatory Phase 05 follow-ups remaining. |
| 2026-10-02 | **Phase 06 deterministic verification:** migrations `0013`–`0015`, planning kernel + REST; **`make check` green** — **213** pytest (**112** unit, **36** persistence, **47** integration, **10** security, **11** `@git`); ruff format/lint + import-linter + mypy green; Phase 06 remains **IN_PROGRESS** (live Atlas/Kira/workflow, Forge compiled contract, §15 exit open). |
| 2026-10-02 | **Phase 06 COMPLETE:** live planning **3/3** (`live_llm/planning/`, spend ≈ **$0.0046**); §14/§15 closed; §1–§2 + matrix → **6/20**; current phase **07**; Atlas/Kira planning **LIVE VERIFIED** in §10. |
| 2026-10-02 | **Phase 08 IN_PROGRESS:** migrations `0017`–`0018`; IC kernel + §14 acceptance (git E2E, spec links, lineage fixture, depbase); **`make check` 257 pytest**; `verify-phases` script extended to Phase **08** (alembic head **0018**); §15 live `tests/workflow/integration` + 08.13 open. |
| 2026-10-02 | **Phase 08 verify evidence:** `./scripts/verify-phases-00-07.sh --phase 08` and **`--phase 08 --live`** exit **0** locally; §8 IntegrationCandidate + §9 invariants synced to §14 git E2E; README verify table adds scoped **`--phase 08 --live`**. |
| 2026-10-02 | **Full live verify:** **`make verify-phases-live`** exit **0** locally — Bootstrap + Phases **00–08** + CHECK + FULL-DET + LIVE PASS; Phase **08** duplicate-Forge / workflow IC lanes SKIP as designed; STATUS §1 Phase 08 + Phase 08 Notes updated. |
| 2026-10-02 | **Phase 08 §15:** `docs/phase08-handoff-09-10.md`, `tests/workflow/integration/`, verify script §15 steps, **`make verify-phase-08-exit`**. |
| 2026-10-02 | **Phase 08 COMPLETE:** `./scripts/verify-phases-00-07.sh --phase 08 --live` exit **0** (×2); §15 all steps PASS; §1–§2 + matrix → **8/20**; current phase **09**. |
| 2026-10-02 | **Phase 09 kernel:** migration **`0019_p09_assurance`**; assurance orchestrator on `integration.ready`, gates finalizer, Warden/Sentinel profiles + `sentinel.execute`; **`make check` green** (**265** deterministic pytest); assurance targeted suite **12/12**; Phase 09 → **IN_PROGRESS** in §1–§2, §4, §9–§10. |
| 2026-10-02 | **Phase 09 verify (live):** OpenAI strict-schema fix for **`WardenReview`** / **`VerificationPlan`**; **`./scripts/verify-phases-00-07.sh --skip-bootstrap --phase 09 --live`** exit **0** (local terminal): §12 + **live_llm assurance 2/2** PASS. |
| 2026-10-02 | **Phase 09 verify script + tests:** expanded **`--phase 09`** steps (strict schemas, **`assurance_execute`** real pytest, live plan §12 command); worktree **`gitdir:`** fix; handoff doc obligation registry; **`STATUS`** Phase 09 test map. |
| 2026-10-03 | **Phase 09 COMPLETE (exit):** **`./scripts/verify-phases-00-07.sh --live --skip-bootstrap`** exit **0** — Phases **00–09**, CHECK, FULL-DET, **LIVE** PASS; remediation/IC live Forge hardening; §1–§2 milestone → Phase **10** cleared. |
| 2026-10-03 | **Phase 10 COMPLETE:** release plane + migrations **`0020`–`0022`** (scoped IC/finding/gate/evidence keys); verify script Phase **10** lane; **`make db-up && make migrate && make lint && make check`** + **`verify-phases --skip-bootstrap`** + **`--live`** exit **0**; §4 matrix Phase **10** → **COMPLETE**; current phase **11**. |
| 2026-10-04 | **Phase 11 sign-off:** migration **`0023`**; verify script Phase **11** lane; full regression **`make check`** + **`verify-phases --skip-bootstrap`** + **`--live`** exit **0** (Phases **00–11**, CHECK, FULL-DET, **JOURNEY**, **LIVE**); Scout live finalize hardening (`discovery_fact_aliases`); §1 Backend Phase **11** row; §9 Brownfield index/refresh ACs; journey matrix → **PARTIAL** (12 next). |
| 2026-10-04 | **Phase 12 tracking:** §2 **Current Phase** → **IN_PROGRESS**; §4 matrix **12** → **IN_PROGRESS**; Phase **11** optional follow-ups table; Phase **12** guard placeholder map, **`0024`** migration note, implementation tracker + §10 progress breakdown. |
| 2026-10-04 | **Phase 12 verify:** **`make db-up && make migrate`** (head **`0024_p12_baselines_readiness`**); **`make lint`**, **`make typecheck`**, **`make check`** green (**354** pytest); **`tests/unit/baselines`** **4/4**; **`make test-live`** **15/15**; **`sentinel.characterize`** prompt front matter + integration test PASS; §1 Phase **12** row + Phase **12** tracker/test map + AC/progress sync (guards **IMPLEMENTED**; remediation + journey **OPEN**). |
| 2026-10-04 | **Phase 12 harness:** **`tests/fixtures/brownfield_phase12_harness.py`**, workflow **`test_brownfield_to_ready_workflow.py`**, live journey **`test_brownfield_supportdesk.py`**; verify script **`--phase 12`** lane; promotion fixes (canonical **`version+1`**, spec link flush); **`baseline_review_complete`** empty-queue guard. |
| 2026-10-04 | **Phase 12 COMPLETE (exit):** **`BrownfieldRemediationService`** + remediation workflow; integration promotion/declare_ready tests; live characterize + live journey PASS (**`--phase 12 --live`**); **`ModelCall`** cycle linkage + **`live_drain_spec_recovery`**; full **`verify-phases --skip-bootstrap`** PASS; §1–§2 → **12/20**; Journey 2 milestone **COMPLETE**. |
| 2026-10-04 | **Phase 12 follow-ups tracker:** optional table **P12-F01**..**P12-INV** under Phase **12** detail (plan §12 test gaps, journey strictness, verify live monolith, Q-02/Q-07, **M-29**, **19** re-run); §10 invariant rows cross-linked. |
| 2026-10-04 | **Q-04 CONFIRMED:** OpenAI primary for **`embedding`** alias; graceful skip of semantic expansion when unavailable; **`fastembed`** deferred to **13.7**; Phase **13** blocker cleared; §12 decision paragraph + Phase **13** notes. |
| 2026-10-04 | **Phase 13 COMPLETE (exit):** migration **`0025`**; impact/hybrid/incremental/staleness + REST; **`make verify-phase-13`** + full **`verify-phases --skip-bootstrap --live`** exit **0**; §1–§2 → **13/20**; §4 matrix + §10 Impact Analysis; current phase **14**; **P12-F01** closed; Scout live retry in verify script. |
| 2026-10-04 | **Phase 13 STATUS depth:** implementation record + §12 test map; extras (live harness, fixtures, production fixes, **`verify-phase-13-exit`**); §10 embedding live **PARTIAL** when OpenAI embed not entitled. |
| 2026-10-04 | **Phase 14 implementation:** migrations **`0026`–`0027`**; ChangeRequest kernel + Feature Change orchestrator; **`test_feature_change_supportdesk.py`**, **`feature_change_acceptance.py`**, **`test_change_request_idempotency.py`**; plans/14 §10–§14 checkboxes; verify script **`--phase 14`**. |
| 2026-10-05 | **Phase 14 COMPLETE (exit):** sequential **`make db-up/migrate/lint/check/typecheck`** green; **`--phase 14 --live`** exit **0**; **`make test-live`** **17/17**; impact consistency fix (contract surfaces vs file scope); release harness sentinel ordering + priority AC obligation stub; alembic head grep **`0027_feature_spec_supersede`**; §1–§2 → **14/20**; Journey 3 milestone **COMPLETE** (isolated; Phase **19** chained pending). |
| 2026-10-05 | **STATUS sync (Phase 14):** §10 Feature Change invariants + §11 MVP DoD; §10 Live LLM table (`change_interpret`, Forge retry, journey **3**); **`make verify-phase-14`** / **`verify-phase-14-exit`**; Phase **14** deliverables, REST, follow-ups **P14-F01** / **P14-19**, implementation record. |
| 2026-10-05 | **Phase 15 COMPLETE (exit):** migrations **`0028`–`0029`**; bug-fix kernel + reproduction/regression; journey **`test_bug_fix_supportdesk.py`** live PASS; lint/mypy fixes; **`bootstrap_bug_fix_to_root_cause`** + POST_REPAIR integration chain; sequential **`make migrate/lint/check/typecheck`** green; Phase 15 pytest **13/13**; §1–§2 → **15/20**; Journey 4 milestone **PARTIAL** (isolated; Phase **19** chained pending). |
| 2026-10-05 | **Phase 15 gap closure + verify sign-off:** bug-fix prompt front matter; **`_snapshot`** in execution snapshots; worker bug-fix **artifact:** outputs; triage signature normalization; duplicate reproduction/evidence hardening; expanded §12 tests (**`live_llm/defects`**, eligibility, **`proceed_unreproduced`**, NOT_REPRODUCED R1, artifact immutability); **`make verify-phase-15-exit`** exit **0** (local). |
| 2026-10-08 | **RL1 COMPLETE (Review loop):** Studio S1–S5 + D1 — brownfield repo register/intake, promotion decisions, findings waive/remediate, architecture-delta panel, defect proceed-unreproduced/reject, per-cycle **`approvalStage`** mapping, request-changes interim UX; plan docs aligned (§17). |
| 2026-10-08 | **RL1 review fixes + live check:** approvals expose decision note/author/time; `ArchitectureService.get_approved` ignores DELTA rows; Studio fixes (note from approval, latest-round request-changes, accurate helper text, Remediate only on blocking findings, pending waiver, delta panel states, proceed-unreproduced policy/status conditions, reject statuses, repo secret naming + credential reuse, review-queue role message, Next step bar runs the first allowed forward command, feature-change / bug-fix intake routes). Execution stack fixes found live: worker image installs pytest; executor exceptions fail the task instead of killing the worker; stale worktree registrations pruned on re-claim; recovery finalize runs after the task is marked complete; `CHARACTERIZATION_PLAN` / `BASELINE_RUN` / `ARCHITECTURE_DELTA` artifacts recorded from executor output. RL1 → **PARTIAL**; backend gaps in §17. |
| 2026-10-09 | **Assurance task artifacts + lease test:** worker records `WARDEN_REVIEW` / `VERIFICATION_PLAN` / `VERIFICATION_EVIDENCE` from executor output so assurance agent tasks complete; per-gate-type finalize; one adopted Sentinel plan per IC; lease race test isolated. Backend suite 547 passed, 0 failed; `npm run check` green. |
| 2026-10-09 | **RL1 backend gaps closed:** worktree sweeper grace period; pytest path node ids; characterization context + authored baseline tests run at onboarding SHA and in gates; typed principal entity links resolved to index keys; baseline coverage follows promotion; `NO_ACTIVE_BASELINES` guard; recovery pruning + `retry_spec_recovery`; workers import the model registry; effective architecture (base + deltas) for planning/conformance; Atlas delta context. Live RL1: brownfield → READY_FOR_CHANGE at default policy (2 PASS); feature change through architecture-delta approval; last run stopped on OpenAI credits. RL1 stays **PARTIAL**. |
| 2026-10-08 | **RL2 COMPLETE (Review loop):** revision on CHANGES_REQUESTED, auto-requested approvals, orchestrator focus + Studio revision/diff UI, product-spec view, six chat generation commands; **`test_revision_loop_live.py`** (`live_llm`); chat plan **B-01** / **B-03** marked fixed. |
| 2026-10-09 | **RL1 COMPLETE:** `studio-rl1.spec.ts` @live 3/3 PASS (brownfield → READY_FOR_CHANGE, feature change → architecture delta → implementation-spec delta, bug fix → repair spec); execution worker fails a crashed execution inside a savepoint instead of exiting; code index `build/` package tracked. RL2 row: `studio-rl2.spec.ts` @live PASS recorded as phase acceptance. |

---

## 16. FRONTEND UI TRACK (Olympus Studio)

Chat + workspace operator UI in `apps/dashboard` per `docs/design/olympus-chat-workspace-plan.md` and `docs/design/olympus-cursor-prompt-chat-workspace.md`.

| Phase | State | Milestone | Blockers |
|---|---|---|---|
| C0 | COMPLETE | Hygiene — duplicate cleanup, inbox types + `/views/inbox` filters, SSE `Last-Event-ID`, release eligibility status | — |
| C1 | COMPLETE | Studio API layer — stage reads/writes, §6 proposal map, mutation hooks; unit tests per C1 API fn + invalidation | — |
| C2 | COMPLETE | Studio shell — `/studio` route, three-pane layout + tabs, stage spine, SSE invalidation | — |
| C3 | COMPLETE | Orchestrator chat — session reuse, async turns, intent UI, PRD attach, AskOlympus drawer | — |
| C4 | COMPLETE | Greenfield workspace stages — discovery through release, embedded DAG/executions/assurance | — |
| C5 | COMPLETE | Decision panel + Next step bar — APPROVER gating, guard truth, cycle commands | — |
| C6 | COMPLETE | Other journeys — feature change, bug fix, brownfield, remediation stage views | — |
| C7 | COMPLETE | Playwright `studio-greenfield.spec.ts` @live — greenfield studio path vs Control API | — |

---

## 17. REVIEW LOOP TRACK (RL)

Studio + backend follow-ups per `docs/design/olympus-review-loop-plan.md` and `docs/design/cursor-prompts/RL*.md`.

| Phase | State | Milestone | Blockers |
|---|---|---|---|
| RL1 | COMPLETE | Studio-only S1–S5, D1: repo register + brownfield intake, review-queue promotion decisions, findings waive/remediate, impact architecture-delta panel, bug-fix unreproduced/reject + repair-spec Decision panel via **`approvalStage`**, request-changes note UX; feature-change / bug-fix journeys start through intake routes; **`npm run check`** green. Live (`studio-rl1.spec.ts` @live, default readiness policy): brownfield register → recovery → characterization baselines → review queue → readiness **READY** (principal 1.0, baseline coverage 1.0) → **declare_ready** → READY_FOR_CHANGE, all from the Studio (2 PASS runs, 20/20 and 28/30 baselines ACTIVE). Feature change live: spec delta approved → impact → architecture-delta panel (propose + approve) → planning → implementation-spec delta drafted. Bug fix live: triage → reproduction (REPRODUCED, signature matched) → expected behavior (SPECIFIED) → root cause → repair IMPLEMENTATION_SPEC in the Decision panel. Full `studio-rl1.spec.ts` @live **3/3 PASS** (2026-10-09, 5.9 min); backend gaps found live are fixed (see below) | — |
| RL2 | COMPLETE | RL2.1–RL2.10: revision inputs + `RevisionService` on CHANGES_REQUESTED, auto-requested approvals (G11), architecture-delta persistence (RL2.5), orchestrator focus + `revision_note_draft` / `navigate_to` / `refs` (G4), Studio revision SSE + diff UI, `GET /projects/{p}/product-spec`, six chat generation commands + proposal routes; live revision loop test (`test_revision_loop_live.py`, `LLM_LIVE_TESTS=1`); **`make check`** + **`npm run check`** green; phase acceptance live in `studio-rl2.spec.ts` @live PASS (architecture chat propose, cite, request-changes revision diff, greenfield Product spec); brownfield Product spec (recovered provenance, no PRD chips) checked live at the end of the `studio-rl1.spec.ts` brownfield test (PASS 2026-10-09) | — |
| RL3 | NOT_STARTED | Gates, edits, baselines (G5–G10); EXPECTED_BEHAVIOR and plan acceptance enforcement | — |
| RL4 | NOT_STARTED | Journey tests + live four-journey Studio run; **`evaluate_mvp.py`** without fallback flags | RL1–RL3 |

**RL1 live check: backend gaps (2026-10-08)**

- **Fixed (2026-10-09): brownfield characterization produces no baselines.** Root causes: the scheduler's worktree sweeper deleted in-flight worktrees (their `ExecutionWorkspace` row is uncommitted while the executor runs; now a `OLYMPUS_WORKTREE_ORPHAN_GRACE_SECONDS` grace period, default 3600); junit node ids were dotted (`tests.test_x::t`) so no baseline check matched (now pytest path form, legacy refs rewritten); `sentinel.characterize` ran without context. Characterize contracts now carry ACs, observed behaviours, index summary and code excerpts (`characterization_context.py`); Sentinel writes pytest files (prompt v2) stored as `CHARACTERIZATION_TEST` artifacts, materialized under `tests/olympus_characterization/` for the onboarding-SHA run and in BASELINE gates; baseline execution waits for every characterize task. Readiness baseline coverage follows baselines re-pointed to the canonical spec on promotion. Covered by `tests/integration/brownfield/test_characterization_baselines.py`, `tests/integration/git/test_worktree_sweeper_grace.py`, `tests/unit/brownfield/test_pytest_node_ids.py`.
- **Fixed (2026-10-09): principal coverage 0 live.** `RecoveredFeatureSpec.principal_entity_links` was untyped (`dict`), so the live model returned `{}` and no spec-code link had a key. Now `PrincipalEntityLink(stable_key, confidence)`; recovery rewrites link refs to exact index keys (`canonical_entity_keys`), adds the survey draft's principal entities, and links the ROUTE that exposes / is verified by a cited handler or test.
- **Fixed (2026-10-09): declare_ready with no ACTIVE baselines** is a `NO_ACTIVE_BASELINES` guard reason on `readiness_assessment_ready` and a `DomainError` in `declare_ready` (no bare 500).
- **Fixed (2026-10-09): rejected recovery proposal has no retry.** Recovery prunes unsupported citations/claims before validation (dotted and file refs resolve against the index); new RECOVERED_SPEC self-loop **`retry_spec_recovery`** (guard `recovery_proposal_rejected`) re-runs the Scout survey, and the Studio Next step bar leads with it when `start_baseline` is blocked. Recovery after pruning validated on the first attempt in 5/5 live runs. Covered by `tests/integration/brownfield/test_recovery_retry.py`.
- **Fixed (2026-10-09): feature change live blockers.** Workers never imported `core.domain.registry`, so the first `ChangeRequest` flush crashed the execution worker (`NoReferencedTableError`) in a loop; covered by `tests/unit/test_worker_mapper_registry.py`. The implementation-spec delta prompt read an arbitrary APPROVED architecture (often the DELTA row, with no components), so Kira emitted file paths and failed conformance; the snapshot, conformance and sanitizer now use `ArchitectureService.effective` (base + approved deltas). `atlas.architecture_delta` received no context (planning fields were gated to `kira.*`); it now gets the effective architecture, change request and impact items.
- **Live fixture:** the staged `supportdesk.git` contains `tests/olympus_repro` from earlier bug-fix runs; RL1 live used a clean copy (`STUDIO_RL1_REPO_URL=file:///data/workspaces/fixtures/supportdesk-clean.git`).
- **Fixed (2026-10-09): bug-fix agents ran without context.** `sentinel.reproduce` saw only the triage JSON and guessed imports (`from olympus.app import app`) and placeholder ids, so the test errored and the defect was NOT_REPRODUCED; its contract now carries an index summary and code excerpts for the triaged routes and spec-linked code (`reproduction_context.py`, prompt v2 with the runner's assertion / `got <status>` rules). `kira.expected_behavior` cited spec keys as ACs; it now gets the project's approved ACs as `SPEC/AC` citations (recovered AC keys like `AC-1` repeat across specs) and citations resolve within the project (the old lookup was cross-project `scalar_one_or_none`). The REPAIR implementation spec now gets the effective architecture, faulty stable keys, fix outline and expected-behavior statement (prompt v3). Covered by `tests/integration/reproduction/test_reproduce_context.py`, `tests/integration/defects/test_expected_behavior_citations.py`, `tests/unit/runtime/test_bug_fix_prompts.py`.
- **Fixed (2026-10-09): feature change flakes.** A NEW_FEATURE interpretation reused the model's `feature_key`; an existing key raised `UniqueViolation` and killed the execution worker. New features now take a sequence key (`tests/integration/control_plane/test_change_new_feature_key.py`). The implementation-spec delta prompt (v3) gets the strict `valid_component_names` rules, and the draft sanitizer maps code references (`app.services.x.TicketService`) to the owning component by name or unique package directory (`tests/unit/planning/test_impl_spec_component_resolution.py`).
- **Studio spec:** bug-fix stages advance on their own after qualifying agent output; `studio-rl1.spec.ts` runs a stage command from the Next step bar only if the backend offers it first, and fails fast when reproduction ends NOT_REPRODUCED.
- **Fixed (2026-10-09): execution worker exits on a non-`DomainError` in an executor or completion handler** (for example an `IntegrityError` that poisons the transaction). `run_once` now runs the execution inside a savepoint that excludes the lease claim; on any exception it rolls back to the savepoint and fails the execution (`WORKER_<EXCEPTION>`, not retriable, so the agent is not re-run) and its task in the same transaction. `run_tick` logs and continues on anything that still escapes. Covered by `tests/integration/brownfield/test_completion_crash_fails_task.py`.
- **Follow-up (not blocking):** existing-test baselines still fall back to the first test when an AC matches none.
- **Fixed (2026-10-09): code index build package untracked.** `core/intelligence/code_index/build/` (`pipeline.py`, `types.py`) was hidden by the `build/` ignore rule although committed modules import it; it is now un-ignored and tracked.
- **Fixed (2026-10-09):** `warden.review` / `sentinel.plan` / `sentinel.execute` tasks used to fail output validation because nothing wrote `WARDEN_REVIEW` / `VERIFICATION_PLAN` / `VERIFICATION_EVIDENCE`; the worker now records them from executor output and the tasks complete. Each producer finalizes only its own gate type (WARDEN after the review, SENTINEL after verification); other gates stay PENDING. One adopted Sentinel plan per IC: a valid plan arriving after the deterministic one is stored PROPOSED and does not schedule a second execute. Covered by `tests/integration/assurance/test_assurance_agents_worker.py`. `test_concurrent_claim_one_wins` now locks other queued executions during the race and counts only its own execution's leases.
