# Olympus — Chat + Workspace, aligned to the backend

Status: plan for Cursor. Repo state reviewed: `main` @ `0979a53` (2026-10-07).
Rule for every phase below: **the backend is read-only and is the source of truth.** If the UI needs something the backend does not provide, record it in §3 and use the stated workaround. Do not edit `core/`, `apps/control_api/`, `agents/` or `migrations/`.

---

## 1. Backend review — what the UI must respect

**Shape.** FastAPI control API (`apps/control_api`), 49 routers, **205 operations**, 33 Alembic migrations, scheduler + execution workers. Phases 00–18 complete, Phase 19 in progress (`STATUS.md`).

**Auth and headers.** `Authorization: Bearer <token>` on every call. Mutations take `Idempotency-Key`. Roles that matter to the UI: `OPERATOR` (drive the cycle) and `APPROVER` (decide approvals). Approval decisions are HUMAN-only.

**Delivery-cycle state machines** (`core/state/machines.py`). Every cycle also has `cancel` (human) and `fail` (system).

| Cycle type | States, in order |
|---|---|
| GREENFIELD_BUILD | DISCOVERY → PRODUCT_MODEL → ARCHITECTURE → PLANNING → DEVELOPMENT → INTEGRATION → ASSURANCE → RELEASE → COMPLETE |
| BROWNFIELD_ONBOARDING | RECON → CODE_INDEX → RECOVERED_SPEC → BASELINE → READINESS ⇄ REMEDIATION → READY |
| FEATURE_CHANGE | INTAKE → SPEC_DELTA → IMPACT_ANALYSIS → PLANNING → DEVELOPMENT → INTEGRATION → ASSURANCE → RELEASE → COMPLETE |
| BUG_FIX | TRIAGE → REPRODUCTION → EXPECTED_BEHAVIOR → ROOT_CAUSE → DEVELOPMENT → INTEGRATION → REGRESSION → ASSURANCE → RELEASE → COMPLETE |
| REMEDIATION | INTAKE → PLANNING → DEVELOPMENT → INTEGRATION → ASSURANCE → RELEASE → COMPLETE |

Transitions: `POST /delivery-cycles/{id}/commands/{command}` with `{expected_state, payload?}`. What is possible right now, and why not: `GET /delivery-cycles/{id}/next-transitions` → `[{command, to_state, allowed, guard_preview[], guard_results[{guard_id, ok, reasons[]}], authorization_denied}]`. **The UI never decides whether a step is allowed; it renders this.**

**Approvals (the human-in-the-loop record).** Types the backend actually raises today: SCOPE, ARCHITECTURE, ARCHITECTURE_DELTA, IMPLEMENTATION_SPEC, SPEC_DELTA, UNREPRODUCED_REPAIR, **EXPECTED_BEHAVIOR**, **TASK_PLAN**, PROMOTION, FINDING_WAIVER, ACTION, RELEASE. **Never created by the backend:** REPAIR_SPEC, READINESS, SPEC_DECISION, DEPLOYMENT. Repair and remediation specs use **IMPLEMENTATION_SPEC**. Statuses: PENDING → APPROVED | REJECTED | CHANGES_REQUESTED (human) or EXPIRED | CANCELLED (system). Each approval is bound to `subject_type / subject_id / subject_version / subject_hash`; if the subject changes, the approval no longer counts. Decide with `POST /approvals/{id}/decision {decision, note}`.

**Chat backend = Orchestrator** (`/orchestrator/sessions`).
- `POST /orchestrator/sessions {project_id, delivery_cycle_id}` → session (8 h TTL). A cycle is required before any turn.
- `POST /orchestrator/sessions/{id}/turns {message}` → `{execution_id}` only. The reply is produced asynchronously by an agent execution.
- When it finishes, the backend appends an `assistant` turn and emits **`orchestrator.turn_completed`** on the cycle event stream. Assistant turn fields: `text`, `intent` (EXPLAIN | ANSWER_CLARIFICATION | PROPOSE_COMMAND | NAVIGATE | OUT_OF_SCOPE), `proposal {command, target_ref, args, rationale}`, `clarification_answer_draft {clarification_id, answer}`.
- **The orchestrator is not allowed to decide approvals** (`APPROVAL_DECISION_REQUIRES_FORM`). This matches the design spec rule "approvals are never placed behind a chat transcript". The decision lives in the workspace, never in the transcript.

