# Phase 17 — Dashboard, Operator Experience and Orchestrator

## 1. Objective

Deliver the **thin operator command center** (TECH §25; ARCH §3 primary operator: Product Owner / Engineering Lead):

- a Next.js + TypeScript + shadcn/ui + TanStack Query dashboard that is a **projection of authoritative APIs and events**. It emphasizes delivery outcomes and lineage, not chat transcripts;
- the read-model endpoints it needs;
- the **Orchestrator** agent (live LLM): it explains state, routes clarification answers and **proposes** typed commands, which execute only after explicit human confirmation through the command API.

All human governance actions are operable from the UI: approvals, clarifications, scope, spec deltas, promotion decisions, waivers, release approval, reconciliation and deployment.

## 2. Architectural Context

- **Position:** `apps/dashboard` (Next.js), `apps/control_api/routers/views/*` (read models), `agents/orchestrator`.
- **Upstream:** all domain APIs (01–16), SSE `/events/stream` (01), OpenAPI (00).
- **Downstream:** 19 (Playwright E2E drives journeys through the UI).
- **Invariants:**
  - The UI never computes authoritative state: eligibility, gate status and readiness come from APIs.
  - Every mutating UI action is a typed command with an `Idempotency-Key` and a HUMAN actor.
  - Conversation is only an interaction surface. The Orchestrator writes no canonical state (TECH §11 table).
  - Brownfield knowledge classes are visually distinct (FACT / INFERENCE / UNCERTAINTY / DECISION / ASSUMPTION).
  - Retrieval sources and confidence are always shown in Code Intelligence and Impact views.

## 3. Current Repository Assessment

Inspection on 2026-10-01: no frontend exists.

### Existing
- (after 01–16) REST APIs and SSE — **RETAIN**. Some list endpoints lack the aggregation the views need — **EXTEND** (read-model routers).

### Partial
- The OpenAPI schema is exposed but there is no TS client generation — **ADD**.

### Missing
- `apps/dashboard`, the read models, `agents/orchestrator`, Playwright UI tests — **ADD**.

### Refactor / Migration Required
- None. Read models are additive and query-only.

## 4. Scope

1. **Dashboard scaffold** `apps/dashboard`:
   - Next.js (App Router), TypeScript strict, shadcn/ui, Tailwind, TanStack Query, `openapi-typescript` + `openapi-fetch` generated client from `/openapi.json`;
   - auth: API-token login stored in an httpOnly cookie via a Next route handler that proxies to control-api;
   - pnpm workspace inside `apps/dashboard`;
   - Dockerfile, plus a compose service `dashboard`.
2. **SSE integration**: a single `EventSource` per session on `/events/stream?after=<last_event_id>` with resume. The event-type → query-key invalidation map lives in `lib/events.ts`. The UI refetches authoritative state and never applies event payloads as state.
3. **Views** (TECH §25 table plus governance inboxes):

   | Route | Content (all data from APIs) |
   |---|---|
   | `/projects` | list; readiness state; current release |
   | `/projects/[id]` | **Project overview**: current release, active cycle(s), product/spec/code coverage (ACs with evidence %, features with links %), blockers (blocking findings, pending approvals, reconciliation items) |
   | `/projects/[id]/cycles/[cid]` | **Delivery Cycle**: lifecycle stepper with current state and guard results for the next transition (from `GET /delivery-cycles/{id}/next-transitions`), approvals, task DAG (graph view), executions, current action |
   | `/projects/[id]/product` | **Product / Specs**: capability → feature tree; FeatureSpec versions with diff view (SpecDelta); ImplementationSpec versions; AC coverage per spec |
   | `/projects/[id]/repository` | **Repository**: source type (GREENFIELD_MANAGED / EXTERNAL_CLONE), provider, remote URL, default branch, status, `registered_sha` / `canonical_commit` / `released_commit`, canonical revision history (cause, IC/release/event refs), materialization attempts with retry, canonical workspace logical location + state, `credential_ref` name + status, sync events. No physical path or secret value is ever rendered. |
   | `/projects/[id]/code` | **Code Intelligence**: canonical index SHA badge (equal to `canonical_commit`); hybrid search with source labels; entity page with graph neighborhood (relations depth 1–2) and SpecCodeLinks (origin + confidence + status); Feature/Spec → CodeEntity traversal |
   | `/executions/[id]` | **Execution**: TaskContract (version, hash), snapshot (hash, content, repository revision), ExecutionWorkspace (logical location, mode, branch, base commit, state), event timeline, checkpoints/continuations, candidate commit diff, model calls (alias, provider, model, tokens, cost, latency, retries), tool/action requests with decisions |
   | `/projects/[id]/brownfield` | **Brownfield Intelligence**: discovery facts, ObservedBehaviors, RecoveredSpecs with knowledge-class chips, citations (file:line links), confidence + cap reason, reconciliation status; baseline review; readiness metrics; promotion decision forms |
   | `/impact/[iaId]` | **Impact Explorer**: items grouped by type, path visualization, retrieval source and confidence, selected-for-verification flag, architecture-delta flag |
   | `/projects/[id]/assurance` | **Assurance**: per IC, obligations (reason, status), evidence (type, SHA, result, artifact), gates (status, finalized_by), Warden findings (severity, blocking, remediation tasks), repair loop history |
   | `/defects/[id]` | Defect: triage, reproductions (pre/post), trace candidates, root cause (INFERENCE label), expected-behavior resolution |
   | `/change-requests/[id]` | CR: interpretation, candidates, delta, IA, release |
   | `/projects/[id]/integrations` | **Integrations**: inbound events (status, source, correlation), connector actions (status, attempts, idempotency key, external id), reconciliation items with retry/resolve, repository events (drift), connector config/health |
   | `/releases/[id]` | **Release**: manifest, exact SHA, gates, approvals, eligibility conditions with pass/fail reasons, deployment state, approve/deploy/rollback |
   | `/inbox` | **Governance inbox**: pending approvals (subject + hash), open clarifications, promotion decisions, escalated reconciliations; each with a decision form |
   | `/lineage` | **Lineage explorer**: forward (source/AC → release) and backward (code entity → spec) queries (Phase 08 API) |
   | `/audit` | audit event search by entity/correlation id |

