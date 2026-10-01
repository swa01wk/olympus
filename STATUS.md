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

**Implementation shape.** Python 3.12 modular monolith (FastAPI, Pydantic v2, SQLAlchemy 2 + Alembic, PostgreSQL 16 + pgvector) with separate scheduler and execution worker processes. AgentRuntime is a LangGraph adapter, and ModelRouter calls live providers. Git worktrees isolate execution, and a ToolGateway governs actions. The Code Intelligence index is a Python AST index. The dashboard is a thin Next.js client. The full sequence is 20 phases (00–19).

**Repository reality at planning time** (basis for every state below):

| Item | Observation |
|---|---|
| Git | Branch `main`, **no commits**. Remote `origin = git@github.com:swa01wk/olympus.git` is **unreachable** (`Permission denied (publickey)` over SSH, both inside and outside the sandbox; HTTPS requires credentials). |
| Content | The two `.docx` source documents, `plans/`, this file, Phase **00** scaffold (Python backend: `core/`, `apps/control_api`, worker skeletons, Alembic baseline, tests, CI). Untracked `apps/dashboard/` (Phase 17) may also be present locally. |
| Backend (Phase 00) | **Present (uncommitted):** packaging, settings, async SQLAlchemy, Alembic `0000_p00_baseline`, `/health` + `/ready`, JSON logging + correlation IDs, worker noop loops, pytest lanes, import-linter, Docker Compose postgres. **No domain entities yet.** |
| Remaining MVP surface | Domain kernel, agents/runtime, ToolGateway, journeys, dashboard integration, etc. — still **ADD** per phases 01–19. |
| Conflicts with target architecture | None (nothing to conflict with). Risk R-REMOTE: if `origin/main` has content, Phase 00 task 00.1 re-runs the assessment before any code is written. |

---

## 2. OVERALL STATUS

| Field | Value |
|---|---|
| **Overall State** | `IN_PROGRESS` |
| **Current Phase** | Phase 01 — Domain Model and Control Plane Kernel (ready to start). |
| **Current Milestone** | Phase 01: command-driven lifecycle kernel with atomic audit. |
| **Last Completed Phase** | Phase 00 — Foundation and Repository Scaffold |
| **Next Phase** | Phase 01 — Domain Model and Control Plane Kernel |
| **Overall Completion** | **1 / 20 phases** |
| **Planning artifacts** | `plans/README.md` (incl. D-16/D-17 and §5.9 repository ownership) + 20 phase files + `STATUS.md` (complete) |

Allowed Overall State values: `NOT_STARTED | IN_PROGRESS | BLOCKED | MVP_COMPLETE`. `MVP_COMPLETE` may be set only by Phase 19 under its §15 exit criteria.

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
Phase 17  Dashboard │  Phase 18  Observability, security,
& Orchestrator      │  recovery hardening
   │  (parallel path P4: both depend only on 16)
   ↓ ───────────────┘