**Events.** `GET /delivery-cycles/{id}/events/stream` (SSE, `id: <sequence>`, `event: <type>`, resumes from `Last-Event-ID`); `GET /events/stream?project_id=&after=`; paged history `GET /delivery-cycles/{id}/events?after_sequence=`. Event types the chat/workspace react to: `orchestrator.turn_completed`, `delivery_cycle.transitioned`, `approval.requested`, `approval.decided`, `scope.approval_requested`, `scope.approved`, `scope.rejected`, `product_source.ingested`, `product_decomposition.proposed`, `feature_spec.proposed`, `architecture.proposed`, `architecture.approved`, `implementation_spec.proposed`, `implementation_spec.approved`, `task_plan.proposed`, `task_plan.accepted`, `task.created`, `task.transitioned`, `execution.*`, `integration.*`, `gate.finalized`, `finding.*`, `release.*`.

**Read models for the workspace.** `/views/delivery-cycles/{id}/overview`, `/views/delivery-cycles/{id}/control-plane`, `/views/inbox?project_id|delivery_cycle_id` (pending approvals + open clarifications, with nested `approval{…}` / `clarification{…}`), `/views/tasks/{cycle_id}/dag`, `/views/ic/{ic_id}/assurance`, `/views/projects/{id}/overview`.

---

## 2. Frontend audit (`apps/dashboard`) against the backend

**Aligned — keep as is.**
- All **50 distinct API calls** in `src/api` and components resolve to real backend routes with the right method.
- `DeliveryCycle`, `Project`, `Task`, `Execution`, orchestrator session types in `src/api/types/core.ts` match the backend response models field-for-field.
- Stage names in `src/control-plane/stage-lanes.ts`, `lanes.ts`, `lib/journey-labels.ts` are all real machine states.
- `ApprovalDialog` shows subject type, version and hash and sends `{decision, note}` with an idempotency key — correct.

**Mismatches to fix.**

| ID | Where | Problem | Fix |
|---|---|---|---|
| F-01 | `components/shell/AskOlympusDrawer.tsx` | After posting a turn it immediately re-reads the session. The reply is async, so the user only ever sees `system: scheduled`. | Show a pending assistant bubble keyed by `execution_id`; on `orchestrator.turn_completed` for that `execution_id`, refetch the session. Fallback: poll `GET /orchestrator/sessions/{id}` every 2 s for 60 s. |
| F-02 | same | Ignores `intent`, `proposal`, `clarification_answer_draft`. Renders `JSON.stringify` for odd turns. | Render per intent (see §4.3). |
| F-03 | same | Creates a new session on every open, so history is lost. | Keep `sessionId` per `cycleId` (in memory + `sessionStorage`); reuse until `expires_at`; recreate on `NOT_FOUND`. |
| F-04 | whole app | The endpoints that **produce** what humans approve are never called: source upload, decompose, scope approval request, architecture propose + approval request, implementation-spec generate + approval request, task-plan generate + accept, release create / approve / execute. | Add them to `src/api/resources.ts` / `commands.ts` and drive them from the workspace (§5). |
| F-05 | `src/api/types/core.ts` `InboxItem` | Drops the nested `approval{id,key,approval_type,subject_type,subject_id,subject_hash,status}` and `clarification{id,key,question,status}` the backend returns. | Extend the type; the decision panel needs these. |
| F-06 | `src/api/sse/cycle-event-stream.ts` | Parses `event:` and `data:` but not `id:`, and never sends `Last-Event-ID`, so a reconnect misses or replays events. | Track the last `id:`; send `Last-Event-ID` on reconnect. |
| F-07 | `components/dialogs/IntakeFormDialog.tsx` | Creates the cycle only; the PRD never reaches the backend. | Intake moves into the chat composer (§5, stage 1). |
| F-08 | `src/adapters/status.ts` | `ELIGIBLE` and `NOT_ELIGIBLE` (release) fall back to neutral; `EXECUTED` and `UNSATISFIED` map statuses the backend never emits. | Map ELIGIBLE → pass-tone, NOT_ELIGIBLE → blocked; remove the dead keys. |
| F-09 | repo root | **35 macOS duplicate files** are committed (`main 2.py`, `STATUS 2.md`, `uv 2.lock`, `ci 2.yml`, …). Some are stale (e.g. `apps/control_api/main 2.py` is 176 lines vs 195). | Delete every `* 2.*` file in one commit. |