4. **Read-model endpoints** (`apps/control_api/routers/views/*`, query-only, no new tables):
   - `GET /views/projects/{id}/overview`
   - `GET /views/projects/{id}/repository` (composes Phase 01/04/16 repository, revision, materialization and sync reads; `credential_ref` name + `credential_status` only)
   - `GET /views/delivery-cycles/{id}/overview`
   - `GET /delivery-cycles/{id}/next-transitions` (evaluates the guards of outgoing edges in dry-run mode: `TransitionService.preview`, no locks, no writes)
   - `GET /views/tasks/{cycle_id}/dag`
   - `GET /views/code/entities/{stable_key}/neighborhood?depth=`
   - `GET /views/ic/{id}/assurance`
   - `GET /views/inbox`
   - `GET /views/projects/{id}/coverage`
5. **Orchestrator agent** (`orchestrator.converse`, live):
   - Input: user message, the project/cycle overview read model (structured), pending approvals/clarifications, the command catalog (names + JSON schemas + required actor), and recent conversation (UI session only, non-canonical).
   - Output `OrchestratorTurn`:
     - `intent` ∈ {EXPLAIN, ANSWER_CLARIFICATION, PROPOSE_COMMAND, NAVIGATE, OUT_OF_SCOPE};
     - `message` (explanation with entity refs);
     - `proposed_command` (`{command, target_ref, args}`, validated against the catalog schema);
     - `clarification_answer_draft` (`{clarification_id, answer}`);
     - `refs` (entity keys cited).
   - Executed as an Execution (Task origin CONTROL_PLANE, work_type ANALYSIS; D-12) with priority scheduling. The structured output is persisted as an artifact; the conversation text is not canonical.
   - Deterministic validation:
     - the command exists, the args are schema-valid, and the target ref exists;
     - the command is permitted for the current user's role;
     - refs exist;
     - proposals for approval decisions are allowed only as **drafts**: the user must open the approval form.
   - The UI renders the proposal as a confirmation card. Confirming sends the typed command as the HUMAN user with an `Idempotency-Key`. The Orchestrator never calls the command API itself.
   - The chat panel is available on project/cycle pages. History is stored in `orchestrator_sessions` (non-canonical, retention-limited).
6. **Role model in the UI**: actors' roles (OPERATOR, APPROVER, VIEWER) from Phase 01 `actors`. Decision forms are hidden or disabled when the role is missing (the server enforces it regardless).
7. **Accessibility and quality**: keyboard-navigable forms, ARIA labels on graph views, ESLint + TypeScript strict, Vitest unit tests for lib code, Playwright UI tests.

## 5. Out of Scope

- Full-journey E2E proof through the UI (19).
- Multi-tenant org management and SSO (post-MVP).
- Editing code in the UI.

### Do Not Change
- No new write endpoints for the UI. All mutations use existing command endpoints.
- No business rules duplicated in TypeScript (eligibility, gate logic, readiness thresholds).

## 6. Domain / Data Model Changes

Migration `0027_p17_orchestrator_sessions.py` (rebase on 18 if merged later):

