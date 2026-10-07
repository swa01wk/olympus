# Phase 17 — Operator Read Models and Orchestrator

> **Scope:** backend only (`control_api`, `core/orchestrator`, `agents/orchestrator`). No operator UI in this phase. Filename kept for history.

## 1. Objective

Deliver the **control-plane surface** any operator client needs (TECH §25 read models; ARCH §3 primary operator: Product Owner / Engineering Lead):

- **Read-model** HTTP endpoints that aggregate authoritative domain state for projects, cycles, repository, code, assurance, inbox, and related views;
- **Guard preview** and **command catalog** so clients can show why transitions are blocked and which typed commands are valid;
- the **Orchestrator** agent (live LLM): explains state, drafts clarification answers, and **proposes** typed commands. Proposals execute only after explicit human confirmation via the existing command API (never from the agent runtime).

Operator **UI** is **out of this phase** (separate client repo or future `apps/*` UI); Phase **19** journey proof uses API + journey tests until a client exists.

## 2. Architectural Context

- **Position:** `apps/control_api/routers/views/*` (read models), `core/state/preview.py`, `core/commands/catalog.py`, `agents/orchestrator`, `core/orchestrator`.
- **Upstream:** all domain APIs (01–16), SSE `/events/stream` (01), OpenAPI (00).
- **Downstream:** 19 (full-journey acceptance; may use any client).
- **Invariants:**
  - Clients never compute authoritative state: eligibility, gate status and readiness come from APIs.
  - Every mutating operator action is a typed command with an `Idempotency-Key` and a HUMAN actor (no UI-specific write endpoints).
  - Conversation is only an interaction surface. The Orchestrator writes no canonical state (TECH §11 table).
  - Read models expose knowledge class, retrieval source, link origin and confidence fields needed for TECH §25 views (presentation is the client's job).

## 3. Current Repository Assessment

### Existing
- (after 01–16) REST APIs and SSE — **RETAIN**. Some list endpoints lack the aggregation operator clients need — **EXTEND** (read-model routers).

### Missing (Phase 17)
- Read models, guard preview, command catalog, `agents/orchestrator` — **ADD**.

### Refactor / Migration Required
- None. Read models are additive and query-only.

## 4. Scope

1. **Read-model endpoints** (`apps/control_api/routers/views/*`, query-only, no new tables except orchestrator sessions):
   - `GET /views/projects/{id}/overview`
   - `GET /views/projects/{id}/repository` (composes Phase 01/04/16 repository, revision, materialization and sync reads; `credential_ref` name + `credential_status` only)
   - `GET /views/delivery-cycles/{id}/overview`
   - `GET /views/tasks/{cycle_id}/dag`
   - `GET /views/code/entities/{stable_key}/neighborhood?depth=`
   - `GET /views/ic/{id}/assurance`
   - `GET /views/inbox`
   - `GET /views/projects/{id}/coverage`
   - `GET /views/projects/{id}/agent-activity`
   - `GET /views/delivery-cycles/{id}/control-plane`
2. **Guard preview:** `GET /delivery-cycles/{id}/next-transitions` via `TransitionService.preview` (no writes).
3. **Command catalog:** `GET /commands/catalog` (names, JSON schemas, required roles from the command registry).
4. **Operator session reads:** `GET /actors/me`; SSE `GET /events/stream?after=&project_id=` (existing; clients refetch on events).
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
   - Clients render proposals for human confirmation; confirming sends the typed command as the HUMAN user with an `Idempotency-Key`. The Orchestrator never calls the command API itself.
   - Session history is stored in `orchestrator_sessions` (non-canonical, retention-limited).
6. **Role enforcement:** actors' roles (OPERATOR, APPROVER, VIEWER) from Phase 01 `actors`; command and orchestrator validators enforce permissions server-side.

## 5. Out of Scope

- **Operator UI** (screens, Playwright, generated TS client).
- Full-journey E2E proof through a client (19).
- Multi-tenant org management and SSO (post-MVP).
- Editing source code in a client.

### Do Not Change
- No new write endpoints for clients. All mutations use existing command endpoints.
- No business rules duplicated in client code (eligibility, gate logic, readiness thresholds).

## 6. Domain / Data Model Changes

Migration **`0031_p17_orchestrator`** (linear before Phase 18 **`0032`**):

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
| GET | `/views/...` (§4.1) | read models |
| GET | `/delivery-cycles/{id}/next-transitions` | guard preview |
| GET | `/commands/catalog` | command names, JSON schemas, required roles (generated from the command registry) |
| POST | `/orchestrator/sessions` | create session |
| POST | `/orchestrator/sessions/{id}/turns` | user message → schedules `orchestrator.converse` → returns execution id; result via SSE `orchestrator.turn_completed` |
| GET | `/orchestrator/sessions/{id}` | turns |

## 9. Services / Modules

| Path | Responsibility |
|---|---|
| `apps/control_api/routers/views/*.py` | read models |
| `core/state/preview.py` | guard preview |
| `core/commands/catalog.py` | catalog export |
| `agents/orchestrator/{profile,prompts/converse.md,schemas}.py` | Orchestrator |
| `core/orchestrator/{service,validator}.py` | session + validation + scheduling |
## 10. Development Tasks

- [x] 17.1 Migration **`0031_p17_orchestrator`** + orchestrator session persistence.
- [x] 17.2 Read-model routers (`/views/*`) + integration tests.
- [x] 17.3 `TransitionService.preview` + `GET /delivery-cycles/{id}/next-transitions` + side-effect tests.
- [x] 17.4 `GET /commands/catalog` + unit tests on registry export.
- [x] 17.5 Orchestrator profile, validator, session/turn API, worker wiring, live LLM test (§11).
- [x] 17.6 Execution read extensions used by operator clients (`GET /executions/{id}/model-calls`, worktree mapping as applicable).
- [x] 17.7 §12 Python test suite (unit + integration + live orchestrator).

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
- Python: read-model query correctness on seeded rows; preview has no side effects (row counts and `state_version` unchanged).
- Orchestrator validator: unknown command, bad args, missing role, unknown ref.
- Command catalog export.

### Integration Tests
- Read models return consistent data with the underlying endpoints (`test_views_api.py`).
- Orchestrator session API (`test_orchestrator_api.py`).
- `/commands/catalog` covers every registered command.

### Runtime / Live-LLM Tests
- The §11 live test: `tests/integration/live_llm/test_orchestrator_live.py`.

### Commands
```
make verify-phase-17          # alembic 0031 + §12 Python tests
make verify-phase-17-exit     # + live orchestrator (LLM_LIVE_TESTS=1)
```

## 13. Milestone

A conforming operator client (built outside this phase) can:
- load TECH §25-shaped state from `/views/*` and related reads;
- show guard results from `next-transitions` and available commands from `/commands/catalog`;
- subscribe to `/events/stream` and refetch authoritative reads (events are not state);
- run Orchestrator turns and submit typed commands as a HUMAN after validating proposals.

## 14. Acceptance Criteria

- [x] Read-model endpoints in §4.1 return aggregated authoritative data (integration tests green).
- [x] `GET /delivery-cycles/{id}/next-transitions` is side-effect free and matches guard registry behavior.
- [x] `GET /commands/catalog` lists registered commands with schemas.
- [x] No new mutating routes for operator clients; mutations remain the command bus.
- [x] Orchestrator uses the live `orchestration` alias, persists no canonical delivery state, validates proposals, and never executes commands itself.
- [x] Role checks on orchestrator proposals and commands match `actors` roles (integration + live tests).
- [x] Live orchestrator test in §11 passes when `LLM_LIVE_TESTS=1`.

## 15. Exit Criteria

- §14 green via `make verify-phase-17-exit`.
- `STATUS.md` Phase **17** section updated (backend scope only).

## 16. Dependencies

### Depends On
- 16. All domain APIs including integrations exist.

### Blocks
- 19.

### Can Run In Parallel With
- 18.
  - 17 owns `routers/views`, `core/state/preview.py`, `core/commands/catalog.py` and `agents/orchestrator`.
  - 18 owns telemetry, security hardening and recovery in `core/*` and `apps/*/main.py`.
  - Coordinate on auth middleware and the migration chain (**`0031`** → **`0032`**).

## 17. Risks / Implementation Notes

- **Orchestrator over-reach:** strict validator; humans confirm all commands. Approvals are never auto-executed from agent output.
- **Read-model drift:** contract tests against seeded fixtures; OpenAPI remains the client contract.

## 18. Deliverables

- Code: read-model routers, guard preview, command catalog, `agents/orchestrator/*`, `core/orchestrator/*`.
- Migration: **`0031_p17_orchestrator`**.
- APIs/events: §8 (+ `orchestrator.turn_completed`).
- Config: `orchestration` alias in `config/models.yaml`.
- Tests: §12 Python suite + Orchestrator live.