---

## 3. Backend gaps (record; fixed items noted)

| ID | Gap | UI workaround |
|---|---|---|
| B-01 | **Fixed (RL2.6).** `complete_turn` now persists `navigate_to` and `refs`; Studio applies them via `useStudioFocus`. | — |
| B-02 | Posting a turn to a session with no `delivery_cycle_id` raises an unhandled `ValueError` (500). | Never open chat without a cycle; the composer's first action in an empty project is "create cycle". |
| B-03 | **Fixed (RL2.9).** Six generation commands (`architecture.propose`, `implementation_specs.generate`, `task_plan.generate`, `change_interpretation.rerun`, `architecture_delta.propose`, `release.create`) are on the bus with proposal → REST mapping. | Proposal cards run the mapped route after confirm. |
| B-04 | There is no generic `POST /commands`; only `GET /commands/catalog`. | Map each proposable command to its REST route (§6). Unmapped proposals render as "Not runnable from chat". |
| B-05 | **Partly fixed (RL1 review).** `ApprovalResponse` now returns `decision_note`, `decided_by_actor_id`, `decided_at`, `created_at`. `GET /approvals` still has no project/cycle filter. The audit log does not carry decision notes. | Pending: use `/views/inbox?delivery_cycle_id=`. History: `GET /approvals` filtered client-side by `delivery_cycle_id`. |
| B-06 | No endpoint lists orchestrator sessions for a cycle. | Client keeps the session id (F-03). |

**Note on the backend's own journey tests.** `tests/journey/*` and the Phase 19 chained run (`tests/journey/chained/runner.py`) drive several steps through Python services and seeded rows rather than HTTP: brownfield cycle creation and promotion, some approvals, architecture and implementation-spec seeding in the deterministic lane. So a passing backend journey does not prove every human step is reachable over HTTP. C7b closes that gap by doing every step through the studio; any step that turns out to have no route is recorded here as a new B-gap.
The backend also has no fake model provider for a running stack (`MODEL_PROVIDER` is `anthropic` or `openai`; `FakeProvider` is in-process and test-only), so C7b needs a live LLM key, like the backend's Phase 19 run.

---

## 4. The concept

### 4.1 Layout

```
┌──────────────┬──────────────────────────┬──────────────────────────────────────┐
│ CONTROL      │ CHAT                     │ WORKSPACE  (magnified stage)         │
│ PANEL        │                          │                                      │
│ Project ▾    │  assistant / user turns  │ ┌ Decision required ──────────────┐ │
│ Cycle ▾      │  proposal cards          │ │ SCOPE APR-007 · v2 · 3fa1c9e…   │ │
│              │  clarification drafts    │ │ Reject · Request changes · Appr.│ │
│ ● DISCOVERY  │                          │ └─────────────────────────────────┘ │
│ ● PRODUCT_…  │                          │  Stage content: PRD / features /    │
│ ◐ ARCHITECT… │                          │  architecture / task DAG / IC /     │
│ ○ PLANNING   │                          │  release manifest                   │
│ ○ …          │ ┌──────────────────────┐ │                                      │
│ Inbox (3)    │ │ composer · attach PRD│ │  Next: start_planning  ✕ 1 guard   │
│              │ └──────────────────────┘ │  architecture_approved — pending    │
└──────────────┴──────────────────────────┴──────────────────────────────────────┘
```