```python
class OrchestratorSession(Base, UUIDPkMixin, TimestampMixin):
    __tablename__ = "orchestrator_sessions"
    actor_id: Mapped[uuid.UUID]
    project_id: Mapped[uuid.UUID | None]
    delivery_cycle_id: Mapped[uuid.UUID | None]
    turns: Mapped[list] = mapped_column(
        JSONB, default=list
    )  # [{role, text, execution_id, proposal_ref}] — non-canonical
    expires_at: Mapped[datetime]
```

`OrchestratorTurn` schema:

```python
class ProposedCommand(BaseModel):
    model_config = ConfigDict(extra="forbid")
    command: str
    target_ref: str
    args: dict
    rationale: str


class OrchestratorTurn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    intent: Literal[
        "EXPLAIN", "ANSWER_CLARIFICATION", "PROPOSE_COMMAND", "NAVIGATE", "OUT_OF_SCOPE"
    ]
    message: str
    refs: list[str]
    proposed_command: ProposedCommand | None = None
    clarification_answer_draft: dict | None = None
    navigate_to: str | None = None
```

## 7. State / Lifecycle Changes

No new state machines. `TransitionService.preview(cycle, command)` is added: a guard dry-run returning `GuardResult[]`, read-only, never cached as truth.

## 8. API / Contract Changes

| Method | Path | Notes |
|---|---|---|
| GET | `/views/...` (§4.4) | read models |
| GET | `/delivery-cycles/{id}/next-transitions` | guard preview |
| GET | `/commands/catalog` | command names, JSON schemas, required roles (generated from the command registry) |
| POST | `/orchestrator/sessions` | create session |
| POST | `/orchestrator/sessions/{id}/turns` | user message → schedules `orchestrator.converse` → returns execution id; result via SSE `orchestrator.turn_completed` |
| GET | `/orchestrator/sessions/{id}` | turns |

TS client: `apps/dashboard/lib/api/schema.d.ts` generated by `pnpm gen:api` (CI checks it is up to date).

## 9. Services / Modules

| Path | Responsibility |
|---|---|
| `apps/dashboard/app/**` | routes/views §4.3 |
| `apps/dashboard/components/{lifecycle,dag,graph,diff,evidence,knowledge-chip,confirm-command,approval-form}/*` | shared components |
| `apps/dashboard/lib/{api,events,auth,format}.ts` | client, SSE map, auth |
| `apps/control_api/routers/views/*.py` | read models |
| `core/state/preview.py` | guard preview |
| `core/commands/catalog.py` | catalog export |
| `agents/orchestrator/{profile,prompts/converse.md,schemas}.py` | Orchestrator |
| `core/orchestrator/{service,validator}.py` | session + validation + scheduling |
| `tests/ui/*.spec.ts` | Playwright UI tests |

## 10. Development Tasks

- [ ] 17.1 Scaffold `apps/dashboard` (Next.js, TS strict, shadcn/ui, TanStack Query, ESLint, Vitest, Playwright). Add the Dockerfile and compose service.
- [ ] 17.2 Add the OpenAPI client generation + CI freshness check.
- [ ] 17.3 Add the auth proxy route handler + login page.
- [ ] 17.4 Add SSE resume + the invalidation map.
- [ ] 17.5 Add the read-model endpoints + `TransitionService.preview` + command catalog.
- [ ] 17.6 Build the Project overview and Delivery Cycle (stepper with guard preview, DAG) views.
- [ ] 17.7 Build the Product/Specs view with the version diff.
- [ ] 17.8 Build the Code Intelligence view (search, entity, neighborhood, links) and the Repository view (metadata, revision history, materialization retry, sync events).
- [ ] 17.9 Build the Execution view (contract, snapshot, events, model calls, actions, diff).
- [ ] 17.10 Build the Brownfield view + promotion decision forms + readiness.
- [ ] 17.11 Build the Impact Explorer.
- [ ] 17.12 Build the Assurance view.
- [ ] 17.13 Build the Defect and Change Request views.
- [ ] 17.14 Build the Integrations view + reconciliation actions + connector config.
- [ ] 17.15 Build the Release view + approve/deploy/rollback.
- [ ] 17.16 Build the Governance inbox + approval/clarification forms.
- [ ] 17.17 Build the Lineage explorer and Audit search.
- [ ] 17.18 Add the Orchestrator profile, validator, session API and chat panel with confirmation cards.
- [ ] 17.19 Write the tests in §12.

## 11. LLM-Dependent Tasks

