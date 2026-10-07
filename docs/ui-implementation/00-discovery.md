# Phase 0 — Discovery

**Date:** 2026-10-07  
**Status:** Read-only discovery complete. **No frontend code written in this phase.**

## Writable path declaration (hard constraint)

| Path | Purpose |
|------|---------|
| **`apps/dashboard/`** | Sole application code directory for the Olympus operator UI (frontend). |
| **`docs/ui-implementation/`** | Discovery, plan, gap report, changelog, and implementation notes only. |

Everything else in the repository—including `apps/control_api/`, `core/`, agents, migrations, CI, Docker, and root config—is **read-only** for this effort.

### Frontend root confirmation

- **Expected (Architecture plan):** `apps/dashboard/`
- **Working tree (2026-10-07):** `apps/dashboard/` is **absent**—removed per `STATUS.md` (*“Remove legacy operator UI”*). Git `HEAD` still contains the prior Next.js app (~100+ files); the tree is deleted locally but recoverable from history.
- **Implication for Phase 2+:** Recreate `apps/dashboard/` as a **greenfield** control-plane-first UI, reusing the prior stack choices where sensible (see §3), not incrementally patching deleted files unless you explicitly choose to restore from `HEAD` first.

### Phase 0 git boundary check

After writing this document only:

```text
# Run after Phase 0 doc writes:
git status --porcelain  → only docs/ui-implementation/*
git diff --stat         → only docs/ui-implementation/*
```

---

## 1. Backend inventory

**Source:** Static analysis of `apps/control_api/` and `core/` (OpenAPI generation was not run in this environment—missing Python deps such as `uuid6`; route list was parsed from router modules). **205 HTTP routes** are registered on the Control API.

### 1.1 Authentication and command context

| Mechanism | Detail |
|-----------|--------|
| **Auth** | `Authorization: Bearer <token>` on protected routes (`apps/control_api/deps.py`). Missing/invalid → `UNAUTHENTICATED`. |
| **Scopes** | Per-route scope via `core.security.route_scopes.required_scope(request)`; failure → `FORBIDDEN`. |
| **Actor** | `GET /actors/me` → current actor profile. |
| **Tokens** | `POST /auth/tokens`, `POST /auth/tokens/{token_id}/rotate`, `POST /auth/tokens/{token_id}/revoke`. |
| **Idempotency** | Optional header `Idempotency-Key` on command paths using `command_context` dependency. |
| **Correlation** | `CorrelationIdMiddleware` (correlation ID on requests). |

Public / low-scope endpoints include `GET /health`, `GET /ready`, `GET /metrics`, and inbound integration webhooks under `/integrations/...` (separate auth).

### 1.2 Command endpoints (mutations the UI must use)

| Pattern | Body / headers | Notes |
|---------|----------------|-------|
| `POST /projects/{project_id}/delivery-cycles` | `CreateCycleRequest`: `type`, `objective`, optional `repository_id` | Creates cycle; returns `CycleResponse` with `allowed_commands`. |
| `POST /delivery-cycles/{cycle_id}/commands/{command_name}` | `CycleCommandRequest`: `expected_state`, optional `payload` | Dispatches `delivery_cycle.transition`; rejects recorded on conflict. |
| `POST /delivery-cycles/{cycle_id}/approvals` | `RequestApprovalBody`: approval subject + hash/version | |
| `POST /approvals/{approval_id}/decision` | `DecisionBody`: `decision` (`ApprovalStatus`), optional `note` | |
| `POST /tasks/{task_id}/commands/{command_name}` | `TaskCommandRequest`: `expected_state` | |
| `POST /executions/{execution_id}/cancel` | (command context) | |
| `POST /specs/{spec_id}/approve` | (command context) | |
| `POST /releases/{release_id}/approve` | (command context) | |
| `POST /releases/{release_id}/execute` | (command context) | |
| `POST /gates/{gate_id}/finalize` | | |
| `POST /task-plans/{plan_id}/commands/accept` | | |
| `POST /task-contracts/{contract_id}/commands/issue` | | |
| `POST /delivery-cycles/{cycle_id}/commands/rebase_cycle` | (impact router) | |
| `POST /reconciliation/{item_id}/resolve` | | Design: no retry UI for unknown connector—see gap report. |
| `GET /commands/catalog` | | Exported command catalog (metadata). |