- **Control panel (left).** Project and cycle picker; a vertical **stage spine** built from the cycle type's state list (§1). Each stage shows done / current / waiting-on-human / blocked. Inbox count from `/views/inbox`. Clicking a stage magnifies it in the workspace; it does not change state.
- **Chat (centre).** One orchestrator session per cycle. The composer accepts text and a PRD file.
- **Workspace (right).** The selected stage, magnified. Top: **Decision panel** when that stage has a pending approval. Middle: the stage's records. Bottom: **Next step bar** rendered from `next-transitions` with each guard's result.

### 4.2 Interaction rules

1. Chat proposes; the workspace shows; a human decides in the workspace. Nothing mutates from the transcript without an explicit confirm.
2. Approvals are never decided in chat. A chat turn may link to the decision panel ("Review SCOPE APR-007 →").
3. Every mutation shows its exact API call before sending (reuse `lib/command-preview.ts`).
4. After any mutation or relevant event: refetch `next-transitions`, the stage's records and the inbox.
5. The workspace follows the cycle's current state by default. If the user pins another stage, show "Cycle moved to X → follow".

### 4.3 Rendering assistant turns by intent

| intent | Render |
|---|---|
| EXPLAIN | Text. Record keys (`TASK-104`, `APR-007`) become links that magnify the owning stage. |
| PROPOSE_COMMAND | Text + **proposal card**: command, target, args, rationale, the mapped API call (§6), and *Run* / *Dismiss*. *Run* calls the mapped route with a new idempotency key. `delivery_cycle.transition` sends `expected_state` = current state. |
| ANSWER_CLARIFICATION | Text + **draft answer card** for the clarification: editable answer, *Send answer* → `POST /clarifications/{id}/answer {answer}`. |
| NAVIGATE | Text + workspace focus from persisted `navigate_to` / `refs` (RL2.6). |
| OUT_OF_SCOPE | Muted text. |

---

## 5. Stage map — Greenfield (the PRD → features → plan → tasks journey)

| Stage | Workspace shows (GET) | Actions (POST) | Human gate | Advance |
|---|---|---|---|---|
| **DISCOVERY** — PRD to Olympus | Sources: `/projects/{p}/sources`, content `/projects/{p}/sources/{s}/content`; decomposition progress `/delivery-cycles/{c}/decompositions` | Upload PRD from the composer: `POST /projects/{p}/sources?delivery_cycle_id={c}` (multipart `file`, or JSON `{title, text, source_type:"PRD"}`) → `result.product_source_id`; then `POST /sources/{s}/decompose {delivery_cycle_id}` | — (guard `product_source_ingested`) | `start_product_modeling` from DISCOVERY |
| **PRODUCT_MODEL** — features and specs; user discusses changes | Capabilities `/projects/{p}/capabilities`; features `/projects/{p}/features`; specs `/features/{f}/specs`; open clarifications (inbox) | Edit a spec: `POST /features/{f}/specs {body: FeatureSpecBody}` (new version). PRD changes: upload again with the same `lineage_key` (the backend stores it as the next version), then `POST /sources/{s}/derive` to re-run decomposition. Answer clarifications. Request sign-off: `POST /delivery-cycles/{c}/scope/approval-request {feature_spec_ids}` | **SCOPE** approval | `start_architecture` (guard `scope_approved`) |
| **ARCHITECTURE** | `/projects/{p}/architecture`, `/architectures/{a}` | `POST /delivery-cycles/{c}/architecture/propose`; `POST /architectures/{a}/approval-request {delivery_cycle_id}` | **ARCHITECTURE** approval | `start_planning` (guards `architecture_approved`, `repository_ready_with_canonical_commit`) |
| **PLANNING** — feature planning and tasks | Implementation specs `/features/{f}/implementation-specs`; task plans `/delivery-cycles/{c}/task-plans`, `/task-plans/{id}`; DAG `/views/tasks/{c}/dag` | `POST /delivery-cycles/{c}/implementation-specs/generate`; per spec `POST /implementation-specs/{id}/approval-request {delivery_cycle_id}`; `POST /delivery-cycles/{c}/task-plan/generate`; `POST /task-plans/{id}/commands/accept` | **IMPLEMENTATION_SPEC** approvals; the guard requires an accepted plan, but accepting has no role check and raises no approval until RL3 (G6) | `start_development` (guards `implementation_specs_approved`, `task_plan_accepted_contracts_issued`) |
| **DEVELOPMENT** | Tasks `/delivery-cycles/{c}/tasks`, executions, governed actions | Task commands `POST /tasks/{t}/commands/{cmd}`; cancel execution | **ACTION** approvals (governed tool actions) | `start_integration` (guard `all_code_tasks_completed`) |
| **INTEGRATION → ASSURANCE** | IC `/delivery-cycles/{c}/integration-candidates`, `/views/ic/{ic}/assurance`, gates, findings, evidence | `POST /findings/{f}/waive`, `/remediate` | **FINDING_WAIVER** approvals | `start_assurance`, then `start_release` (guard `required_gates_pass`); `return_to_development` when remediation exists |
| **RELEASE** | `/delivery-cycles/{c}/release-eligibility`, `/releases/{r}`, `/releases/{r}/manifest` | `POST /delivery-cycles/{c}/release`; `POST /releases/{r}/approve` (bound to the manifest hash); `POST /releases/{r}/execute` | **RELEASE** approval | `complete` (guard `release_executed`) |