| Item | Detail |
|---|---|
| Profile | `orchestrator.converse` |
| Why | Natural-language intent classification and explanation over structured state |
| Inputs | user message (UI), overview read model (DB), pending items (DB), command catalog (registry), session turns (non-canonical) |
| Output | `OrchestratorTurn` |
| Runtime / alias | LangGraphRuntime / `orchestration` (D-11) |
| Validation | catalog membership, args schema, role permission, refs exist; approval decisions are drafts only |
| Retries / failure | schema retry ×2; on failure, a deterministic fallback message "I could not interpret that; here are the available actions" + catalog (no proposal) |
| Cost logging | `model_calls` with `purpose=orchestration` |
| Live test | `test_orchestrator_live.py`: on a seeded cycle with one pending clarification, "answer the open question: closed tickets return 409" gives ANSWER_CLARIFICATION with the correct clarification id; "what is blocking the release?" gives EXPLAIN citing the blocking finding key; "approve scope" gives a PROPOSE_COMMAND draft, nothing executed (no approval decided in DB) |

## 12. Testing Strategy

### Unit Tests
- Vitest: SSE invalidation map, formatters, knowledge-chip mapping, command-confirmation payload builder (`Idempotency-Key` present).
- Python: the read models' query correctness on seeded rows; preview has no side effects (row counts and `state_version` unchanged).
- Orchestrator validator: unknown command, bad args, missing role, unknown ref.

### Integration Tests
- Read models return consistent data with the underlying endpoints (contract tests).
- `/commands/catalog` covers every registered command.
- The OpenAPI client compiles (`pnpm tsc --noEmit`).

### UI Tests (Playwright; backend seeded via real APIs with human-authored inputs; not journey proof)
- Login; the project overview renders blockers.
- The approval inbox approves a scope approval and the cycle stepper advances via SSE without reload.
- A clarification answer form creates the answer.
- The Brownfield view shows FACT/INFERENCE/UNCERTAINTY chips distinctly and a promotion decision persists.
- Impact Explorer shows source labels and paths.
- The Release view shows failing eligibility conditions with reasons and the Approve button disabled when not eligible.
- Reconciliation retry from the UI.
- A VIEWER role sees disabled decision forms, and the server rejects a forged request (403).

### Runtime / Live-LLM Tests
- The §11 live test.
- The Orchestrator chat panel in Playwright (`live_llm` + `ui` markers): proposal → confirm → command executed as HUMAN with the audit actor = user.

### Commands
```
cd apps/dashboard && pnpm install && pnpm gen:api && pnpm lint && pnpm typecheck && pnpm test
make dev   # control-api + workers + dashboard
cd apps/dashboard && pnpm exec playwright test tests/ui
LLM_LIVE_TESTS=1 uv run pytest -m live_llm --live-required tests/integration/live_llm/test_orchestrator_live.py
```

## 13. Milestone

An operator can run every governance step of the four journeys from the dashboard:
- see project, cycle, product, code, execution, Brownfield, impact, assurance, integration and release state projected live from authoritative APIs over SSE;
- decide approvals, clarifications, promotions, waivers, reconciliations, releases and deployments through typed commands;
- converse with a live Orchestrator that explains state and proposes commands that only execute after explicit human confirmation.

## 14. Acceptance Criteria

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

## 15. Exit Criteria

- §14 green.
- `STATUS.md` Frontend/Operator Experience tracker updated, plus live LLM readiness for the Orchestrator.
- The generated API client is committed and checked fresh in CI.

## 16. Dependencies

### Depends On
- 16. All domain APIs including integrations exist.

### Blocks
- 19.

### Can Run In Parallel With
- 18.
  - 17 owns `apps/dashboard`, `routers/views`, `core/state/preview.py`, `core/commands/catalog.py` and `agents/orchestrator`.
  - 18 owns telemetry, security hardening and recovery in `core/*` and `apps/*/main.py`.
  - Coordinate on the auth middleware (18 hardens tokens; 17 consumes the same API) and the migration chain (17's `0027` and 18's migration must be linearized at merge).

## 17. Risks / Implementation Notes

- **Graph rendering performance:** limit neighborhood depth to 2 and items to 200, and use a virtualized list fallback.
- **Orchestrator over-reach:** strict validator and confirmation-only execution. Approvals are never auto-proposed as final decisions.
- **API drift breaks the UI:** generated types + CI freshness check.
- **SSE through the Next proxy:** use a direct control-api origin with CORS for SSE, or a streaming route handler. Pick the streaming route handler for the cookie-auth simplicity.

## 18. Deliverables

- Code: `apps/dashboard/**`, read-model routers, guard preview, command catalog, `agents/orchestrator/*`, `core/orchestrator/*`.
- Migration: `0027`.
- APIs/events: §8 (+ `orchestrator.turn_completed`).
- Config: compose `dashboard` service, `orchestration` alias in `config/models.yaml`.
- Tests: Vitest, Playwright UI, Orchestrator live.