**Never:** PATCH lifecycle/status fields from the UI.

**Delivery cycle `allowed_commands`** (on `GET/POST` cycle responses): `{ command, to_state, guard_preview[], allowed }` — guard evaluation only for **current state** edges (`core/domain/delivery_cycles/service.py`).

**Transition preview (richer “why not”):** `GET /delivery-cycles/{id}/next-transitions` and `views/.../overview` → `next_transitions[]` with `guard_results[]` per guard (`preview_to_api` in `core/state/preview.py`).

### 1.3 Aggregated read models (`/views/*`)

| Method | Path | Purpose |
|--------|------|---------|
| GET | `/views/projects/{project_id}/overview` | S01 tiles: active cycle, repo SHAs, blockers, embedded `cycle_overview`. |
| GET | `/views/projects/{project_id}/repository` | Repository materialization view. |
| GET | `/views/projects/{project_id}/coverage` | Coverage counts (includes `%` for AC evidence—UI must **not** show invented overall %). |
| GET | `/views/delivery-cycles/{cycle_id}/overview` | Cycle summary + `next_transitions`. |
| GET | `/views/delivery-cycles/{cycle_id}/control-plane` | **Partial** control-plane dashboard (counts/flags only—see §1.6). |
| GET | `/views/tasks/{cycle_id}/dag` | Task DAG read model for S04. |
| GET | `/views/code/entities/{stable_key}/neighborhood` | Code neighborhood for S06. |
| GET | `/views/ic/{ic_id}/assurance` | Assurance composite for S09. |
| GET | `/views/inbox` | Approvals + open clarifications (attention inputs). |
| GET | `/views/projects/{project_id}/agent-activity` | Agent execution activity (S05 context only—not nav). |

### 1.4 Event stream (SSE)

| Endpoint | Format |
|----------|--------|
| `GET /delivery-cycles/{cycle_id}/events/stream` | SSE: `id: <sequence>`, `event: <event_type>`, `data: JSON` `{ id, sequence, event_type, payload }`. Resume: `Last-Event-ID` header. |
| `GET /events/stream?project_id=` | Global stream; resume via `after` query or `Last-Event-ID`. |
| `GET /delivery-cycles/{cycle_id}/events` | Paged poll: `after_sequence`, `limit`. |

**UI rule:** SSE **invalidates/refetches** TanStack Query caches; it does not apply optimistic lifecycle completion.

### 1.5 Domain enums (UI-facing values)

Lifecycle **state strings** are plain strings on `DeliveryCycle.state` (not a single enum type). Machines in `core/state/machines.py`:

| `DeliveryCycleType` | States (non-terminal) | Terminal |
|---------------------|-------------------------|----------|
| `GREENFIELD_BUILD` | DISCOVERY → PRODUCT_MODEL → ARCHITECTURE → PLANNING → DEVELOPMENT → INTEGRATION → ASSURANCE → RELEASE | COMPLETE, CANCELLED, FAILED |
| `BROWNFIELD_ONBOARDING` | RECON → CODE_INDEX → RECOVERED_SPEC → BASELINE → READINESS → (REMEDIATION loop) | READY, CANCELLED, FAILED |
| `FEATURE_CHANGE` | INTAKE → SPEC_DELTA → IMPACT_ANALYSIS → PLANNING → … (shared tail with greenfield) | COMPLETE, … |
| `BUG_FIX` | TRIAGE → REPRODUCTION → EXPECTED_BEHAVIOR → ROOT_CAUSE → DEVELOPMENT → INTEGRATION → REGRESSION → ASSURANCE → RELEASE | COMPLETE, … |
| `REMEDIATION` | INTAKE → PLANNING → … | COMPLETE, … (backend-only fifth journey; design pack focuses on four) |