Other cycle types reuse the same three panes; only the spine and stage contents change. Map approval types to stages the way the Studio does (`apps/dashboard/lib/studio-spine.ts`):

- **FEATURE_CHANGE:** SPEC_DELTA at SPEC_DELTA; ARCHITECTURE_DELTA at IMPACT_ANALYSIS; IMPLEMENTATION_SPEC at PLANNING; shared gates (FINDING_WAIVER, ACTION, RELEASE) as in the greenfield table.
- **BUG_FIX:** UNREPRODUCED_REPAIR at REPRODUCTION; **EXPECTED_BEHAVIOR** at EXPECTED_BEHAVIOR when Kira’s resolution needs human confirmation; **TASK_PLAN** at ROOT_CAUSE after a repair task plan is proposed; repair specs use **IMPLEMENTATION_SPEC** at ROOT_CAUSE (not REPAIR_SPEC).
- **BROWNFIELD_ONBOARDING:** ARCHITECTURE (recovered model) and **PROMOTION** at BASELINE; **IMPLEMENTATION_SPEC** at REMEDIATION; `declare_ready` does not request a READINESS approval. The backend requests and approves the ARCHITECTURE, PROMOTION and remediation IMPLEMENTATION_SPEC approvals inside the promotion decision or remediation call, so they are never pending; the human decision happens in the review queue.
- **REMEDIATION:** IMPLEMENTATION_SPEC at PLANNING.

Stage reads: Feature Change — `/features/{f}/spec-deltas`, `/delivery-cycles/{c}/impact-assessments`; Bug Fix — `/defects/…`; Brownfield — `/discovery`, `/recovery`, `/review-queue`, `/promotion-decisions`, `/readiness`.

### 5.1 Decision panel (human in the loop)

Source: inbox item for the stage (`/views/inbox?delivery_cycle_id=`) + `GET /approvals/{id}` + the subject record.
Shows: approval type and key; subject type, id, **version and hash**; what the decision unlocks (the guard from `next-transitions` that reads it); the subject's content (spec list, architecture, impl spec, manifest).
Actions: *Reject* · *Request changes* · *Approve*. A note is required for Reject and Request changes. Send `POST /approvals/{id}/decision {decision, note}` with an idempotency key.
After the decision: refetch inbox and `next-transitions`. If the advance command is now `allowed`, enable the Next step bar's primary button.
Errors: 403 → "You need the APPROVER role"; stale subject hash → "This changed after the request — request approval again".

---

## 6. Chat proposal → REST route map