Phase 19  Final four-journey E2E & MVP acceptance       ← MVP exit gate
```

| Parallel path | Phases | Technical justification | Coordination rule |
|---|---|---|---|
| P1 | 07 alongside 02→03→04/05→06 | 07 needs only the Phase 01 `Repository` entity. It is pure deterministic parsing with no shared modules (`core/intelligence/code_index` vs `core/runtime`, `core/scheduler`, `core/execution`, `core/tools`, `core/product_model`, `core/planning`). | 07 must be COMPLETE before 08 starts. Rebase the Alembic `down_revision` at merge (README §5.8). |
| P2 | 04 alongside 05 | Both depend only on 03. Their modules are disjoint (`core/tools`, `core/execution/worktrees`, `agents/forge` vs `core/product_model`, `core/integrations/inbound`, `agents/kira`). Kira needs no ToolGateway tools. | Both must be COMPLETE before 06. Linearize migrations 0007–0012. |
| P3 | 14 alongside 15 | Both depend only on 13 and own disjoint packages (`core/product_model/changes` vs `core/product_model/defects`, `core/assurance/reproduction`). | Serialize merges of `core/release/eligibility.py`, `core/release/service.py`, `core/assurance/obligations.py` and the migration chain. |
| P4 | 17 alongside 18 | Both depend only on 16. 17 owns `apps/dashboard`, read models and `agents/orchestrator`; 18 owns telemetry, security and recovery in `core/*`. | Coordinate on auth middleware; linearize migrations 0027/0028. |

There are no other parallel paths. Phases 08→13 and 16→19 are strictly serial because each consumes the previous phase's frozen contracts. Phase 10 → 11 is serialized by ARCH §2 (vertical-slice delivery: complete one journey before expanding breadth).

---

## 4. PHASE DEPENDENCY MATRIX

| Phase | Name | Depends On | Blocks | Parallel With | State |
|---|---|---|---|---|---|
| 00 | Foundation and Repository Scaffold | — | 01 (and all) | — | COMPLETE |
| 01 | Domain Model and Control Plane Kernel | 00 | 02, 03, 07, all later | — | NOT_STARTED |
| 02 | ModelRouter, AgentRuntime and Live LLM Infrastructure | 01 | 03, all agent phases | 07 | NOT_STARTED |
| 03 | Scheduler, Execution, Snapshot, Lease and Execution Worker | 01, 02 | 04, 05 | 07 | NOT_STARTED |
| 04 | Git Worktrees, ToolGateway, Governed Actions and Connector Framework | 02, 03 | 06, 08, 09, 10, 11, 16 | 05, 07 | NOT_STARTED |
| 05 | Product Source Intake, Inbound Event Kernel and Product Model | 03 | 06 | 04, 07 | NOT_STARTED |
| 06 | Architecture, ImplementationSpec, Task Planning and TaskContract Compiler | 04, 05 | 08 | 07 | NOT_STARTED |
| 07 | Code Intelligence Index (Deterministic, Python-First) | 01 | 08, 11 | 02, 03, 04, 05, 06 | NOT_STARTED |
| 08 | IntegrationCandidate, Canonical Index Promotion and Product-to-Code Traceability | 04, 06, 07 | 09 | — | NOT_STARTED |
| 09 | Assurance: Evidence, Verification Obligations, Warden, Sentinel, Gates and Remediation Loop | 08 | 10 | — | NOT_STARTED |
| 10 | Release Eligibility, Release Manifest and the Greenfield Journey (R1) | 09 | 11 | — | NOT_STARTED |
| 11 | Brownfield Repository Discovery, Observed Behavior and Recovered Specifications | 10 (and 07, 08, 09) | 12 | — | NOT_STARTED |
| 12 | Behavioral Baselines, Human Promotion, Readiness, Remediation and READY_FOR_CHANGE | 11 (and 09, 10) | 13 | — | NOT_STARTED |
| 13 | Specification Delta, Impact Engine, Hybrid Retrieval, Incremental Re-index and Staleness | 12 (and 05, 06, 07, 08) | 14, 15 | — | NOT_STARTED |
| 14 | Feature Change Journey (R2) | 13 | 16 | 15 | NOT_STARTED |
| 15 | Bug Fix Journey (R3) | 13 | 16 | 14 | NOT_STARTED |
| 16 | External Integrations: Inbound Adapters, Outbound Connectors and Reconciliation | 14, 15 (and 04, 05, 10, 13) | 17, 18 | — | NOT_STARTED |
| 17 | Dashboard, Operator Experience and Orchestrator | 16 | 19 | 18 | NOT_STARTED |
| 18 | Observability, Security and Recovery Hardening | 16 (and 02–15) | 19 | 17 | NOT_STARTED |
| 19 | Final Four-Journey E2E and MVP Acceptance | 17, 18 (transitively 00–16) | — | — | NOT_STARTED |

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
- [x] The CI `deterministic` job definition runs lint, typecheck, unit, persistence and integration with a PostgreSQL service.
- [x] No domain tables exist yet (only the baseline migration).
- [x] `OLYMPUS_WORKSPACE_ROOT` is a required settings field, resolved to an absolute writable directory at startup. It is configuration only and is never persisted in a domain row (README D-16, §5.9.2).

Progress:
- [x] 00.1 Remote divergence check resolved (R-REMOTE): fetch unreachable; no local commits to diverge from.
- [x] 00.2–00.4 Packaging, `.gitignore`, `.env.example`.
- [x] 00.5–00.10 Settings (incl. `OLYMPUS_WORKSPACE_ROOT`), DB layer, Alembic baseline, logging/correlation, `/health` + `/ready`, worker skeletons.
- [x] 00.11–00.14 Package tree, compose/Docker/Make, lint/type/import contracts, test harness.
- [x] 00.15–00.17 Smoke tests, CI, root README.
- [ ] 00.18 First commit on `main` (pending; scaffold is uncommitted).
- [x] §12 commands green (`make check` + plan §12 smoke commands above).
- [x] §14 acceptance criteria verified (see table).
- [ ] §15 exit criteria: **first commit on `main` (00.18)** still pending — working tree uncommitted.

Blockers:
- None for implementation. **Exit:** commit Phase 00 scaffold to `main` when ready (00.18).

Notes:
- Do not modify the two `.docx` files. PostgreSQL is mandatory (D-01).

### Phase 01 — Domain Model and Control Plane Kernel

Status: NOT_STARTED

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

Milestone Status: NOT_STARTED

Key Deliverables:
- `core/domain/*` (incl. `repositories`, `repository_workspaces`, `repository_revisions`), `core/repositories/{service,revision,workspace_locator}`, `core/state/*`, `core/commands/*`, `core/policy/*`, outbox + SSE, auth, routers, `seed_actor` CLI
- Migrations `0001`–`0004` (incl. `olympus_forbid_mutation()` trigger, `delivery_cycle_events` view)
- `config/policy/default.yaml`

Acceptance Criteria:
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

Progress:
- [ ] 01.1–01.8 Canonical JSON, models, migrations 0001–0004, immutability triggers, `delivery_cycle_events` view.
- [ ] 01.9–01.11 State machines as data, fail-closed GuardRegistry, TransitionService.
- [ ] 01.12–01.16 CommandBus + idempotency, Task/Contract/Approval/Policy services.
- [ ] 01.17–01.19 Outbox + SSE, bearer auth + routers, Repository / RepositoryWorkspace / revision services + LOCAL registration.
- [ ] 01.20 §12 suites green; §14 verified; §15 exit criteria verified.

Blockers:
- None.

Notes:
- Guards owned by later phases are fail-closed `RequiredGuard` placeholders until those phases replace them.

### Phase 02 — ModelRouter, AgentRuntime and Live LLM Infrastructure

Status: NOT_STARTED

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

Milestone Status: NOT_STARTED

Key Deliverables:
- `core/runtime/{model_router,model_policy,structured_output,usage,budget,agent_runtime,langgraph_runtime,agent_profiles,tool_client}.py`, providers, prompt registry
- Migration `0005` (`model_calls`); `config/models.yaml`, `config/model_pricing.yaml`
- `tests/plugins/live_guard.py`; CI `live` job

Acceptance Criteria:
- [ ] All model selection goes through aliases, and no model ID literal appears outside `config/`.
- [ ] A live structured-output call succeeds and is persisted with `provider_request_id`, tokens and cost.
- [ ] Schema-invalid output is retried with validation feedback up to the bound, then fails with a persisted record.
- [ ] Transient, rate-limit and auth errors are classified and retried or failed according to policy (unit-tested with FakeProvider).
- [ ] Budget enforcement blocks calls that would exceed the configured budget.
- [ ] `FakeProvider` cannot be constructed when `OLYMPUS_ENV` is `integration` or `journey`.
- [ ] `--live-required` turns skipped live tests into failures.
- [ ] `LangGraphRuntime` supports run, stream, cancel and resume. Resume works after LangGraph checkpoint tables are truncated.
- [ ] No secrets appear in logs or `model_calls`.

Progress:
- [ ] 02.1–02.3 `model_calls` + migration, model/pricing config, alias policy.
- [ ] 02.4–02.9 Providers, structured-output loop, transport retry, usage/budget, `ModelRouter.invoke/embed`.
- [ ] 02.10–02.15 Prompt registry, runtime contracts, LangGraphRuntime, ToolGatewayClient protocol, FakeProvider guard, diagnostic profile.
- [ ] 02.16–02.17 `live_guard` plugin + CI live job; tests.
- [ ] Live suite passed with real credentials (record run ID/cost below); §14 and §15 verified.

Blockers:
- Provider credentials (`ANTHROPIC_API_KEY`; `OPENAI_API_KEY` if Q-04 selects OpenAI embeddings) must be provisioned before the live suite can run.

Notes:
- Q-03 (alias set) and Q-04 (embedding provider) are relevant.

### Phase 03 — Scheduler, Execution, Snapshot, Lease and Execution Worker

Status: NOT_STARTED

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

Milestone Status: NOT_STARTED

Key Deliverables:
- `core/scheduler/*`, `core/execution/{service,worker,snapshots,leases,executors,validation,checkpoints,continuation,resume}`
- Migration `0006`; execution/clarification/artifact APIs and events

Acceptance Criteria:
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

Progress:
- [ ] 03.1–03.3 Models + migration 0006, Execution machine, RefResolver registry.
- [ ] 03.4–03.8 Eligibility, admission, BaseCommitResolver, SnapshotBuilder, LeaseManager + sweeper.
- [ ] 03.9–03.12 ArtifactStore, executors, output validators, worker flow.
- [ ] 03.13–03.16 Checkpoint/clarification/resume, retry + unblocking, APIs, tests (incl. live diagnostic run).
- [ ] Live suite evidence recorded; §14 and §15 verified.

Blockers:
- None.

Notes:
- Multi-dependency base resolution is intentionally deferred to Phase 08 (`BASE_RESOLVER_UNAVAILABLE`).

### Phase 04 — Git Worktrees, ToolGateway, Governed Actions and Connector Framework

Status: NOT_STARTED

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

Milestone Status: NOT_STARTED

Key Deliverables:
- `core/execution/worktrees/*`, `core/repositories/{materialization,materialization_loop,connectors,credentials}`, `core/tools/*` (gateway, catalog, handlers, policy), `core/integrations/connectors/{base,registry,git_local}`
- `agents/forge/*`; migrations `0007`–`0008`; `execution_workspaces`; candidate commits; action APIs

Acceptance Criteria:
- [ ] Every writable execution runs in its own ExecutionWorkspace (Git worktree). The canonical RepositoryWorkspace's protected refs and `canonical_commit` are never modified by an execution.
- [ ] Concurrent writable executions use different worktrees and branches.
- [ ] A `GREENFIELD_MANAGED` repository is provisioned (bare repository plus baseline commit) by governed SYSTEM actions, and its baseline SHA is recorded as `registered_sha`/`canonical_commit` (revision #1 `MATERIALIZED`).
- [ ] An `EXTERNAL_CLONE` repository is cloned into the canonical RepositoryWorkspace. Its default branch is resolved, its exact HEAD SHA is captured and recorded, it is validated against the materialization policy, and the external source is never written.
- [ ] Materialization is idempotent and crash-resumable. Failures leave the Repository in ERROR with a reason, and code-needing work stays blocked until a retry succeeds.
- [ ] Workspace physical paths derive only from `OLYMPUS_WORKSPACE_ROOT` through `WorkspaceLocator`. Relocating the root requires no DB change.
- [ ] Repository credentials are resolved from `credential_ref` only inside connector subprocesses, and never appear in DB rows, Git config, remote URLs, logs or API responses.
- [ ] A candidate commit never changes `Repository.canonical_commit`, the default branch or the revision history.
- [ ] ToolGateway persists an ActionRequest, decision and result for 100% of tool calls, including reads.
- [ ] Writes outside `allowed_scope`, path traversal, symlink escapes and `.git` access are denied with recorded reasons.
- [ ] A tool not in `AgentProfile.allowed_tools` **or** `contract.allowed_actions` is denied.
- [ ] Implementation agents cannot write `main`, `release/*` or tags. Release-resource actions are denied for Forge.
- [ ] An approval-required action creates an Approval(ACTION) and checkpoints the execution, and proceeds only after APPROVED.
- [ ] Connector actions with the same idempotency key produce a single effect.
- [ ] The candidate commit records sha, parent, base, changed files and diff artifact, and its trailers reference execution, task and contract version.
- [ ] The live Forge milestone passes with real provider model calls (no mocked model output).
- [ ] Execution tokens are run-scoped and invalid after lease loss or completion.

Progress:
- [ ] 04.1–04.3 GitCli allowlist, WorktreeManager + `execution_workspaces`, execution tokens; materialization service + loop.
- [ ] 04.4–04.8 Path confinement, shell policy, tool catalog/handlers, action policy, ToolGateway.
- [ ] 04.9–04.11 Connector protocol + registry, `git_local`, GatewayToolClient binding.
- [ ] 04.12–04.16 Forge profile/graph, candidate commit persistence, worktree wiring, routes, tests (TECH Appendix B live milestone).
- [ ] Live Forge evidence recorded; §14 and §15 verified.

Blockers:
- None.

Notes:
- Satisfies TECH Appendix B (first implementation milestone) together with Phases 00–03.

### Phase 05 — Product Source Intake, Inbound Event Kernel and Product Model

Status: NOT_STARTED

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

Milestone Status: NOT_STARTED

Key Deliverables:
- `core/integrations/inbound/*`, `core/product_model/{sources,capabilities,features,specifications}`, `agents/kira` (`kira.decompose`)
- Migrations `0009`–`0012`; `tests/fixtures/supportdesk/PRD.md` (includes the closed-ticket 409 rule)

Acceptance Criteria:
- [ ] ProductSource versions are immutable and content-addressed. A duplicate upload creates no new version.
- [ ] Every inbound upload produces an `inbound_events` row with correlation ID, idempotency handling and audit.
- [ ] Kira decomposition runs as an Execution through the live ModelRouter path.
- [ ] Invalid proposals are rejected by the deterministic validator before any canonical row is written.
- [ ] Every persisted FeatureSpec has ≥1 Requirement and ≥1 mandatory AC with an `evidence_requirement`.
- [ ] Open questions become Clarifications. Answers become DECISION KnowledgeItems and feed re-decomposition.
- [ ] Scope approval is an explicit HUMAN Approval pinned to a scope-set hash, and it atomically approves the FeatureSpecs.
- [ ] Approved FeatureSpecs are immutable. Edits create new versions.
- [ ] `start_architecture` is blocked until scope is approved and blocking clarifications are resolved.
- [ ] Kira has no write path to the DB (the import-linter contract passes).

Progress:
- [ ] 05.1–05.4 Migrations, inbound kernel, document upload adapter, ProductSource versioning.
- [ ] 05.5–05.6 Product model services, SupportDesk PRD fixture.
- [ ] 05.7–05.10 `kira.decompose`, proposal validator, proposal persistence, re-decomposition after clarification.
- [ ] 05.11–05.15 Scope sets + Approval(SCOPE), guards, RefResolvers, routes, tests.
- [ ] Live Kira evidence recorded; §14 and §15 verified.

Blockers:
- None.

Notes:
- Can run in parallel with Phase 04 (path P2).

### Phase 06 — Architecture, ImplementationSpec, Task Planning and TaskContract Compiler

Status: NOT_STARTED

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

Milestone Status: NOT_STARTED

Key Deliverables:
- `core/planning/*` (architecture, implementation specs, task plan validator, contract compiler), `agents/atlas`, Kira planning profiles
- Migrations `0013`–`0015`

Acceptance Criteria:
- [ ] Architecture and ImplementationSpec are distinct, versioned entities. APPROVED versions are immutable.
- [ ] An ImplementationSpec that references components, paths or contracts not in the Architecture is rejected as `ARCHITECTURE_DELTA_REQUIRED`.
- [ ] An invalid or cyclic TaskPlan is rejected before any Task becomes READY.
- [ ] Every mandatory AC of every in-scope FeatureSpec is covered by ≥1 Task.
- [ ] Every CODE_CHANGE Task references an APPROVED ImplementationSpec, and manual issue of such contracts is rejected.
- [ ] Compiler output is deterministic (identical hash for identical inputs) and involves no model call.
- [ ] Greenfield `start_planning` is rejected until the `GREENFIELD_MANAGED` repository is READY with its recorded baseline SHA. On success, `delivery_cycles.base_sha` is pinned to that canonical SHA, and the repository's provisioning ActionRequests are audited SYSTEM actions.
- [ ] Atlas, Kira ImplementationSpec and Kira TaskPlan run through the live ModelRouter path.
- [ ] Snapshots of planned tasks include Architecture and ImplementationSpec versions.

Progress:
- [ ] 06.1–06.4 Migrations, Architecture + Atlas, architecture approval, Greenfield repository precondition (`start_planning` + pinned `base_sha`).
- [ ] 06.5–06.7 ImplementationSpec + Kira profile, conformance validator, approval.
- [ ] 06.8–06.12 TaskPlan + validator + acceptance, TaskContractCompiler, CODE_CHANGE issue guard, plan guard.
- [ ] 06.13–06.15 RefResolvers + snapshot extension, routes, tests.
- [ ] Live Atlas/Kira evidence recorded; §14 and §15 verified.

Blockers:
- None.

Notes:
- The Phase 04 Forge live test migrates to compiled contracts here.

### Phase 07 — Code Intelligence Index (Deterministic, Python-First)

Status: NOT_STARTED

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

Milestone Status: NOT_STARTED

Key Deliverables:
- `core/intelligence/code_index/{parsers,entities,relations,retrieval}`, `git_source` reader
- Migration `0016`; `tests/fixtures/repos/supportdesk_r1/` golden fixture; code search/entity APIs

Acceptance Criteria:
- [ ] Index content is reproducible: the same `(repository, sha)` gives an identical `content_hash`.
- [ ] Every CodeIndexVersion records the exact `commit_sha`, `kind` and `source`. CANDIDATE and CANONICAL are distinguishable in schema and API.
- [ ] The golden `supportdesk_r1` index matches all expected entities and relations.
- [ ] The route → handler → service → repository → model → table chain is traversable for every SupportDesk route.
- [ ] Test entities are linked via `VERIFIED_BY` to the symbols and routes they exercise.
- [ ] Every retrieval result includes `retrieval_source`, `index_version_id`, `commit_sha` and provenance.
- [ ] Repository code is never executed or imported during indexing.
- [ ] READY index versions are immutable.
- [ ] Indexes are built from Git objects of the Repository's canonical RepositoryWorkspace at the exact SHA. Uncommitted working-tree content is never indexed, and no source-file bodies are persisted in index tables.
- [ ] Only CANDIDATE versions can be created outside Phase 08's `CanonicalIndexService`.

Progress:
- [ ] 07.1–07.3 Migration 0016, `git_source`, `supportdesk_r1` fixture + `materialize_fixture_repository`.
- [ ] 07.4–07.7 AST extraction, imports (incl. external classification), calls, inherits.
- [ ] 07.8–07.12 FastAPI, Pydantic, SQLAlchemy, pytest extractors; Git metadata.
- [ ] 07.13–07.16 CodeIndexer orchestration, retrieval, routes, golden/determinism tests.
- [ ] §14 and §15 verified.

Blockers:
- None.

Notes:
- Parallel path P1: may start as soon as Phase 01 is COMPLETE. No LLM dependency.

### Phase 08 — IntegrationCandidate, Canonical Index Promotion and Product-to-Code Traceability

Status: NOT_STARTED

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

Milestone Status: NOT_STARTED

Key Deliverables:
- `core/integration/*`, `core/traceability/{spec_code_links,lineage}`, canonical index service, FindingPolicy
- Migrations `0017`–`0018`; IC, lineage and code-link APIs

Acceptance Criteria:
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

Progress:
- [ ] 08.1–08.5 Migrations, IC ordering, IntegrationService, `integration.merge` executor, conflict handling.
- [ ] 08.6–08.9 FindingPolicy, candidate index + entity diff, canonical promotion, principal-symbol GENERATED_LINEAGE.
- [ ] 08.10–08.15 DependencyBaseResolver, LineageService, guards, compiler context, routes, tests.
- [ ] Live workflow precursor evidence recorded; §14 and §15 verified.

Blockers:
- None.

Notes:
- Requires Phase 07 COMPLETE (end of parallel path P1).

### Phase 09 — Assurance: Evidence, Verification Obligations, Warden, Sentinel, Gates and Remediation Loop

Status: NOT_STARTED

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

Milestone Status: NOT_STARTED

Key Deliverables:
- `core/assurance/{evidence,obligations,coverage,gates,findings,remediation,workspace}`, `agents/warden`, `agents/sentinel`
- Migration `0019`; evidence/coverage/findings/gates APIs

Acceptance Criteria:
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

Progress:
- [ ] 09.1–09.4 Migration, EvidenceService + allowed types, ObligationService, coverage.
- [ ] 09.5–09.9 Verification workspace, `test.run` / `test.run_probe`, Sentinel plan/execute/summarize.
- [ ] 09.10–09.11 Warden profile + finding policy, pure gate finalizer.
- [ ] 09.12–09.18 Assurance orchestrator, remediation, waivers, guards, lineage hops, routes, tests.
- [ ] Live Warden/Sentinel + remediation workflow evidence recorded; §14 and §15 verified.

Blockers:
- None.

Notes:
- Guardrail: `MODEL_ASSESSMENT` / `STATIC_REVIEW` evidence never satisfies a mandatory AC that requires executable evidence.

### Phase 10 — Release Eligibility, Release Manifest and the Greenfield Journey (R1)

Status: NOT_STARTED

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

Milestone Status: NOT_STARTED

Key Deliverables:
- `core/release/*`, `agents/stratos/*`; migration `0020`
- `tests/journey/{conftest,helpers}.py` (`assert_live_llm_proof`), `tests/journey/test_greenfield_supportdesk.py`, `scripts/demo/greenfield.py`

Acceptance Criteria:
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

Progress:
- [ ] 10.1–10.5 Migration, eligibility registry + conditions, recompute triggers, manifest, Release lifecycle + Approval(RELEASE).
- [ ] 10.6–10.9 `stratos.release`, released pointer + DeliveryOutcome + COMPLETE, guard, lineage hop.
- [ ] 10.10–10.12 Journey harness, Greenfield journey test, demo script.
- [ ] Greenfield journey run recorded (run ID, cost, duration); §14 and §15 verified.

Blockers:
- None.

Notes:
- Recommended live budget is at least $15 for the full Greenfield journey (record the observed cost).

### Phase 11 — Brownfield Repository Discovery, Observed Behavior and Recovered Specifications

Status: NOT_STARTED

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

Milestone Status: NOT_STARTED

Key Deliverables:
- `core/intelligence/{repository,recovered_specs}`, ObservedBehaviorService, ScoutContextBuilder, RecoveryValidator, RecoveryReconciliationService, `agents/scout`
- Migration `0021`

Acceptance Criteria:
- [ ] Brownfield runs from durable repository/project state only. The context manifest proves no prior product model, other-cycle artifact or runtime history was used.
- [ ] The external repository is registered as `EXTERNAL_CLONE`, with credentials resolved only through the connector/credential provider. It is cloned into the canonical RepositoryWorkspace by the shared Phase 04 materializer, and the exact HEAD SHA of the resolved default branch is captured as `registered_sha = canonical_commit`.
- [ ] Code Intelligence indexes the cloned SHA, and discovery, observed behaviors, existing-test runs and Scout reads are all bound to that exact SHA (`cycle.base_sha`).
- [ ] A fresh runtime (new workspace root, new processes, truncated LangGraph state) can re-materialize the repository at the registered SHA and reconstruct identical repository understanding from durable state.
- [ ] FACT items are produced only by deterministic discovery/derivation. Scout output cannot create FACTs.
- [ ] Every INFERENCE and recovered AC cites ≥1 resolvable fact, behavior, code entity or test.
- [ ] UNCERTAINTIES are persisted with a blocking suggestion (blocking is finally decided by policy in 12).
- [ ] Recovered entities are PROPOSED with `spec_kind=RECOVERED` / `origin=RECOVERED`, never APPROVED or CANONICAL.
- [ ] Persisted confidence never exceeds the deterministic evidence cap, and the claimed vs persisted values are both visible.
- [ ] DISCOVERED SpecCodeLinks carry confidence and evidence refs and are distinguishable from GENERATED_LINEAGE.
- [ ] ObservedBehavior, RecoveredSpec and (future) CanonicalSpec are distinct records.
- [ ] Scout runs through the live ModelRouter path in readonly workspaces.
- [ ] Repository prompt-injection text cannot change any authoritative state.

Progress:
- [ ] 11.1–11.5 Migration, `EXTERNAL_CLONE` registration + shared Phase 04 materializer, deterministic discovery, CODE_INDEX stage, existing-test executor.
- [ ] 11.6–11.7 ObservedBehavior derivation, Scout context isolation + manifest.
- [ ] 11.8–11.12 Scout profiles, RecoveryValidator (no-FACT, citations, caps), persistence, reconciliation.
- [ ] 11.13–11.15 Guards, routes, tests.
- [ ] Live Scout evidence recorded; §14 and §15 verified.

Blockers:
- None.

Notes:
- Brownfield must not depend on Greenfield conversation or LangGraph history (prompt invariant; ARCH §16).

### Phase 12 — Behavioral Baselines, Human Promotion, Readiness, Remediation and READY_FOR_CHANGE

Status: NOT_STARTED

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

Milestone Status: NOT_STARTED

Key Deliverables:
- `core/intelligence/baselines/*`, PromotionService, ReadinessService, BaselineSet; `sentinel.characterize`
- Migration `0022`; `tests/journey/test_brownfield_supportdesk.py`

Acceptance Criteria:
- [ ] Every ACTIVE baseline has executable evidence PASS at its `established_sha`.
- [ ] A RecoveredSpec becomes CANONICAL only through an explicit HUMAN Approval(PROMOTION). No auto-promotion path exists.
- [ ] HUMAN_CONFIRMED links retain references to their DISCOVERED origin and evidence.
- [ ] Recovered behavior rejected as "not intended" never becomes canonical.
- [ ] Readiness is a deterministic, persisted assessment with metric thresholds from policy.
- [ ] NOT_READY with remediable gaps drives REMEDIATION through the standard Task, Contract, Forge, IC, gates and release path.
- [ ] `declare_ready` atomically creates a BaselineSet and sets `READY_FOR_CHANGE`.
- [ ] The Brownfield journey test passes live from a fresh context (no Greenfield conversation or runtime history).
- [ ] BASELINE obligations and the baseline release condition are active for FEATURE_CHANGE/BUG_FIX cycles.
- [ ] Greenfield releases promote passing mandatory ACs to baselines (policy-controlled).
- [ ] READY_FOR_CHANGE is declared only while `Repository.canonical_commit` equals the SHA at which the ReadinessAssessment and the ACTIVE baselines were evaluated. A canonical revision change in between (remediation IC, external sync) forces reassessment.

Progress:
- [ ] 12.1–12.5 Migration, baseline proposals, `sentinel.characterize`, safe probes, baseline execution at SHA.
- [ ] 12.6–12.7 PromotionService, baseline activation.
- [ ] 12.8–12.10 ReadinessService, remediation loop, BaselineSet + `declare_ready`.
- [ ] 12.11–12.15 BASELINE obligation source/gate, Greenfield release promotion, guards, routes, Brownfield journey.
- [ ] Brownfield journey run recorded; §14 and §15 verified.

Blockers:
- None.

Notes:
- Q-08 (remediation publication consumes a release key) is relevant.

### Phase 13 — Specification Delta, Impact Engine, Hybrid Retrieval, Incremental Re-index and Staleness

Status: NOT_STARTED

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

Milestone Status: NOT_STARTED

Key Deliverables:
- `core/intelligence/impact/*`, `core/intelligence/code_index/retrieval` (hybrid + embeddings), incremental indexer, link refresh, StalenessService
- Migration `0023` (incl. HNSW index)

Acceptance Criteria:
- [ ] SpecDelta is computed deterministically between FeatureSpec versions, is immutable, and its approval is hash-pinned.
- [ ] Impact is resolved primarily through SpecCodeLinks and CodeRelations, with recorded paths for every item.
- [ ] Every impact item records `retrieval_source` (STRUCTURAL/LEXICAL/SEMANTIC) and confidence.
- [ ] Only STRUCTURAL items create verification obligations. Each obligation records why it was chosen.
- [ ] Impacted baselines are selected and the policy floor is applied.
- [ ] Incremental re-index equals the full rebuild hash for tested changes.
- [ ] After re-index, changed entities and SpecCodeLinks reflect the new SHA before assurance. Missing principal symbols produce STALE links and Findings.
- [ ] StalenessService marks tasks, executions and baselines STALE/REVALIDATION_REQUIRED on authoritative input changes.
- [ ] A canonical revision change (`repository.canonical_advanced` / `.canonical_reverted`) marks impacted TaskContracts, Executions, candidate indexes, ImpactAssessments and baselines of other open cycles with cause `CANONICAL_REVISION_CHANGED`. A cycle whose base diverged from the canonical revision is blocked until it is explicitly rebased.
- [ ] An architecture delta is either approved or explicitly declined by a human before planning when suggested.
- [ ] The semantic retrieval path uses the live `embedding` alias and degrades gracefully when unavailable.

Progress:
- [ ] 13.1–13.3 Migration, SpecDelta, ImplementationSpec DELTA + conformance re-check.
- [ ] 13.4–13.8 Traversal, test/baseline selection, lexical gating, EmbeddingService, HybridRetrieval.
- [ ] 13.9–13.10 Architecture-delta heuristic, ImpactAssessment + obligation hooks.
- [ ] 13.11–13.16 Incremental index + equivalence, link refresh, StalenessService, guards, routes, tests.
- [ ] Embedding decision (Q-04) recorded; §14 and §15 verified.

Blockers:
- Q-04 must be decided before this phase starts.

Notes:
- Semantic retrieval never creates obligations and never replaces structural lineage.

### Phase 14 — Feature Change Journey (R2)

Status: NOT_STARTED

Plan:
`plans/14-feature-change-journey.md`

Objective: ChangeRequest intake through the inbound kernel, then:
- live `kira.change_interpret` → FeatureSpec v(n+1) + approved SpecDelta;
- graph-derived impact → optional live Atlas architecture delta → ImplementationSpec delta → impact-bounded TaskPlan and contracts;
- live Forge → IC → incremental re-index;
- new ACs plus impacted baselines verified → **Release R2** (**Journey 3**).

Dependencies: 13.

Milestone: **Journey 3 complete.** The change request "Add ticket priority: LOW, MEDIUM, HIGH" is resolved by live Kira to the existing SupportDesk feature and becomes an approved, versioned FeatureSpec delta. Graph-derived impact analysis bounds an approved ImplementationSpec delta and task scopes. Live Forge produces the code delta, which is integrated and incrementally re-indexed with refreshed lineage. New ACs and every impacted baseline pass against the exact integrated SHA, and a deterministically eligible, human-approved **Release R2** is produced with BaselineSet B2.

Milestone Status: NOT_STARTED

Key Deliverables:
- `core/product_model/changes`, `kira.change_interpret`, `atlas.architecture_delta`, feature-change orchestrator, AC_REVALIDATION obligation source
- Migration `0024`; `tests/journey/seed.py`, `tests/journey/test_feature_change_supportdesk.py`

Acceptance Criteria:
- [ ] A ChangeRequest is ingested idempotently through the inbound kernel and linked to exactly one FEATURE_CHANGE cycle.
- [ ] The change creates FeatureSpec v(n+1) and a hash-pinned approved SpecDelta. The parent version is unchanged.
- [ ] Impacted code, tests and baselines are selected via SpecCodeLinks and CodeRelations, with recorded paths and reasons.
- [ ] An architecture delta occurs only when suggested or expected, and is approved or explicitly declined by a human.
- [ ] Task `allowed_scope` is bounded by the ImplementationSpec delta and impact.
- [ ] The cycle starts from the repository's exact canonical revision (`base_sha` pinned from `canonical_commit`). All Forge work runs in isolated ExecutionWorkspaces from that base. At IC READY, `canonical_commit` advances to the integrated SHA, and the canonical index is re-indexed incrementally at that SHA before assurance, with links refreshed.
- [ ] New and modified mandatory ACs and all selected impacted baselines have PASS evidence at the IC SHA.
- [ ] Release R2 is eligible only with BASELINE, SENTINEL, WARDEN and INTEGRATION gates PASS.
- [ ] The Feature Change journey test passes live with LLM proof for all model-dependent stages.
- [ ] Lineage from the change request to R2 and back from changed code to FeatureSpec v2 is queryable.

Progress:
- [ ] 14.1–14.3 Migration, ChangeRequest intake adapter, readiness/link guards.
- [ ] 14.4–14.8 Change interpretation, FeatureSpec v(n+1) + SpecDelta, architecture delta, ImplementationSpec delta, impact-bounded compiler.
- [ ] 14.9–14.11 AC_REVALIDATION source, baseline promotion/supersession, orchestrator.
- [ ] 14.12–14.14 Seed helper, routes, Feature Change journey.
- [ ] Feature Change journey run recorded; §14 and §15 verified.

Blockers:
- None.

Notes:
- Parallel path P3 with Phase 15. The isolated journey uses `seed_trusted_project` (human-authored inputs). Phase 19 proves the same journey chained, without seeds.

### Phase 15 — Bug Fix Journey (R3)

Status: NOT_STARTED

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

Milestone Status: NOT_STARTED

Key Deliverables:
- `core/product_model/defects`, `core/assurance/reproduction`, trace correlation, CodePathResolver, Kira/Sentinel/Warden bug-fix profiles, bug-fix orchestrator
- Migration `0025`; defect fixtures; `tests/journey/test_bug_fix_supportdesk.py`

Acceptance Criteria:
- [ ] A Defect is ingested idempotently and linked to one BUG_FIX cycle and, after triage, to the affected Feature/ACs.
- [ ] PRE_REPAIR REPRODUCTION evidence (assertion failure + symptom signature match, stable over 2 runs) exists at the affected SHA before the first repair commit.
- [ ] Expected behavior is explicitly resolved (cited approved AC, approved spec delta, or human decision) before root-cause analysis.
- [ ] Faulty-symbol candidates are derived deterministically from traceback/coverage and the code graph, with paths.
- [ ] The root-cause hypothesis is persisted as INFERENCE, separate from evidence, and never satisfies an obligation.
- [ ] The repair contract is minimal (≤ policy file limit) and requires a regression test.
- [ ] The affected SHA is the repository's canonical revision pinned at `start_reproduction`. The repair runs in an isolated ExecutionWorkspace from that base. At IC READY, `canonical_commit` advances to the IC SHA, and the canonical index is re-indexed at that SHA before the REGRESSION stage.
- [ ] The original reproduction (same artifact hash) passes at the IC SHA. The regression test passes at the IC SHA and fails at the affected SHA.
- [ ] Impacted baselines pass. Release R3 is eligible only with the REPRODUCTION, REGRESSION, BASELINE, WARDEN, SENTINEL and INTEGRATION gates PASS.
- [ ] The Bug Fix journey test passes live with LLM proof for all model-dependent stages.

Progress:
- [ ] 15.1–15.3 Migration, defect intake, live triage + guard.
- [ ] 15.4–15.7 `sentinel.reproduce`, signature matchers, reproduction retry/NOT_REPRODUCIBLE path, trace correlation.
- [ ] 15.8–15.11 Expected-behavior resolution paths, CodePathResolver, `warden.root_cause`, REPAIR planning + compiler constraints.
- [ ] 15.12–15.15 REGRESSION stage, eligibility conditions + required gates, release hook, orchestrator.
- [ ] 15.16–15.18 Fixtures, routes, Bug Fix journey.
- [ ] Bug Fix journey run recorded; Q-09 decision recorded; §14 and §15 verified.

Blockers:
- None.

Notes:
- Parallel path P3 with Phase 14. "Affected SHA" (`defects.affected_sha`) generalizes "released SHA", so the Phase 19 external-push defect path is supported.

### Phase 16 — External Integrations: Inbound Adapters, Outbound Connectors and Reconciliation

Status: NOT_STARTED

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

Milestone Status: NOT_STARTED

Key Deliverables:
- `core/integrations/{inbound/adapters,connectors/*,reconciliation}`, RepositorySyncService, SecretProvider, Stratos extension
- Migration `0026`; `deploy/compose.test.yaml` (Gitea, MinIO, CI runner), fault proxy; `tests/journey/test_feature_change_via_issue_tracker.py`

Acceptance Criteria:
- [ ] Every inbound adapter (document upload, repository registration, Git webhook, issue/change event, defect event, CI/test event, operator command) authenticates the caller, persists the event id + source identity uniquely, and dispatches at most one command per event.
- [ ] Stale or out-of-order inbound events are recorded without mutating canonical state.
- [ ] External pushes to the default branch trigger canonical re-index, link refresh, staleness evaluation and EXTERNAL_DRIFT findings for affected cycles.
- [ ] An adopted external fast-forward changes `canonical_commit` only through a governed `EXTERNAL_SYNC` revision that references the RepositoryEvent. A rewrite is never adopted without HUMAN acknowledgement. Work never continues silently against the new state: affected work is marked stale or blocked.
- [ ] Remote `GITHUB`/`GITEA` repositories are registered and cloned through the shared materializer, with credentials resolved from `credential_ref` by `SecretProvider`. Credential values are never persisted in repository rows, Git config or remote URLs, and are never returned by any API. `GITLAB`/`BITBUCKET` are rejected as not supported.
- [ ] A `GREENFIELD_MANAGED` repository can attach a remote and publish its released default branch and tags through governed connector actions.
- [ ] CI evidence is accepted only for known IC/release SHAs with valid correlation, and counts toward the mapped obligations.
- [ ] Every outbound mutation (git push/PR, CI trigger, issue update, artifact publish, deployment, external HTTP) passes through ToolGateway with execution identity, scope and policy checks, and carries an idempotency key.
- [ ] Unknown outcomes create ReconciliationItems. No mutation is retried before provider state is queried, and fault-injection tests show exactly one external effect.
- [ ] Executions waiting on external outcomes are checkpointed without a live runtime and resume on resolution.
- [ ] Protected-branch/release mutation is denied to non-release executors.
- [ ] Every external mutation is traceable via `external_links` and connector action rows to project, cycle, task, execution, correlation id and external id.
- [ ] Connector secrets never appear in agent context, logs, audit or artifacts.
- [ ] The Feature Change via issue tracker journey passes live.

Progress:
- [ ] 16.1–16.3 Migration, SecretProvider + connector configs, HMAC verifiers.
- [ ] 16.4–16.7 Git webhook adapter, RepositorySyncService + drift, issue webhook adapter, CI callback adapter.
- [ ] 16.8–16.13 Connectors: git_provider, ci, artifact, issue_tracker, deploy_local, http_generic.
- [ ] 16.14–16.18 Reconciliation + WAITING_EXTERNAL checkpoints, Stratos extension, import contract, test infra, tests.
- [ ] Integration tracker (§9) updated; issue-tracker journey run recorded; §14 and §15 verified.

Blockers:
- None.

Notes:
- Provides the external-push path that Phase 19 uses to introduce the defect (Q-05). Q-10 is relevant.

### Phase 17 — Dashboard, Operator Experience and Orchestrator

Status: NOT_STARTED

Plan:
`plans/17-dashboard-and-operator-experience.md`

Objective:
- A thin Next.js + TypeScript + shadcn/ui + TanStack Query command center over the authoritative APIs and SSE.
- All TECH §25 and ARCH §23 views, plus the Governance inbox, Lineage and Audit.
- Typed command mutations only, with a guard preview.
- A live Orchestrator that explains state and proposes commands. Proposals execute only after explicit human confirmation.

Dependencies: 16.

Milestone: An operator can run every governance step of the four journeys from the dashboard:
- see project, cycle, product, code, execution, Brownfield, impact, assurance, integration and release state projected live from authoritative APIs over SSE;
- decide approvals, clarifications, promotions, waivers, reconciliations, releases and deployments through typed commands;
- converse with a live Orchestrator that explains state and proposes commands that only execute after explicit human confirmation.

Milestone Status: NOT_STARTED

Key Deliverables:
- `apps/dashboard/**`, read-model routers, `core/state/preview.py`, `core/commands/catalog.py`, `agents/orchestrator`, `core/orchestrator`
- Migration `0027`; Playwright UI suite; generated API client

Acceptance Criteria:
- [ ] All ten TECH §25 views plus the Governance inbox, Lineage and Audit are implemented and render from authoritative APIs only.
- [ ] SSE updates trigger refetches with resume after reconnect. No event payload is used as state.
- [ ] Every UI mutation is a typed command with an `Idempotency-Key` and a HUMAN actor. There are no UI-specific write endpoints.
- [ ] The guard preview shows why the next transition is or is not allowed, with no side effects.
- [ ] Knowledge classes, retrieval sources, link origins and confidence are visually distinguishable wherever shown.
- [ ] The Release view shows the exact SHA, gates, approvals and per-condition eligibility from the server.
- [ ] The Repository view shows source type, provider, default branch, status, canonical/released revision and revision history from the server. It never renders a physical workspace path or a credential value.
- [ ] The Orchestrator uses the live `orchestration` alias, persists no canonical state, and its proposals execute only after user confirmation.
- [ ] Role-based UI restrictions match server enforcement (forged requests are rejected).
- [ ] Playwright UI suite and the Orchestrator live test pass.

Progress:
- [ ] 17.1–17.5 Scaffold, API client generation, auth proxy, SSE resume, read models + preview + command catalog.
- [ ] 17.6–17.13 Project, Delivery Cycle, Product/Specs, Code Intelligence, Execution, Brownfield, Impact, Assurance, Defect/Change views.
- [ ] 17.14–17.17 Integrations, Release, Governance inbox, Lineage + Audit views.
- [ ] 17.18–17.19 Orchestrator, tests.
- [ ] Orchestrator live test + Playwright suite evidence recorded; §14 and §15 verified.

Blockers:
- None.

Notes:
- Parallel path P4 with Phase 18.

### Phase 18 — Observability, Security and Recovery Hardening

Status: NOT_STARTED

Plan:
`plans/18-observability-security-and-recovery-hardening.md`

Objective:
- **Observability:** OpenTelemetry traces, metrics and logs with end-to-end correlation; LLM observability and retention policy.
- **Security:** secret redaction and scanning; hardened API and execution tokens; an adversarial ToolGateway suite; a network-less SandboxRunner for untrusted code; prompt-injection resistance proven live; a tamper-evident audit chain; rate limiting; supply-chain scanning.
- **Recovery:** startup reconcilers and chaos scenarios RC-01..RC-12 (including LangGraph state loss and backup/restore), each verified by `assert_system_invariants`.

Dependencies: 16 (and 02–15).

Milestone: Every request, execution, model call, tool action and connector action in a SupportDesk cycle is observable as one correlated trace with standard Olympus identifiers and LLM cost metadata. Adversarial path, shell, egress, token and prompt-injection tests (including live Scout and Forge) are all denied and audited. Untrusted code runs only in a network-less sandbox. Twelve crash, restart and restore scenarios leave the system consistent with every invariant intact, and the audit chain verifies.

Milestone Status: NOT_STARTED

Key Deliverables:
- `core/observability/*`, `core/security/*`, hardened `core/tools/policy/*`, `core/execution/sandbox/*`, `core/ops/*`, fault points
- Migration `0028`; observability compose + dashboards; worker sandbox image; backup/restore scripts; runbooks; security CI

Acceptance Criteria:
- [ ] A single trace links API, command, scheduler, execution, model call, tool and connector spans, with all TECH §24.2 identifiers.
- [ ] LLM spans and `model_calls` record provider, model, prompt version, tokens, latency, retries, schema failures and cost. Raw prompts follow the retention policy.
- [ ] Secrets never appear in logs, traces, snapshots, artifacts, commits or agent context (scanner + redaction tests).
- [ ] API tokens have scopes, expiry, rotation and revocation, enforced on every endpoint.
- [ ] The ToolGateway adversarial suite and SandboxRunner isolation tests pass. Untrusted code runs without network in integration/journey environments.
- [ ] Live prompt-injection tests show no privilege escalation, no FACT inflation and no out-of-scope writes or pushes.
- [ ] The audit chain is tamper-evident and verifiable.
- [ ] Recovery scenarios RC-01..RC-12 pass with `assert_system_invariants` green, including LangGraph state loss and backup/restore.
- [ ] The security CI workflow passes (pip-audit, pnpm audit, bandit, gitleaks).

Progress:
- [ ] 18.1–18.4 Migration + audit-chain backfill, OTel, metrics + dashboards, LLM retention.
- [ ] 18.5–18.8 Secret redaction/scanning, API token hardening, execution-token binding, ToolGateway hardening.
- [ ] 18.9–18.12 SandboxRunner + executor migration, audit hash chain, rate limiting, security CI.
- [ ] 18.13–18.17 Fault points + chaos harness + invariants, startup reconcilers, RC-01..RC-12, backup/restore + runbooks, tests.
- [ ] Live injection + RC-01 live evidence recorded; §14 and §15 verified.

Blockers:
- The Linux host (or Linux worker container) with bubblewrap must be available for SandboxRunner integration tests.

Notes:
- Parallel path P4 with Phase 17.

### Phase 19 — Final Four-Journey E2E and MVP Acceptance

Status: NOT_STARTED

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
- DC-004 Bug Fix: externally pushed defect → reproduction before repair → root cause → regression-proven Release R3, approved in the dashboard.

Every model-dependent stage uses a live provider. Canonical state is identical across four runtime-wiping restarts. The read-only MVP Acceptance Evaluator returns `mvp_complete = true`, with every ARCH §26 / TECH §32 term and every ARCH §22 / TECH §31 row backed by passing evidence.

Milestone Status: NOT_STARTED

Key Deliverables:
- `scripts/demo/{bootstrap.sh,preflight.py,run_mvp.py,chained/*}`, `scripts/acceptance/{evaluate_mvp,check_matrix}.py`, `deploy/compose.demo.yaml`, Make targets
- `tests/journey/test_mvp_chained_supportdesk.py`, `tests/acceptance/matrix.yaml`, `apps/dashboard/tests/e2e/mvp_walkthrough.spec.ts`, chained fixtures, `docs/demo/MVP_DEMO_RUNBOOK.md`
- Two acceptance reports + junit files referenced here

Acceptance Criteria:
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

Progress:
- [ ] 19.1–19.3 Demo compose overlay + Make targets, bootstrap, preflight.
- [ ] 19.4–19.6 Chained driver, restart boundary + fingerprint, chained fixtures.
- [ ] 19.7–19.11 Stages A–D, precondition probe + defect injector (Q-05 strategy A).
- [ ] 19.12–19.16 Cross-cycle assertions + chained test, chaos plan, evaluator, acceptance matrix, Playwright walkthrough.
- [ ] 19.17–19.19 Runbook, two clean-environment runs recorded, final STATUS update.

Blockers:
- Q-05 strategy must be confirmed. Q-06 (budget ceiling) must be set before the first run.

Notes:
- `MVP_COMPLETE` may be declared only under Phase 19 §15.

---

## 6. JOURNEY READINESS

| Journey | Required Phases | Repository / workspace dependencies | State | Blocking Phase | Evidence |
|---|---|---|---|---|---|
| Greenfield | 00–10 | Repository provisioning; Canonical workspace; Execution worktrees; IntegrationCandidate; Canonical Code Index | NOT_STARTED | 00 | — (target: `tests/journey/test_greenfield_supportdesk.py` run ID; Phase 19 chained DC-001) |
| Brownfield | 00–12 (directly 07, 11, 12) | Repository connector; Credential resolution; Clone/fetch; Canonical workspace; Code Intelligence discovery | NOT_STARTED | 00 | — (target: `tests/journey/test_brownfield_supportdesk.py`; Phase 19 chained DC-002) |
| Feature Change | 00–14 (directly 13, 14; issue-tracker path 16) | Canonical repository SHA; Execution worktrees; IntegrationCandidate; Canonical re-index | NOT_STARTED | 00 | — (target: `tests/journey/test_feature_change_supportdesk.py`, `test_feature_change_via_issue_tracker.py`; Phase 19 chained DC-003) |
| Bug Fix | 00–13, 15 | Canonical repository SHA; Execution worktrees; IntegrationCandidate; Canonical re-index | NOT_STARTED | 00 | — (target: `tests/journey/test_bug_fix_supportdesk.py`; Phase 19 chained DC-004) |
| Four-journey chained MVP demo | 00–19 | Unified Repository / RepositoryWorkspace / ExecutionWorkspace model for all four cycles | NOT_STARTED | 00 | — (target: two `mvp_acceptance_<run_id>.json` reports, one with `chaos=true`) |

State values: `NOT_STARTED | PARTIAL | IN_PROGRESS | COMPLETE | BLOCKED`. A journey is `COMPLETE` only after its owning phase's journey test passed live **and** the Phase 19 chained run passed.

Once a canonical RepositoryWorkspace is READY, Greenfield and Brownfield use the same post-materialization path: ExecutionWorkspace → TaskContract → Execution → Candidate Commit → IntegrationCandidate → Integrated SHA → Canonical repository revision → Canonical Code Intelligence index → Assurance → Release. There is no separate execution system per journey.

---

## 7. ARCHITECTURAL INVARIANT TRACKER

Check an invariant only when the listed proving tests pass in CI (and the live lane, where noted). Record the test IDs in Notes.

| ✓ | Invariant | Established in | Proven by (phase §12) |
|---|---|---|---|
| [ ] | Olympus owns canonical state. | 01 | 01 transition atomicity; 03 restart; 18 RC-02; 19 restart fingerprints |
| [ ] | Runtime cannot directly mutate authoritative lifecycle state. | 01, 02 | 01 AGENT-actor rejection + import-linter `agents-no-persistence`; 02 runtime contract tests |
| [ ] | Project and DeliveryCycle are distinct. | 01 | 01 persistence + API tests |
| [ ] | Task and Execution are distinct. | 03 | 03 retry/new-Execution tests |
| [ ] | TaskContract is versioned. | 01 | 01 contract immutability (app + trigger) |
| [ ] | ExecutionSnapshot is immutable. | 03 | 03 snapshot hash + trigger tests |
| [ ] | Worktree isolation is enforced. | 04 | 04 concurrent worktree + canonical-checkout tests; 18 adversarial suite |
| [ ] | ToolGateway authorization is enforced. | 04 | 04 denial tests; 18 adversarial + live injection |
| [ ] | External mutations use governed ActionRequests. | 04, 16 | 04 `git_local`; 16 connector tests + `connectors-only-via-gateway` |
| [ ] | IntegrationCandidate is the assurance target. | 08, 09 | 08 candidate-not-target; 09 evidence SHA tests |
| [ ] | The canonical Code Intelligence index is tied to the integrated SHA. | 07, 08, 13 | 08 pointer == integrated_sha; 13 incremental equivalence; 19 cross-cycle check |
| [ ] | FeatureSpec and ImplementationSpec remain distinct. | 05, 06 | 06 entity/version tests |
| [ ] | Architecture constrains ImplementationSpec. | 06 | 06 `ARCHITECTURE_DELTA_REQUIRED` rejection; 13/14 delta path |
| [ ] | Brownfield inference cannot silently become canonical intent. | 11, 12 | 11 no-FACT + PROPOSED-only; 12 PROMOTION-only path |
| [ ] | Mandatory ACs require evidence. | 09 | 09 coverage truth table; 10 eligibility |
| [ ] | Warden/Sentinel cannot directly finalize gates. | 09 | 09 DB constraint + 403 + no tool path |
| [ ] | Release eligibility is deterministic. | 10 | 10 eligibility truth table + TOCTOU |
| [ ] | Runtime restart retains canonical state. | 03, 18 | 03 worker restart; 10 journey restart; 18 RC-01..RC-12; 19 RB-A..RB-D |
| [ ] | Mocked LLM output is not used as journey proof. | 02, 10 | 02 FakeProvider env guard + `--live-required`; `assert_live_llm_proof` in 10/12/14/15/16/19 |
| [ ] | Git/repository storage owns source-code bytes. | 01, 04, 10 | 01 no code-body columns; 04 worktree writes; 10 Greenfield `pg_dump` grep |
| [ ] | Control Plane owns repository identity and canonical revision metadata. | 01, 08 | 01 Repository + revision trigger; 08 `INTEGRATION_READY` advance |
| [ ] | Greenfield and Brownfield converge on one RepositoryWorkspace model. | 04, 11 | 04 shared materializer; 11 no clone-of-its-own |
| [ ] | Execution writes occur only in isolated ExecutionWorkspace/worktrees. | 04 | 04 concurrent worktree + canonical-ref tests; 18 adversarial suite |
| [ ] | Candidate commits do not automatically change canonical project revision. | 04, 08 | 04 candidate-not-canonical; 08 advance only at IC READY |
| [ ] | Canonical revision changes only through the governed integration flow. | 08, 10, 16 | 08 `RepositoryRevisionService`; 10 `RELEASED`; 16 `EXTERNAL_SYNC` only |
| [ ] | Canonical Code Intelligence indexes the exact canonical integrated SHA. | 07, 08, 13 | 08 pointer == `canonical_commit` == `integrated_sha`; 13 incremental equivalence |
| [ ] | Repository credentials are never stored or exposed in plaintext. | 01, 04, 16 | 01 `credential_ref` only; 04 env clone dump grep; 16 SecretProvider |

Additional prompt invariants tracked here (numbering from the planning prompt):

| ✓ | Invariant | Phase(s) |
|---|---|---|
| [ ] | 8–9 Retry creates a new Execution, and historical failed Executions stay immutable. | 03 |
| [ ] | 12–13 Scheduler eligibility is deterministic, and agents do not authorize themselves. | 03 |
| [ ] | 15–16 Candidate commits converge into an IntegrationCandidate and never become release candidates on their own. | 08 |
| [ ] | 19 Temporary/candidate indexes are distinguishable from the canonical index. | 07, 08 |
| [ ] | 25 Human approvals are explicit persisted objects. | 01 |
| [ ] | 27 Model opinion alone cannot satisfy an AC. | 09 |
| [ ] | 29–30 Recovered behavior ≠ intended behavior; ObservedBehavior / RecoveredSpec / CanonicalSpec are distinct. | 11, 12 |
| [ ] | 31–32 Feature Change uses a versioned spec delta and graph impact. | 13, 14 |
| [ ] | 33–35 Bug Fix is reproduce-first, has regression proof, and revalidates impacted baselines. | 15 |
| [ ] | 37 Product-to-code lineage is queryable both ways. | 08, 10, 19 |
| [ ] | 38 Integrations are auditable, idempotent and correlated. | 05, 16 |

---

## 8. TECHNICAL ACCEPTANCE TRACKER

The first block tracks repository materialization (README §5.9). Later blocks remain the existing thematic tracker. Items here are implementation work and acceptance criteria, not already-proven claims.

### Repository Model
- [ ] Repository entity exists (01).
- [ ] Project → Repository relationship exists (01).
- [ ] Greenfield-managed repository supported (`source_type=GREENFIELD_MANAGED`, declared by a GREENFIELD cycle) (01, 04, 06).
- [ ] External cloned repository supported (`source_type=EXTERNAL_CLONE`) (01, 04, 11, 16).
- [ ] provider / default branch / canonical SHA tracked (`registered_sha`, `canonical_commit`, `released_commit`) (01, 08, 10).
- [ ] `credential_ref` used instead of plaintext credentials (01, 04, 16).

### Workspace Model
- [ ] Canonical RepositoryWorkspace implemented (logical location; `LOCAL_FILESYSTEM` backend) (01, 04).
- [ ] ExecutionWorkspace implemented (`GIT_WORKTREE`, writable or readonly) (04).
- [ ] Physical workspace root configurable (`OLYMPUS_WORKSPACE_ROOT`; optional `OLYMPUS_WORKTREE_ROOT` override) (00, 04).
- [ ] Logical workspace identifiers stored in domain state; no machine-specific host path (01, 04).
- [ ] Isolated Git worktree enforced for writable Executions (04, 18).

### Greenfield
- [ ] Repository is provisioned before implementation Executions (04, 06, 10).
- [ ] Initial canonical SHA recorded (`registered_sha` / revision #1 `MATERIALIZED`) (04, 06, 10).
- [ ] Generated source code resides in Git / workspaces, not DB state (04, 10).

### Brownfield
- [ ] Repository registration supported (01, 11, 16).
- [ ] Credentials resolved through connector / credential provider (04, 11, 16).
- [ ] Clone / fetch materializes the canonical workspace (04, 11).
- [ ] Exact HEAD SHA captured (04, 11).
- [ ] Code Intelligence indexes the cloned SHA (07, 11).
- [ ] Fresh runtime can reconstruct project understanding from durable repository + SHA (11, 19).

### Control Plane
- [ ] All five DeliveryCycle machines are encoded as data, with exhaustive edge tests (01).
- [ ] Transition + domain event + audit commit atomically, and concurrent transitions give exactly one success (01).
- [ ] Unregistered guards fail closed, and no `RequiredGuard` placeholder remains at MVP end (01 → 15).
- [ ] Command idempotency: a duplicate `Idempotency-Key` creates no duplicate state (01).
- [ ] No endpoint accepts a direct `state`/`status` field (01 OpenAPI test).

### Product / Specification Model
- [ ] ProductSource versions are immutable and content-addressed (05).
- [ ] The Capability → Feature → FeatureSpec → Requirement/UserStory/AC hierarchy is persisted from validated Kira output only (05).
- [ ] Every FeatureSpec has ≥1 mandatory AC with an `evidence_requirement` (05).
- [ ] Approved FeatureSpec/ImplementationSpec/Architecture versions are immutable, and changes create versions (05, 06, 13).
- [ ] KnowledgeItems distinguish FACT/INFERENCE/UNCERTAINTY/DECISION/ASSUMPTION (05, 11).

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
- [ ] Every writable run has TaskContract + Snapshot + isolated worktree + candidate commit (04; TECH §31 Execution).

### AgentRuntime / ModelRouter
- [ ] Alias-only model selection; no model ID literal outside `config/` (02).
- [ ] Structured output is Pydantic-validated, with bounded schema-feedback retries (02).
- [ ] Every model call is persisted with tokens, cost, latency, prompt hash and provider request ID (02).
- [ ] Budgets are enforced before send (02).
- [ ] LangGraph checkpoints are non-authoritative (resume after truncation) (02, 18 RC-02).

### Git Isolation
- [ ] One ExecutionWorkspace (worktree + branch) per writable execution; the canonical RepositoryWorkspace is never written by agents (04).
- [ ] Protected branches and tags are writable only by the deterministic release executor (04, 10, 16).
- [ ] Candidate commits remain non-canonical and do not move `canonical_commit` (04, 08).

### ToolGateway
- [ ] 100% of tool calls persisted as ActionRequest + decision + result (04).
- [ ] Path traversal, symlink escape, `.git` access and out-of-scope writes are denied (04, 18).
- [ ] Shell allowlist with bounded cwd, timeout and output limits (04, 18).

### Governed Actions
- [ ] Approval-required actions create Approval(ACTION) and checkpoint (04).
- [ ] Same idempotency key → single external effect (04, 16).
- [ ] Unknown outcomes → reconciliation before any retry (16).

### Code Intelligence
- [ ] The index is reproducible per `(repository, sha)` (07).
- [ ] The golden SupportDesk entity/relation fixture matches (07).
- [ ] Route → handler → service → repository → model → table traversal (07).
- [ ] Candidate and canonical indexes are distinct; candidate indexes are temporary and DISCARDED (07, 08).
- [ ] Canonical index references the exact integrated / canonical SHA (`pointer.commit_sha == repositories.canonical_commit`) (08, 13).
- [ ] Product-to-code lineage resolves through the canonical index (08, 10, 19).
- [ ] Incremental re-index equals full rebuild (13).
- [ ] Retrieval results expose STRUCTURAL/LEXICAL/SEMANTIC source and provenance (07, 13).

### IntegrationCandidate
- [ ] Candidate Commits remain non-canonical (08).
- [ ] IntegrationCandidate produces an exact `integrated_sha` (08).
- [ ] Canonical repository revision corresponds to the accepted integrated SHA (08).
- [ ] Merge conflicts create explicit work (Finding + remediation task); no autonomous resolution (08).
- [ ] IC READY ⇒ canonical pointer `commit_sha == integrated_sha == Repository.canonical_commit` (08).
- [ ] Default branch and tags in the canonical RepositoryWorkspace are untouched by integration (08).

### Assurance
- [ ] Warden / Sentinel target the exact integrated SHA (`HEAD == integrated_sha == canonical_commit`) (09).
- [ ] Warden produces findings and recommendations only (09).
- [ ] Sentinel planning is live, and check execution is deterministic (09).
- [ ] The Gate Finalizer is a pure function of evidence, coverage, findings and policy (09).
- [ ] A gate cannot PASS unless `Repository.canonical_commit == ic.integrated_sha` (09).
- [ ] The remediation loop produces a new Execution → new IC → new gates (09).

### Evidence
- [ ] Every Evidence row references the exact integrated SHA (09).
- [ ] MODEL_ASSESSMENT never satisfies a mandatory AC (09).
- [ ] External CI evidence is accepted only for known SHAs with correlation (16).

### Brownfield
- [ ] Context isolation is proven by a manifest (11, 19).
- [ ] FACTs come only from deterministic discovery (11).
- [ ] Confidence is capped by deterministic evidence (11).
- [ ] DISCOVERED links are distinguishable and retained after HUMAN_CONFIRMED (11, 12).
- [ ] Onboarding uses the shared Repository connector / materializer, not a Greenfield-only path (04, 11).

### Behavioral Baselines
- [ ] Every ACTIVE baseline has PASS evidence at its established SHA (12).
- [ ] BaselineSets are versioned and monotonic (12, 14, 15, 19).
- [ ] The baseline release condition and BASELINE gate are active for FEATURE_CHANGE/BUG_FIX (12).

### Impact Analysis
- [ ] ImpactAssessment items have traversal paths, retrieval source and confidence (13).
- [ ] Only STRUCTURAL items create obligations, each with a reason (13).
- [ ] StalenessService flags tasks, executions and baselines on input change (13).
- [ ] A canonical revision change marks impacted TaskContracts, Executions, candidate indexes, ImpactAssessments and baselines; a diverged cycle base requires explicit rebase (13, 16).

### Feature Change
- [ ] FeatureSpec v(n+1) with a hash-pinned SpecDelta; the parent version is unchanged (14).
- [ ] Task scope is bounded by ImplementationSpec delta + impact (14).
- [ ] Cycle starts from the canonical repository SHA; Forge runs in ExecutionWorkspaces; IC READY advances `canonical_commit` and re-indexes (14).
- [ ] New ACs and impacted baselines PASS at the IC SHA before R2 (14).

### Bug Fix
- [ ] PRE_REPAIR reproduction evidence predates the first repair commit (15).
- [ ] Expected behavior is explicitly resolved before root cause; ambiguous cases go to a human decision or SpecDelta (15).
- [ ] The root-cause hypothesis is INFERENCE and never Evidence (15).
- [ ] Affected SHA is the pinned canonical revision; repair runs in an ExecutionWorkspace; IC READY advances `canonical_commit` and re-indexes (15).
- [ ] The regression test fails at the affected SHA and passes at the IC SHA (15).

### Inbound Integration
- [ ] A common `InboundEvent` envelope with correlation ID and idempotency (05).
- [ ] HMAC-authenticated webhooks with a replay window (16).
- [ ] Unique `(source_type, source_id, event_id)`; a duplicate is ACKed without re-dispatch (05, 16).
- [ ] Stale or out-of-order events are recorded without mutation (16).

### Outbound Integration
- [ ] Connectors are callable only via ToolGateway (16 import contract).
- [ ] Every mutating ConnectorAction carries an idempotency key and correlation ID (04, 16).
- [ ] `external_links` trace every external mutation (16).

### Release
- [ ] Eligibility is persisted per condition, with reasons (10).
- [ ] Release approval is pinned to the manifest hash (10).
- [ ] Release Manifest references the exact integrated SHA (10, 14, 15, 19).
- [ ] The manifest SHA == default-branch HEAD == tag == `Repository.canonical_commit` == `Repository.released_commit` == released index pointer (10).
- [ ] A TOCTOU re-check at execution (10).
- [ ] A DeliveryOutcome bundle is persisted (10).

### Frontend / Operator Experience
- [ ] All views render from authoritative APIs; SSE triggers refetch only (17).
- [ ] UI mutations are typed commands with an Idempotency-Key (17).
- [ ] Orchestrator proposals execute only after human confirmation (17).
- [ ] UI role restrictions match the server (17, 19).

### Observability / Security
- [ ] One correlated trace across API → scheduler → execution → model → tool → connector (18).
- [ ] No secrets in logs, traces, snapshots, artifacts, commits or agent context (18).
- [ ] Network-less sandbox for untrusted code (18).
- [ ] The audit hash chain verifies (18).
- [ ] RC-01..RC-12 recovery scenarios pass (18).

---

## 9. INTEGRATION TRACKER

Status values: `NOT_STARTED | IMPLEMENTED | VERIFIED` (VERIFIED = connector/integration tests and the owning journey test passed). Rows marked "(planned)" describe the contract each phase must deliver.

### Inbound

| Integration | Connector / Adapter | Phase | Status | Contract | Idempotency | Retry | Reconciliation | Correlation ID | Audit / Evidence |
|---|---|---|---|---|---|---|---|---|---|
| Document upload | `document_upload` (`POST /projects/{id}/sources`) | 05 | NOT_STARTED | `InboundEvent` → immutable `ProductSource` version (planned) | `(source, event_id)` unique + content hash (duplicate → no new version) | client re-POST is safe (duplicate ACK) | n/a (synchronous) | assigned or propagated | `inbound_events` + `audit_events` + `product_source.ingested` |
| Repository registration | `repository_registration` (API) | 01 (LOCAL metadata), 04 (materialize), 11 (EXTERNAL_CLONE wiring), 16 (remote + webhook) | NOT_STARTED | `register_repository` command; `GREENFIELD_MANAGED` declared by cycle create; records `registered_sha` / `canonical_commit` after materialization (planned) | `Idempotency-Key` + `UNIQUE(project_id)` | client retry safe | polling loop (16) | command correlation | `repository.registered` + `repository.materialized` + audit |
| Git webhook | `git_provider_webhook` (GitHub/Gitea) | 16 | NOT_STARTED | push / ref / default-branch → `RepositoryEvent` → `RepositorySyncService` (planned) | `(source, delivery id)` unique | provider redelivery | ancestry-based STALE + repository polling | from delivery / assigned | `repository_events` + drift Findings + audit |
| Issue / change event | `change_request_api` (14), `issue_tracker_webhook` (16) | 14, 16 | NOT_STARTED | label `olympus:change` → `intake_change_request` → ChangeRequest + FEATURE_CHANGE cycle (planned) | event id unique; one CR per issue | provider redelivery | `updated_at` vs stored source_version | propagated to the cycle | `external_links` (CR↔issue) + audit |
| Defect event | `defect_report_api` (15), `issue_tracker_webhook` (16) | 15, 16 | NOT_STARTED | label `olympus:defect` → `intake_defect` → Defect + BUG_FIX cycle (planned) | event id unique; one Defect per issue | provider redelivery | source_version staleness | propagated | `external_links` (Defect↔issue) + audit |
| CI / test event | `ci_callback` | 16 | NOT_STARTED | `ExternalCiResult` → `EXTERNAL_CI` Evidence for a known IC/release SHA (planned) | run id unique | CI runner retry | STALE for superseded IC SHA | must match a `ci.trigger_verification` action | Evidence + junit artifact + audit |
| API / operator command | command bus (`POST …/commands/{command}`); `operator_api` recording | 01, 16 | NOT_STARTED | typed commands, HUMAN actor (planned) | `command_log(actor_id, idempotency_key)` unique | replay returns the stored result | n/a | `X-Correlation-ID` | `command_log` + `audit_events` |

### Outbound

| Integration | Connector | Phase | Status | Contract | Idempotency | Retry | Reconciliation | Correlation ID | Audit / Evidence |
|---|---|---|---|---|---|---|---|---|---|
| Git actions (local) | `git_local` | 04 (08 merge, 10 ff/tag, 11 clone) | NOT_STARTED | typed `ConnectorAction` via ToolGateway (planned) | idempotency key per action | bounded | by ref / tree hash | execution + correlation | `connector_actions/results` + audit |
| Git actions (remote) | `git_provider` (GitHub, Gitea): fetch, push_branch, push_release, PR, merge status, webhook | 16 | NOT_STARTED | §4.4 of Phase 16 (planned) | key template per action | same key, bounded backoff | remote ref SHA / PR search by head branch | yes | `external_links` (IC↔PR, Release↔tag) + audit |
| CI trigger | `ci` (`http_ci`, `github_actions`) | 16 | NOT_STARTED | `trigger_verification(sha, ref, suite)`, `read_status` (planned) | key per (IC SHA, suite) | same key | run lookup by correlation id | yes | Evidence on callback + audit |
| Issue update | `issue_tracker` (GitHub, Gitea) | 16 | NOT_STARTED | comment / status / close / link release, scoped to the current cycle (planned) | `<!-- olympus:idem=<key> -->` marker | same key | comment search by marker | yes | `external_links` + audit |
| Artifact publication | `artifact` (`artifact_fs`, `artifact_s3`); internal store (03) | 03, 16 | NOT_STARTED | content-addressed publish/read (planned) | content hash | same key | object exists with matching hash | yes | artifact rows + audit |
| Deployment | `deployment` (`deploy_local`) via Stratos | 10 (release), 16 (deploy) | NOT_STARTED | deploy / status / rollback for RELEASED + ELIGIBLE releases only; Approval(DEPLOYMENT) (planned) | key per (release, target) | same key | deployment marker / health version | yes | `deployments` + audit |
| External APIs | `http_generic` | 16 | NOT_STARTED | host + method allowlist (planned) | idempotency header for mutating methods | same key | provider-specific; unreconcilable mutations need policy opt-in | yes | connector rows + audit |

---

## 10. LIVE LLM READINESS

| Field | Value |
|---|---|
| Provider | Anthropic (primary, TECH §2) — **not configured**. OpenAI optional; required for embeddings if Q-04 selects it. |
| ModelRouter | NOT_STARTED (Phase 02) |
| Configured Model Aliases | Planned (D-11 / Q-03): `product_decomposition`, `planning`, `architecture`, `repository_reasoning`, `implementation`, `review`, `verification_planning`, `orchestration`, `embedding`. All may point to `MODEL_DEFAULT` initially. **None configured.** |
| Credentials Configured | No (`ANTHROPIC_API_KEY`, `OPENAI_API_KEY` absent; CI `live` job secrets absent) |
| Structured Output Validation | NOT_STARTED (Phase 02) |
| Retry Handling | NOT_STARTED (Phase 02: schema ≤ 2, transport ≤ 3) |
| Token Usage Tracking | NOT_STARTED (`model_calls`, Phase 02) |
| Cost Tracking | NOT_STARTED (`config/model_pricing.yaml`, Phase 02; spans in 18) |
| Live Integration Tests | NOT_STARTED (none run) |
| Journey Tests | NOT_STARTED (none run) |

Per capability:

| Agent | Profiles | Alias(es) | Phase | Structured output | Live contract test | Journey proof | Status |
|---|---|---|---|---|---|---|---|
| Orchestrator | `orchestrator.converse` | orchestration | 17 | `OrchestratorTurn` | `test_orchestrator_live.py` | 19 (optional explain) | NOT_STARTED |
| Kira | `kira.decompose`, `kira.implementation_spec`, `kira.task_plan`, `kira.change_interpret`, `kira.defect_triage`, `kira.expected_behavior` | product_decomposition, planning | 05, 06, 14, 15 | `ProductDecomposition`, `ImplementationSpecDraft`, `TaskPlan`, `ChangeInterpretation`, `DefectTriage`, `ExpectedBehaviorProposal` | `test_kira_decompose_supportdesk_live.py`, `test_kira_impl_spec_live.py`, `test_kira_task_plan_live.py`, `test_kira_change_interpret_live.py`, `test_kira_defect_triage_live.py`, `test_kira_expected_behavior_live.py` | 10, 14, 15, 19 | NOT_STARTED |
| Atlas | `atlas.propose_architecture`, `atlas.architecture_delta` | architecture | 06, 14 | `ArchitectureProposal`, `ArchitectureDeltaProposal` | `test_atlas_supportdesk_live.py`, `test_atlas_delta_live.py` | 10, 14, 19 | NOT_STARTED |
| Scout | `scout.survey`, `scout.recover_feature` | repository_reasoning | 11 | `RepositorySurvey`, `RecoveredFeatureSpec` | `test_scout_survey_supportdesk_live.py`, `test_scout_recover_feature_live.py` | 12, 19 | NOT_STARTED |
| Forge | `forge` | implementation | 04 (06 compiled contracts) | `ImplementationResult` | `test_forge_candidate_commit_live.py` | 10, 14, 15, 19 | NOT_STARTED |
| Warden | `warden.review`, `warden.root_cause` | review | 09, 15 | `WardenReview`, `RootCauseHypothesis` | `test_warden_review_live.py`, `test_warden_root_cause_live.py` | 10, 14, 15, 19 | NOT_STARTED |
| Sentinel | `sentinel.plan`, `sentinel.summarize`, `sentinel.characterize`, `sentinel.reproduce` | verification_planning | 09, 12, 15 | `VerificationPlan`, `CharacterizationPlan`, reproduction test artifact | `test_sentinel_plan_live.py`, `test_sentinel_characterize_live.py`, `test_sentinel_reproduce_live.py` | 10, 12, 14, 15, 19 | NOT_STARTED |
| (platform) | `diagnostic.structured_echo`; `ModelRouter.embed` | verification_planning; embedding | 02, 03; 13 | `DiagnosticSummary`; `EmbeddingResult` | `test_model_router_live.py`, `test_langgraph_runtime_live.py`; `test_semantic_retrieval_live.py` | — | NOT_STARTED |
| Stratos | `stratos.release` (deterministic executor) | — (no LLM) | 10, 16 | n/a | n/a | 10, 14, 15, 19 | NOT_STARTED |

Rules (README §6.3): `FakeProvider` is allowed only in `local`/`test` unit tests. `--live-required` turns skipped live tests into failures. Journey tests must pass `assert_live_llm_proof`.

---

## 11. MVP DEFINITION OF DONE

| Journey | Definition | State |
|---|---|---|
| Greenfield | Product Source → Verified Release R1 | NOT_STARTED |
| Brownfield | Unknown Repository → Trusted Product Model → READY_FOR_CHANGE | NOT_STARTED |
| Feature Change | Versioned Spec Delta → Impact Analysis → Safe Code Delta → Regression-Safe Release R2 | NOT_STARTED |
| Bug Fix | Defect → Reproduction → Root Cause → Repair → Regression-Proven Release R3 | NOT_STARTED |

Final conditions (each is computed by the Phase 19 MVP Acceptance Evaluator):
- [ ] product-to-code lineage queryable;
- [ ] required FeatureSpecs/requirements approved;
- [ ] mandatory Acceptance Criteria backed by evidence;
- [ ] required Behavioral Baselines pass;
- [ ] required gates pass;
- [ ] no blocking Findings remain;
- [ ] required approvals exist;
- [ ] canonical Code Intelligence index matches verified IntegrationCandidate;
- [ ] release eligibility calculated deterministically;
- [ ] Release Manifest references exact verified integrated commit;
- [ ] inbound events are auditable/idempotent where applicable;
- [ ] outbound mutations pass through ToolGateway/connector governance;
- [ ] real LLM paths exercised for model-dependent behavior;
- [ ] runtime restart does not lose canonical delivery truth.

`MVP_COMPLETE` additionally requires every conjunct of ARCH §26 and TECH §32 (evaluator) and every ARCH §22 / TECH §31 row (acceptance matrix) to be proven, on two consecutive clean runs (Phase 19 §15).

---

## 12. OPEN ARCHITECTURE QUESTIONS

Each question has a working default that the plans already implement, so implementation can proceed. A human owner must confirm or override each one before the phase listed under "Needed by".

| ID | Question | Working default in plans | Needed by | Status |
|---|---|---|---|---|
| Q-01 | Should Kira, Atlas, Scout, Sentinel and the other agents' model work run as scheduled Task Executions (snapshot, lease, audit, retry), even though ARCH/TECH describe some of it as service flows? | Yes (D-12): every model call runs inside an Execution of a CONTROL_PLANE or IMPLEMENTATION_PLAN Task. | 03 | OPEN |
| Q-02 | In the chained demo, Brownfield DC-002 runs on a Project that already has a canonical Greenfield model. How do recovered specs relate to it without breaking "fresh context"? | Scout context is isolated (no product-model rows). The deterministic reconciliation report (MATCHED/NEW/MISSING/DIVERGENT) feeds human review, and MATCHED → `CONFIRM_EXISTING` (no duplicate lineage). | 11 | OPEN |
| Q-03 | Is the alias set acceptable? TECH Appendix A defines six; the plans add `planning`, `orchestration` and `embedding`. | Nine aliases, all defaulting to `MODEL_DEFAULT`. | 02 | OPEN |
| Q-04 | Which embedding provider backs the `embedding` alias? Anthropic has no embeddings API. | OpenAI embeddings; local `fastembed` as fallback. Semantic retrieval degrades gracefully. | 13 | OPEN |
| Q-05 | How is the closed-ticket defect introduced into the live-generated SupportDesk code for the chained demo? | Strategy A (Phase 19 §4.3): a deterministic, index-located LibCST injector applied as an external commit and detected by Phase 16 sync. Strategy B (separate Project on the hand-written defect fixture) only as an explicit waiver. | 19 | OPEN |
| Q-06 | What are the cost and duration ceilings for one live four-journey chained run? These set `LLM_TEST_BUDGET_USD` and CI timeouts. | No default. Phase 10 recommends ≥ $15 for Greenfield alone. | 19 (set by 10 from observed cost) | OPEN |
| Q-07 | Is the REMEDIATION DeliveryCycle type needed as a standalone cycle in the MVP? | Defined in Phase 01 for completeness. Remediation normally runs inside the owning cycle (09, 12). | 12 | OPEN |
| Q-08 | Brownfield remediation is published through the Release mechanism and consumes a release key (R<n>). Is that acceptable? | Yes. The chained demo is designed to need no remediation. | 12 | OPEN |
| Q-09 | Which agent performs Bug Fix root-cause reasoning? The documents name none. | Warden (`warden.root_cause`): read-only and independent of Forge. Output is INFERENCE only. | 15 | OPEN |
| Q-10 | After an external push to the default branch, the canonical index pointer moves to the external SHA (`source=EXTERNAL_PUSH`, Phase 16). Confirm that this matches ARCH §13.1 ("canonical = current IC or released commit"). | Accepted as the project baseline for impact and reproduction. Assurance still requires pointer == IC SHA at ASSURANCE entry (invariant 18). Adoption writes `canonical_commit` only via `RepositoryRevisionService.advance(cause=EXTERNAL_SYNC)`. | 16 | OPEN |
| Q-11 | May a Project have more than one Repository in the MVP? | No. `UNIQUE(project_id)`. Relaxing later needs cycle-level repository selection and per-repository base pins; the entity shape stays. | 01 | OPEN |
| Q-12 | May two DeliveryCycles hold unreleased canonical revisions at the same time? | No. IC creation is rejected with `CANONICAL_REVISION_HELD`. A new IC in the same cycle (remediation) is allowed and supersedes. | 08 | OPEN |
| Q-13 | Is the canonical RepositoryWorkspace a bare Git repository? | Yes. No working tree; reads use Git objects; every checkout is an ExecutionWorkspace that shares the object store. | 01, 04 | OPEN |
| Q-14 | Where does `credential_ref` resolve, and is an encrypted local secret store acceptable? | Phase 04: `none:` / `env:`. Phase 16 adds `file:` and encrypted `secret:` keyed by `OLYMPUS_SECRET_KEY`. External secret managers (Vault / cloud SM) are post-MVP. | 16 | OPEN |
| Q-15 | Are non-local workspace backends or multi-host workers in MVP scope? | No. `LOCAL_FILESYSTEM` under one shared `OLYMPUS_WORKSPACE_ROOT`. | 04, 18 | OPEN |
| Q-16 | Must a `GREENFIELD_MANAGED` repository have a remote before Release R1? | No. Journey 1 completes locally. Phase 16 `attach_remote` is optional; Phase 19 Stage A uses it for Gitea. RC-12 must back up `OLYMPUS_WORKSPACE_ROOT`. | 10, 16, 18 | OPEN |

---

## 13. ARCHITECTURE DRIFT LOG

Planning-time source reconciliations are recorded in `plans/README.md` §2 (D-01..D-17) and are not drift. Implementation-time drift is recorded here, following the protocol in `plans/README.md` §9.

| ID | Phase | Description | Decision | Invariant impact | Approver | Date |
|---|---|---|---|---|---|---|
| FE-C01 | UI | Phase 15 `ApprovalType` values `UNREPRODUCED_REPAIR`, `EXPECTED_BEHAVIOR`; Phase 16 `DEPLOYMENT` not in Phase 01 enum | Frontend `openEnum` accepts all; await backend union | none | pending | 2026-10-01 |
| FE-C02 | UI | ChangeRequest terminal `DONE` (14) vs `RELEASED` (19) | Frontend accepts both | none | pending | 2026-10-01 |
| FE-C03 | UI | Obligation reasons `BASELINE_IMPACTED`, `AC_REVALIDATION`, `SMOKE` not in Phase 09 enum | Frontend accepts all | none | pending | 2026-10-01 |
| FE-C04 | UI | Finding severity `CRITICAL` (16/18) not in Phase 08 set | Frontend accepts all | none | pending | 2026-10-01 |
| FE-C05 | UI | Baseline `source=REGRESSION`, `check_kind=TEST` (15) vs Phase 12 enums | Frontend accepts all | none | pending | 2026-10-01 |
| FE-C06 | UI | Checkpoint `WAITING_EXTERNAL` (16) vs `EXTERNAL_DEPENDENCY` (03) | Frontend accepts both | none | pending | 2026-10-01 |
| FE-C07 | UI | `IndexSource` `EXTERNAL_PUSH` (16) not in Phase 07 enum | Frontend accepts value | none | pending | 2026-10-01 |
| FE-C08 | UI | InboundEvent status `INFO` (16) not in Phase 05 enum | Frontend accepts value | none | pending | 2026-10-01 |
| FE-C09 | UI | REMEDIATION cycle INTAKE→PLANNING command name unspecified (01) | Display-only journey metadata | none | pending | 2026-10-01 |
| FE-C10 | UI | P17 neighborhood by `stable_key` vs P07 `/code/entities/{id}/neighbors` | Support both paths | none | pending | 2026-10-01 |
| FE-C11 | UI | Prompt evidence types SECURITY_SCAN / CODE_REVIEW / COMPATIBILITY_CHECK | Map to STATIC_REVIEW / MODEL_ASSESSMENT / EXTERNAL_CI | none | pending | 2026-10-01 |
| FE-C12 | UI | Prompt action names (repository.write_worktree, ALLOWED, etc.) | Map to tool + ActionStatus; display both | none | pending | 2026-10-01 |
| FE-C13 | UI | Prompt UNAFFECTED impact class | Not rendered; backend has no UNAFFECTED | none | pending | 2026-10-01 |
| FE-C14 | UI | TraceLink / LIKELY_IMPLEMENTS / GENERATED_FROM_TASK | SpecCodeLink + origins GENERATED_LINEAGE / DISCOVERED | none | pending | 2026-10-01 |
| FE-C15 | UI | Prompt `coding-primary` / LangGraphRuntime labels | Alias `implementation`; runtime from M-27 metadata | none | pending | 2026-10-01 |
| FE-C16 | UI | Generic 9-stage Command Center vs journey states | Macro-band presentation; APPROVAL as gate marker | none | pending | 2026-10-01 |
| FE-C17 | UI | Four-journey checkpointed fixture world (UI-19) | Deterministic engine + scenario controller; not backend E2E | none | pending | 2026-10-01 |
| FE-C18 | UI | Two runtime contexts (A Greenfield, B clone) | Fixture narrative only per SIM-D1 | none | pending | 2026-10-01 |
| FE-C19 | UI | IC-005 remediation supersedes IC-004 (SIM-D4) | Bug-fix checkpoint chain | none | pending | 2026-10-01 |
| FE-C20 | UI | Repository & Code at `/code` (SIM-D9) | `/repository` redirects | none | pending | 2026-10-01 |
| FE-C21 | UI | ControlDecision explainer (M-35) | Fixture-authored explain records | none | pending | 2026-10-01 |
| FE-C22 | UI | Runtime B TASK/EX/IC key numbering (SIM-D8) | Per-project sequences not simulated | none | pending | 2026-10-01 |

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
9. Overall State becomes `MVP_COMPLETE` only through Phase 19 §15.

---

## 15. PLANNING CHANGE LOG

| Date | Change |
|---|---|
| 2026-10-01 | Initial plan set created: `plans/README.md`, phases 00–18. |
| 2026-10-01 | Planning review and completion. Added Phase 19 and this `STATUS.md`. Reconciled cross-phase inconsistencies (each fix is the smallest compatible change):<br>• Phase 18 RC-05 and its startup reconciler now use the Phase 08 IC states (`INTEGRATING` retry on the same IC), not a nonexistent `BUILDING` IC state.<br>• Phase 18 sandbox fallback uses `OLYMPUS_ENV` `local`/`test`, not `dev`.<br>• Phases 16 and 18 compose commands use the root `docker-compose.yml` with `deploy/` overlays.<br>• Phase 15 uses `affected_sha` instead of "released SHA", to support the external-push defect path.<br>• Phase 07 classifies external imports (stdlib / declared dependency / undeclared; TECH §2 "importlib metadata").<br>• Phase 01 adds the `delivery_cycle_events` view (TECH §5.1; README D-15).<br>• README markers add `connector_live` and `ui`, and README §10 aligns with task-group progress tracking. |
| 2026-10-01 | **Frontend UI track:** `plans/frontend-ui-implementation.md` added. UI track pre-builds `apps/dashboard` ahead of Phase 16 with fixture adapters; Phase 17 backend dependency unchanged for live completion; no architectural invariant change. |
| 2026-10-01 | **Frontend UI v2:** Plan rewritten as v2 (UI-00..UI-18). Prior UI-01..UI-20 FIXTURE_COMPLETE claims reset; v1 skeleton acknowledged. Implementation in progress toward honest FIXTURE_COMPLETE per phase exit criteria. |
| 2026-10-01 | **Frontend UI v2 build:** `apps/dashboard` evolved to Software Delivery Control Room (ProjectShell, Command Center, Control Plane, DAG, Execution workspace, Code Intelligence, Lineage, Assurance, fixtures modularized). UI-00..UI-18 marked FIXTURE_COMPLETE in §16; live tier still NOT_STARTED (backend 00–17). |
| 2026-10-01 | **Repository materialization tightening (plan-only).** No new phase. README D-16/D-17 and §5.9 already define the ownership split, unified Repository / RepositoryWorkspace / ExecutionWorkspace model, configurable `OLYMPUS_WORKSPACE_ROOT`, Greenfield/Brownfield flows, candidate vs canonical revision and Code Index, connectors and credentials. This change syncs STATUS.md to those plans: Journey Readiness repository dependencies; eight repository/workspace invariants; §8 Repository Model / Workspace Model / Greenfield / Brownfield / Integration / Code Intelligence / Assurance / Release trackers; Phase 00–16 §14 ACs copied from the phase files; Q-11..Q-16 recorded. Phase 00 adds the workspace-root settings AC; Phase 18 RC-12 now backs up `OLYMPUS_WORKSPACE_ROOT`. No production code, migrations or adapters were added. |
| 2026-10-01 | **UI-19 Four-Journey Simulation:** checkpointed fixture engine (`buildWorld`), scenario controller + `ScenarioControlBar`, Repository & Code UX, consistency/determinism Vitest suite; plan `plans/frontend-four-journey-simulation.md`. |

---

## 16. FRONTEND UI TRACK

**Plan:** [plans/frontend-ui-implementation.md](plans/frontend-ui-implementation.md) (**v2**)

**Overall UI state:** `FIXTURE_COMPLETE`

**Data mode default:** `NEXT_PUBLIC_OLYMPUS_DATA_MODE=fixture` (development). Live mode requires control-api (Phases 00–16+).

**Phase states:** `NOT_STARTED | IN_PROGRESS | FIXTURE_COMPLETE | LIVE_PARTIAL | LIVE_VERIFIED | BLOCKED`

**v1 → v2 mapping:** v1 UI-01..03 → v2 UI-01/01b; v1 UI-04..07 → v2 UI-02..06; v1 UI-08..20 → v2 UI-07..18.

| Phase | Name | State | Milestone | Blockers |
|---|---|---|---|---|
| UI-00 | Docs + STATUS v2 | FIXTURE_COMPLETE | v2 plan + §16 reset | — |
| UI-01 | Alignment + Navigation | FIXTURE_COMPLETE | ProjectShell, services interface, isolation | — |
| UI-01b | Fixture world | FIXTURE_COMPLETE | SupportDesk modules + integrity test | — |
| UI-02 | Command Center | FIXTURE_COMPLETE | Active execution + macro forge | — |
| UI-03 | Control Plane | FIXTURE_COMPLETE | Inspector + ConditionGraph | — |
| UI-04 | Forge + DAG + Contract | FIXTURE_COMPLETE | TaskInspector + ContractView | — |
| UI-05 | Execution + Agents | FIXTURE_COMPLETE | Execution workspace + AgentOpsBoard | — |
| UI-06 | Resource / Actions | FIXTURE_COMPLETE | ActionGovernancePipeline | — |
| UI-07 | Code Intelligence base | FIXTURE_COMPLETE | Index bar + tabs | — |
| UI-08 | Explorer + Symbols | FIXTURE_COMPLETE | CodeSearch + IndexStatusBar | — |
| UI-09 | Lineage + Product | FIXTURE_COMPLETE | LineageExplorer + ProductTree | — |
| UI-10 | Index history | FIXTURE_COMPLETE | Index versions in code tab | — |
| UI-11 | Impact | FIXTURE_COMPLETE | ImpactFlow | — |
| UI-12 | Brownfield | FIXTURE_COMPLETE | Pipeline + knowledge chips | — |
| UI-13 | IC Forge | FIXTURE_COMPLETE | IcForge + integration route | — |
| UI-14 | Assurance + Evidence | FIXTURE_COMPLETE | Warden/Sentinel + tabs | — |
| UI-15 | Attention + Release | FIXTURE_COMPLETE | Inbox + EligibilityVerdict | — |
| UI-16 | Integrations + Audit | FIXTURE_COMPLETE | EventTimeline + integrations shell | — |
| UI-17 | Journey refinement | FIXTURE_COMPLETE | Defect page + journey nav | — |
| UI-18 | Hardening | FIXTURE_COMPLETE | vitest suite + @fixture Playwright | — |
| UI-19 | Four-Journey Simulation | FIXTURE_COMPLETE | Checkpointed world + playback bar + Repository & Code | — |
| UI-20 | Playwright fixture journeys (`@frontend-e2e`) | FIXTURE_COMPLETE | `tests/e2e/olympus/` — 4 journey specs, cross-cutting transparency, `COVERAGE.md`; not backend E2E | — |

### Journey visualization readiness (fixture / live)

| Journey | Fixture UI | Checkpointed fixture | Live UI |
|---|---|---|---|
| Greenfield | FIXTURE_COMPLETE (DC-001) | `greenfield:00..14` | NOT_STARTED (backend 00–10) |
| Brownfield | FIXTURE_COMPLETE (DC-002) | `brownfield:00..11` | NOT_STARTED (backend 00–12) |
| Feature Change | FIXTURE_COMPLETE (DC-003) | `feature-change:00..11` | NOT_STARTED (backend 00–14) |
| Bug Fix | FIXTURE_COMPLETE (DC-004) | `bug-fix:00..11` | NOT_STARTED (backend 00–15) |

### Missing backend APIs / events (frontend dependency)

| ID | Capability | Owner phase |
|---|---|---|
| M-01 | `GET /events/stream?project_id=&after=` | 01/17 |
| M-02 | `GET /events?project_id=&…` | 01/17 |
| M-03 | `GET /auth/me` | 01/18 |
| M-04 | Cycle/project executions list | 03/17 |
| M-05 | `GET /views/projects/{id}/agent-activity` | 17 |
| M-06 | `GET /agent-profiles` | 02/17 |
| M-07 | `GET /runtime/model-aliases`, `/runtime/workers` | 02/18 |
| M-08 | `GET /projects/{id}/model-usage` | 02/18 |
| M-09 | `GET /actions?project_id=&…` | 04/17 |
| M-10 | `GET /delivery-cycle-types/{type}/state-machine` | 01 |
| M-11 | `GET /lineage?root_type=&root_id=&direction=` | 08/17 |
| M-12 | Audit `correlation_id` search | 01/18 |
| M-13 | Cycle risk tier / target release | 17 |
| M-14 | Spec → tasks reverse query | 08/11 |
| M-15 | `GET /projects/{id}/resolve?key=` | 01 |
| M-16 | View shape `delivery-cycles/{id}/overview` | 17 |
| M-17 | View shape `/views/inbox` | 17 |
| M-18 | Connector health in list API | 16/18 |
| M-19 | Evidence `is_current_ic` flag | 09/17 |
| M-20 | SSE `id:` sequence framing | 01 |
| M-21 | IC progress events | 08 |
| M-22 | `GET /views/delivery-cycles/{id}/control-plane` | 17 |
| M-23 | Per-condition task eligibility explain | 03/17 |
| M-24 | GuardResult.details per dependency task | 01/17 |
| M-25 | `GET /code-index/versions/{a}/diff/{b}` | 07/08 |
| M-26 | Project list summary / delivery history fields | 17 |
| M-27 | `runtime_metadata.runtime` on execution read model | 02/03 |
| M-28 | `GET /projects/{id}/delivery-history` (or compose) | 17 |
| M-29 | Brownfield discovery per-step status | 11/17 |
| M-30 | Materialization step progress read model | 04/17 |
| M-31 | `GET /repositories/{id}/commit-ledger` | 04/17 |
| M-32 | ExecutionWorkspace uncommitted_files | 04/17 |
| M-33 | Artifact unified diff content | 03/08 |
| M-34 | Release eligibility `conditions[].subject_refs[]` | 10/17 |
| M-35 | ControlDecision explain API | 17 |
| M-36 | Scenario controller (fixture-only) | UI-19 |
| M-37 | Code index version diff by stable key | 07/08 |
| M-38 | Repository summary chip read model | 04/17 |
| M-39 | Checkpoint delta event stream (fixture) | UI-19 |
| M-40 | RuntimeMetadata current_action / current_resource | 03/17 |
| M-41 | Legacy `supportdesk-chained` → `bug-fix:11-released` alias | UI-19 |

**Phase 17 cross-reference:** Backend dashboard milestone remains `NOT_STARTED` until Phase 16 complete. Do not mark Phase 17 COMPLETE from fixture rendering alone. Prior v1 FIXTURE_COMPLETE claims were reset 2026-10-01 (v2 plan).