Other enums commonly surfaced: `TaskStatus`, `ExecutionStatus`, `ApprovalStatus`, `ApprovalType`, `SpecStatus`, `SpecKind`, `KnowledgeClass`, `ICStatus`, `GateStatus`, `GateType`, `EvidenceType`, `EvidenceResult`, `ObligationStatus`, `ReleaseStatus`, `ReadinessResult`, `ActionStatus`, `ConnectorActionStatus`, `SpecCodeLinkOrigin`, `RelationType` (code index), `FindingStatus`, etc. (`core/domain/enums.py`, `core/assurance/enums.py`, `core/integration/enums.py`, …).

### 1.6 Critical API shape vs design S02

`GET /views/delivery-cycles/{cycle_id}/control-plane` returns **aggregates only**:

```json
{
  "delivery_cycle_id", "scheduler": { "queued_tasks", "blocked_tasks" },
  "execution_manager": { "running" }, "policy": { "denied_actions" },
  "integration": { "active_ic" }, "assurance": { "sentinel_fail" },
  "release": { "eligible" }
}
```

There is **no** server-side `{ nodes, edges, lanes }` graph for the six-lane map. The UI must **compose** graph nodes from many resource endpoints (cycles, tasks, executions, IC, specs, evidence, releases, lineage, …) via a frontend `buildControlPlaneGraph` adapter—only showing **materialized** records and **backend-expressed** obligations (e.g. open obligations, pending approvals), never inventing nodes from lifecycle alone.

### 1.7 Full route catalog

A machine-generated listing of all **205** routes is recorded in discovery artifact `routes.txt` (same directory). Grouped by concern:

- **Projects & cycles:** projects, delivery-cycles, next-transitions, brownfield discovery/recovery/knowledge, readiness, promotion, change-interpretation, spec-delta, architecture-delta.
- **Product model:** sources, decompose/derive, capabilities, features, specs, spec-deltas, clarifications, defects, change-requests.
- **Planning:** architecture, implementation-specs, task-plans, task-dag, accept/issue commands.
- **Work:** tasks, dependencies, contracts, eligibility, executions, workspaces, actions, artifacts, candidate-commits.
- **Code:** code-index rebuild/versions, entities, search, paths, canonical refresh.
- **Integration & assurance:** integration-candidates, gates, obligations, evidence, coverage, findings, warden/sentinel triggers, verification-plans, reviews.
- **Release:** release-eligibility, release CRUD, manifest, approve/execute, outcome.
- **Lineage & impact:** feature/code lineage, impact-assessments, staleness, rebase_cycle.
- **Integrations & audit:** inbound events, connector configs/actions, reconciliation, audit log.
- **Orchestrator:** sessions/turns (Ask Olympus candidate—if used).
- **Ops:** health, policy/current, secrets, external-links.

---

## 2. Existing frontend inventory

| Item | Finding |
|------|---------|
| **Presence** | **None in working tree.** Last committed app at `apps/dashboard/` (Next.js **16.3.8**, React, TypeScript). |
| **Routing** | App Router: `(auth)/login`, `(console)/projects/...`, cycle routes under `projects/[projectId]/cycles/[cycleId]`, feature-specific pages (assurance, code, brownfield, control-plane, tasks, …). |
| **Data** | TanStack Query v5; API client layer under `lib/` (in git history). |
| **Styling** | Tailwind + shadcn/ui (Radix), `globals.css`. |
| **Graph / DAG** | `@xyflow/react`, `elkjs` for layouts—not the design’s lane-grid + SVG overlay grammar. |
| **Tests** | Vitest unit tests; Playwright e2e (`test:e2e`, journey grep). CI dashboard job **removed** per STATUS.md. |
| **Env** | Prior dashboard used `NEXT_PUBLIC_*` API base (see deleted `README` in git); root `.env.example` has **no** dashboard vars at present—Phase 2 must document `NEXT_PUBLIC_OLYMPUS_API_URL` (or equivalent) inside `apps/dashboard/` only. |

---

## 3. Capability map (design → backend)

Legend: **Available** = direct API; **Derivable** = faithful client projection; **Missing** = show documented unavailable + gap report.