| Catalog command | Route |
|---|---|
| `delivery_cycle.transition` | `POST /delivery-cycles/{cycle_id}/commands/{args.command_name}` `{expected_state, payload}` |
| `create_delivery_cycle` | `POST /projects/{project_id}/delivery-cycles {type, objective, repository_id?}` |
| `ingest_product_source` | `POST /projects/{project_id}/sources?delivery_cycle_id=` (JSON body) |
| `decompose_source` | `POST /sources/{source_id}/decompose {delivery_cycle_id}` |
| `request_scope_approval` | `POST /delivery-cycles/{cycle_id}/scope/approval-request {feature_spec_ids}` |
| `approval.request` | `POST /delivery-cycles/{cycle_id}/approvals {approval_type, subject_type, subject_id, subject_version, subject_hash}` |
| `task.command` | `POST /tasks/{task_id}/commands/{command_name} {expected_state}` |
| `create_task` | `POST /delivery-cycles/{cycle_id}/tasks` |
| `intake_change_request` | `POST /projects/{project_id}/change-requests` |
| `intake_defect` | `POST /projects/{project_id}/defects` |
| `approval.decide` | **Never from chat** — open the Decision panel |
| anything else | "Not runnable from chat" + link to the stage |

---

## 7. Phases for Cursor

Run in order. Each phase ends with `npm run check` green and the listed acceptance checks.

**C0 — Hygiene.** Delete all `* 2.*` files (F-09). Fix F-08. Extend `InboxItem` (F-05). SSE `Last-Event-ID` resume (F-06).
*Accept:* `git ls-files | grep ' 2\.'` is empty; a dropped SSE connection resumes without duplicate events.

**C1 — API layer.** Add typed functions for every POST in §5 and the route map in §6 to `src/api/resources.ts` / `commands.ts`, with query keys and `invalidate-cycle` rules. No UI yet.
*Accept:* unit tests assert method, path and body for each function against §5.

**C2 — Shell: three panes.** New route `app/(console)/projects/[projectId]/cycles/[cycleId]/studio` with control panel, chat and workspace. The stage spine comes from the cycle type; status per stage from cycle `state` + inbox + `next-transitions`. Collapses to tabs below 1024 px.
*Accept:* switching cycle type changes the spine; clicking a stage magnifies it without a state change.

**C3 — Chat.** Replace `AskOlympusDrawer` logic with a `useOrchestratorChat(cycleId)` hook: session reuse (F-03), async reply via `orchestrator.turn_completed` with polling fallback (F-01), intent rendering and proposal cards (F-02, §4.3, §6).
*Accept:* sending a message shows a pending bubble that resolves to the assistant turn; a PROPOSE_COMMAND card runs the mapped route and the spine updates.

**C4 — Workspace stages.** Implement each Greenfield stage view from §5, top to bottom: DISCOVERY (PRD upload from the composer, decompose), PRODUCT_MODEL (features, specs, spec edit, clarifications, scope request), ARCHITECTURE, PLANNING (impl specs, task plan DAG, accept), then DEVELOPMENT → RELEASE using the existing screens as embedded views.
*Accept:* the full Greenfield path can be driven from the studio without leaving it.

**C5 — Decision panel and Next step bar.** §5.1. Every guard from `next-transitions` shows with its reasons; the advance button is enabled only when `allowed` and not `authorization_denied`.
*Accept:* an OPERATOR without APPROVER sees the decision panel read-only with the role message; after an APPROVED decision the advance button enables without a page reload.

**C6 — Other journeys.** Feature Change, Bug Fix and Brownfield spines and stage views per §5's last paragraph.

**C7 — End-to-end proof.** A green C7 means frontend and backend are integrated.
- *C7a, contract gate (every PR):* the backend's OpenAPI spec is exported into the dashboard; a test fails if any client call, request body or shared enum drifts from it.
- *C7b, live four-journey run (sign-off):* the backend's Phase 19 acceptance run, driven entirely through the studio on one project: Greenfield → R1, Brownfield → READY_FOR_CHANGE, Feature Change → R2, Bug Fix → R3. Every operator and human action goes through the UI, a separate approver decides every gate (including one *Request changes* and one *Reject*), and chat is exercised in each journey. It ends by running the backend's own `scripts/acceptance/evaluate_mvp.py` on the project; every check must pass.
*Accept:* `npm run test:e2e:studio` and the evaluator both pass on a clean database with live workers and a live LLM key. Full detail: C7 in `olympus-cursor-prompt-chat-workspace.md`.