| UI element | Design source | Backend | Status |
|------------|---------------|---------|--------|
| Delivery cycle (type, state, objective, base_sha) | S02, ribbon | `GET /delivery-cycles/{id}`, list on project | **Available** |
| Lifecycle stages (ordered) | Ribbon, spine | `core/state/machines.py` per `type`; current = `cycle.state` | **Derivable** (map in frontend config; must use backend state names) |
| Control-plane graph nodes/edges | S02, `05-graph-grammar` | No unified graph API | **Derivable** (multi-fetch + adapter); high complexity |
| Control-plane strip tiles | Legacy + design attention | `/views/.../control-plane` | **Available** (partial—no per-node detail) |
| Attention queue ordering | AttentionStrip | `/views/inbox` + cycle overview counts; no explicit priority field | **Derivable** (merge + design order unless server adds priority) |
| Why this state? (cycle) | WhyPanel | `next-transitions`, `allowed_commands.guard_preview`, transition rejections | **Partial** — predicates for **transitions**, not a generic per-record Why API |
| Why this state? (task) | S04 | `blocked_reason`; `GET /tasks/{id}/eligibility` → `{ eligible, reasons[] }` | **Available** (scheduler predicates) |
| Why this state? (release) | S10 | `GET .../release-eligibility` → `conditions[]` with `ok`, `reasons` | **Available** |
| Why this state? (gate) | S09 | `GET /gates/{id}`, finalize inputs; IC assurance view | **Partial** |
| Permitted commands (cycle) | Inspector | `allowed_commands` on cycle | **Available** |
| Permitted commands (task) | Inspector | Task command endpoints; no `allowed_commands` list on `TaskResponse` | **Derivable** via task state machine rules **or** **Missing** explicit list—use command catalog + disabled until tried |
| ProductSource | IN lane | `POST/GET .../sources`, content | **Available** |
| Capability / Feature | IN | `GET .../capabilities`, `.../features`, `{feature_id}` | **Available** |
| FeatureSpec + versions | S03 | `GET/POST .../specs`, `GET /specs/{id}` | **Available** |
| Acceptance criteria | S03 | Embedded in spec payloads / product model routes | **Available** (via spec detail) |
| ImplementationSpec | S03 | planning routes | **Available** |
| Architecture | S03 | `GET .../architecture`, propose commands | **Available** |
| ChangeRequest | FC intake | change-requests routers | **Available** |
| Defect | BG | defects routers + trace/reproductions/root-cause | **Available** |
| Task / TaskDependency | WK | tasks + dependencies | **Available** |
| TaskContract | S04 | contracts routers | **Available** |
| Execution / Snapshot | S05 | executions + snapshot | **Available** |
| Lease | S05 boundary | Snapshot / workspace payloads (not separate lease API in route list) | **Partial** — inspect execution/snapshot models in responses |
| Worktree / workspace | S05 | `/executions/{id}/workspace`, `/worktree` | **Available** |
| ToolAction | S05 timeline | `/executions/{id}/actions` | **Available** |
| CandidateCommit | CD provisional SHA | candidate-commits routes | **Available** |
| IntegrationCandidate | CD canonical target | integration + integration-candidates | **Available** |
| CodeIndexVersion / entities / relations | S06 | code_intelligence + repository canonical | **Available** |
| SpecCodeLink | S06 | via code/spec routes and lineage (confirm in spec detail) | **Partial** — may require multiple calls |
| ImpactAssessment | S08 | impact-assessments routes | **Available** |
| Recovered spec / observed / uncertainty | BF S03 | brownfield discovery, recovery, knowledge, observed-behaviors | **Available** |
| Baseline / promotion | EV/BF | baselines, promotion-decisions, review-queue | **Available** |
| Evidence / obligations / coverage | S09 | assurance evidence, obligations, coverage | **Available** |
| Finding | S09 | findings + remediate/waive | **Available** |
| Gate / finalize | S09 | gates routes + warden/sentinel | **Available** |
| Approval / Checkpoint | Dialogs | approvals, clarifications | **Available** |
| Release / manifest / eligibility | S10 | releases router | **Available** |
| Deployment | S10 separate | `ApprovalType.DEPLOYMENT`; connector actions—not a green “deployed” badge without result | **Partial** |
| Lineage graph | S07, Trace lens | `/features/{id}/lineage`, `/code/entities/{id}/lineage` | **Available** |
| Relation origin + confidence | Inspector | Lineage edge payloads; spec-code link enums | **Available** where persisted |
| Inbound events | IO | `/integrations/inbound-events` | **Available** |
| Connector actions | IO | `/connector-actions/{id}` | **Available** |
| Reconciliation | IO | `/reconciliation` (+ retry API exists) | **Available**; UI must **hide retry** for `UNKNOWN` per design truth rules |
| Audit | AU | `/audit`, `/audit/verify` | **Available** |
| Ask Olympus | Drawer | `/orchestrator/sessions` + turns | **Available** (optional; ship disabled if product defers) |
| SHA scopes (provisional / canonical / released) | ShaScopeBanner | repository `canonical_commit`, `released_commit`, execution candidate, IC integrated SHA | **Derivable** from repository + IC + execution endpoints |
| Brownfield readiness (no release) | S10 BF | `/delivery-cycles/{id}/readiness`, cycle type `BROWNFIELD_ONBOARDING` | **Available** |
| Stage history (ribbon scrub) | Ribbon | No dedicated stage-history API | **Missing** — past stages not clickable |
| Future obligation nodes | Graph grammar | Obligations API per IC; pending approvals | **Partial** — only where backend lists obligations/requirements |

---

## 4. Existing frontend vs design (last committed `apps/dashboard/`)

| Legacy screen / area | Design target | Action |
|----------------------|---------------|--------|
| `projects/[id]/page.tsx` (overview) | S01 | **Restructure** — truth tiles, explicit denominators, cycle history |
| `cycles/[cycleId]/page.tsx`, `control-plane/page.tsx` | S02 hub | **Replace** — six-lane graph, inspector, lenses, list mode |
| `command-center/*`, `control-plane/*` panels | S02 AttentionStrip + subgraph | **Replace** — design grammar, not KPI strip |
| `product/page.tsx` | S03 | **Restructure** — journey modes |
| `cycles/.../tasks/page.tsx`, DAG components | S04 | **Restructure** — lane strip, eligibility panel |
| `executions/[id]/page.tsx` | S05 | **Restructure** |
| `code/page.tsx` | S06 | **Restructure** — ShaScopeBanner, three-way scope |
| `lineage/page.tsx` | S07 | **Restructure** |
| `impact/page.tsx` | S08 | **Restructure** |
| `assurance/page.tsx` | S09 | **Restructure** — evidence matrix rules |
| `releases/page.tsx` | S10 | **Restructure** |
| `integrations/page.tsx` | IO utility | **Restyle** + reconciliation UX |
| `audit/page.tsx` | AU utility | **Keep** route, **restyle** |
| `inbox/page.tsx` | Attention (global) | **Merge** into S01/S02 attention model; optional redirect |
| `agents/page.tsx` | — | **Delete** from primary nav (agents only in execution context) |
| `@xyflow` DAG as primary map | Lane grid graph | **Replace** |
| shadcn/ui primitives | Design tokens + components | **Restyle** / extend |
| Playwright journeys | Phase 7 | **Replace** scenarios for four journeys + real backend |

---

## 5. Source documents located

| Source | Path |
|--------|------|
| UI Design Pack PDF | `docs/design/olympus-ui-spec/Olympus_UI_Design_Pack_v1.0.pdf` |
| Design specification | `docs/design/olympus-ui-spec/` (sections 01–07, tokens, components, reference-implementation) |
| Architecture / technical spec | Implementation plans under `plans/` (e.g. phases 06–19); no separate `docs/` PDF copy found in repo |

---

## 6. Phase 0 exit checklist

- [x] Writable paths declared
- [x] Backend routes, commands, SSE, enums inventoried
- [x] Frontend status documented (removed; baseline from git)
- [x] Capability map drafted
- [x] Legacy vs design mapping recorded
- [ ] **Awaiting approval before Phase 2 code**
