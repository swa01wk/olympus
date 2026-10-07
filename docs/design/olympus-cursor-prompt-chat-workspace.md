# Cursor prompt — Olympus Studio (chat + workspace)

Paste everything below the line into Cursor Composer. Run one phase per Composer session: start each session with "Run phase C<n> from docs/design/olympus-cursor-prompt-chat-workspace.md".

---

You are implementing the **Olympus Studio**: a three-pane operator view (control panel · chat · workspace) in the Next.js dashboard at `apps/dashboard`. It drives a delivery cycle stage by stage: PRD intake → features and specs → architecture → implementation specs and task plan → development → assurance → release. A human approves each gate in the workspace.

## Read first, every session

1. `docs/design/olympus-chat-workspace-plan.md` — the spec. Section numbers below (§1–§7) refer to it.
2. `docs/design/olympus-ui-spec/README.md`, `02-navigation.md`, `tokens.json`, `components/ApprovalDialog.md` — visual and interaction rules.
3. The backend files named in the phase you are running, for exact request and response shapes.

## Non-negotiable rules

- **The backend is read-only and is the source of truth.** Do not edit anything under `core/`, `apps/control_api/`, `apps/*_worker/`, `agents/` or `migrations/`. If the backend lacks something, use the workaround in §3. Never invent an endpoint, field or enum value. If a shape is unclear, open the router in `apps/control_api/routers/` and read the Pydantic model.
- **The UI never decides whether a step is allowed.** Advance buttons render `GET /delivery-cycles/{id}/next-transitions` (`allowed`, `authorization_denied`, `guard_results`). Do not re-implement guards.
- **Approvals are never decided in chat.** Chat links to the Decision panel. The backend rejects chat decisions (`APPROVAL_DECISION_REQUIRES_FORM`).
- **Every mutation shows its exact API call before it is sent** (reuse `lib/command-preview.ts`) and sends a fresh `Idempotency-Key` (already done by `src/api/client.ts`).
- Reuse what exists: `src/api/client.ts`, `src/api/query-keys.ts`, `src/api/hooks/*`, `src/api/sse/*`, `components/primitives/*`, `components/dialogs/*`, `src/adapters/status.ts`. Use the design tokens, IBM Plex Sans/Mono, borders not shadows, light and dark themes.
- No new dependencies unless the phase says so. TanStack Query is already installed.
- Keep files focused: a hook per concern, a component per stage view.
- Accessibility: every control keyboard-reachable, visible focus ring, dialogs trap and restore focus, status never conveyed by colour alone.

## How to work each phase

1. Restate the phase goal and list the files you will create or change. Wait for my OK only if you plan to touch a file outside `apps/dashboard` or `docs/`.
2. Implement.
3. Add or update unit tests in `apps/dashboard/tests/unit`.
4. Run `npm run check` in `apps/dashboard` (lint, typecheck, vitest) and fix until green.
5. Append a row for the phase to `STATUS.md` §16 (Frontend UI track): phase id, state, milestone, blockers.
6. Stop and report: what changed, the acceptance checks and their results, anything left over. Do not start the next phase.

---

## C0 — Hygiene

Goal: clean repo; correct base types and streaming before building on them.

1. Delete every committed file whose name ends in ` 2.<ext>` anywhere in the repo (`git ls-files | grep ' 2\.'` — about 35 files, e.g. `apps/control_api/main 2.py`, `uv 2.lock`, `STATUS 2.md`). These are macOS copies; the originals stay. This is the one allowed change outside `apps/dashboard`.
2. `src/api/types/core.ts`: extend `InboxItem` with the nested objects the backend returns from `/views/inbox` (see `core/views/read_models.py` `build_inbox_view`):
   - `approval?: { id; key; approval_type; subject_type; subject_id; subject_hash; status }`
   - `clarification?: { id; key; question; status }`
3. `src/api/hooks/use-olympus-queries.ts`: make `useInbox` accept `{ projectId?, cycleId? }` and pass them as `project_id` / `delivery_cycle_id` query params; include them in the query key.
4. `src/api/sse/cycle-event-stream.ts`: parse `id:` lines; remember the last id; on reconnect send `Last-Event-ID`. Backend: `apps/control_api/sse.py`.
5. `src/api/sse/use-cycle-event-stream.ts`: pass the parsed event (`{ sequence, event_type, payload }`) to an optional `onEvent(event)` subscriber, in addition to the existing `invalidate`.
6. `src/adapters/status.ts`: add `ELIGIBLE` (pass tone) and `NOT_ELIGIBLE` (blocked tone); remove the unused `EXECUTED` and `UNSATISFIED` keys.

Acceptance: `git ls-files | grep ' 2\.'` prints nothing; a unit test feeds the SSE parser a stream with `id:` lines and asserts the next connect sends `Last-Event-ID`; status tests cover ELIGIBLE / NOT_ELIGIBLE.

## C1 — API layer for every stage

Goal: typed client functions and hooks for every call in §5 and §6. No UI.

Add to `src/api/resources.ts` (reads) and `src/api/commands.ts` (writes), with query keys in `query-keys.ts`. Read each router for exact bodies:

- Sources (`routers/sources.py`): `uploadProductSource(projectId, cycleId, {file} | {title, text, lineage_key?, source_type?})` → `POST /projects/{p}/sources?delivery_cycle_id=` (multipart when a file is given; JSON otherwise; returns `result.product_source_id`), `listSources`, `getSourceContent`, `decomposeSource(sourceId, cycleId)` → body `{delivery_cycle_id}`, `deriveSource(sourceId)`.
- Product model (`product_model.py`, `specs.py`, `clarifications.py`): `listCapabilities`, `listFeatures`, `listFeatureSpecs(featureId)`, `createFeatureSpecVersion(featureId, body: FeatureSpecBody)`, `listDecompositions(cycleId)`, `requestScopeApproval(cycleId, featureSpecIds)`, `listClarifications`, `answerClarification`.
- Planning (`planning.py`): `proposeArchitecture(cycleId)`, `getProjectArchitecture`, `requestArchitectureApproval(architectureId, cycleId)`, `generateImplementationSpecs(cycleId)`, `listImplementationSpecs(featureId)`, `requestImplementationSpecApproval(specId, cycleId)`, `generateTaskPlan(cycleId)`, `listTaskPlans(cycleId)`, `acceptTaskPlan(planId)`, `getTaskDag(cycleId)`.
- Approvals (`approvals.py`, `delivery_cycles.py`): `getApproval`, `requestApproval(cycleId, {approval_type, subject_type, subject_id, subject_version, subject_hash})`, `getNextTransitions(cycleId)`.
- Release (`releases.py`): `createRelease(cycleId)`, `getReleaseEligibility(cycleId)`, `getRelease`, `getReleaseManifest`, `approveRelease(releaseId)`, `executeRelease(releaseId)`.
- Orchestrator (`orchestrator.py`): type the full assistant turn: `{ role, text, execution_id?, intent?, proposal?: {command, target_ref, args, rationale} | null, clarification_answer_draft?: {clarification_id, answer} | null }`.
- `src/api/proposal-routes.ts`: implement the §6 map as a pure function `routeForProposal(proposal, ctx: {projectId, cycleId, cycleState}) → {method, path, body} | {notRunnable: reason}`. `approval.decide` always returns `notRunnable`.

Add mutation hooks that invalidate: the cycle (`invalidateCycleQueries`), `next-transitions`, the inbox, and the stage's own lists.

Acceptance: a unit test per function asserts method, path, query and body (mock `fetch`); `routeForProposal` is tested for every row of §6.

## C2 — Studio shell (three panes)

Goal: the layout and the stage spine, with no stage content yet.

- Route: `app/(console)/projects/[projectId]/cycles/[cycleId]/studio/page.tsx`. Link to it from the cycle page and from `NavRail`.
- `components/studio/StudioShell.tsx`: three columns: control panel (~264px), chat (~400px, resizable), workspace (fills the rest). Below 1024px, collapse to tabs: Stages · Chat · Workspace.
- `components/studio/StageSpine.tsx`: the state list for the cycle type from §1 (add a `STAGES_BY_CYCLE_TYPE` constant next to `src/control-plane/stage-lanes.ts`). Per stage show: done (before current), current, waiting-on-human (a pending inbox approval or clarification belongs to it), blocked (current with `next-transitions` all disallowed), future. Word + glyph + token colour.
- Stage selection is UI state (`?stage=` search param). It never sends a command. Default: the cycle's current state. If the user pins another stage and the cycle moves, show "Cycle moved to X — Follow".
- Control panel also shows: project and cycle pickers (reuse TopBar logic), stream status (`StreamStatus`), and inbox count for this cycle.
- Live updates: `useCycleEventStream(cycleId, { invalidate, onEvent })` at the shell level.

Acceptance: switching between cycles of different types changes the spine; selecting a stage changes `?stage=` and the workspace header only; no POST requests fire.

## C3 — Chat

Goal: a working orchestrator conversation that proposes, but never decides.

Backend: `apps/control_api/routers/orchestrator.py`, `core/orchestrator/service.py`, `agents/orchestrator/schemas.py`. The reply is async: `POST …/turns` returns only `{execution_id}`; the assistant turn is appended later and `orchestrator.turn_completed` (payload: `session_id`, `execution_id`, `intent`) is emitted on the cycle stream.

- `src/api/hooks/use-orchestrator-chat.ts`:
  - Session per cycle: reuse the id from `sessionStorage` key `olympus.chat.<cycleId>` until `expires_at`; create a new session on missing, expired or `NOT_FOUND`. Never create a session without a cycle (backend 500s — §3 B-02).
  - `send(message)`: optimistic user bubble + a pending assistant bubble keyed by `execution_id`.
  - Resolve the pending bubble when `onEvent` receives `orchestrator.turn_completed` with that `execution_id` → refetch the session. Fallback: poll `GET /orchestrator/sessions/{id}` every 2 s for up to 90 s; then show "Still working — the execution is <id>" with a link to `/executions/<id>`.
  - Hide `role: "system"` "scheduled" turns from the transcript.
- `components/studio/ChatPanel.tsx`: transcript + composer. The composer has a text area and an "Attach PRD" button (.md, .txt, .pdf) that is enabled only when the cycle is at DISCOVERY or PRODUCT_MODEL. Attaching uploads through C1 `uploadProductSource` and posts a system note in the transcript ("PRD v<n> ingested — open in workspace").
- Render assistant turns by intent (§4.3):
  - EXPLAIN — markdown text; record keys matching `/[A-Z]{2,}-\d+/` become links that set `?stage=` to the owning stage when known.
  - PROPOSE_COMMAND — `ProposalCard`: command, target, args, rationale, the preview from `routeForProposal`, buttons Run / Dismiss. Run requires a click, sends with a fresh idempotency key, shows result or the API error message. `notRunnable` shows the reason and a "Open in workspace" link.
  - ANSWER_CLARIFICATION — `ClarificationDraftCard`: the question (from inbox), an editable answer pre-filled from the draft, Send answer.
  - NAVIGATE — text only (§3 B-01).
  - OUT_OF_SCOPE — muted text.
- Replace the body of `components/shell/AskOlympusDrawer.tsx` with `ChatPanel` so the drawer elsewhere in the app gets the same behaviour.

Acceptance: unit tests for the hook with mocked fetch and a fake event stream (resolve via event; resolve via polling; session reuse; expired session recreated); component tests for each intent; a proposal for `approval.decide` never sends a request.

## C4 — Workspace stage views (Greenfield first)

Goal: each stage magnified, with its records and its actions. Follow §5 row by row.

`components/studio/workspace/StageWorkspace.tsx` picks a view by `(cycleType, stage)`. Every view has the same frame: header (stage name, cycle key, state), Decision panel slot (C5), body, Next step bar slot (C5).

- `DiscoveryStage`: sources list with version and ingest time; selected source content (markdown render); decomposition status from `/delivery-cycles/{c}/decompositions`; actions: Upload PRD (same as composer), Decompose (when a source exists and no decomposition is running).
- `ProductModelStage`: capabilities → features → specs tree (left), selected spec (right) showing behavior, summary, inputs, outputs, rules, constraints, out_of_scope with version and status; Edit spec opens a form for `FeatureSpecBody` that saves a new version; open clarifications for this cycle with Answer; Request scope approval sends all current spec ids (`PROPOSED`/`DRAFT`), disabled while a SCOPE approval is pending.
- `ArchitectureStage`: architecture document view; Propose architecture; Request approval.
- `PlanningStage`: tabs Implementation specs (per feature, status, Request approval per spec) · Task plan (status, tasks, Accept plan) · DAG (reuse `components/graph` / `lib/task-plan-dag.ts`); Generate implementation specs; Generate task plan.
- `DevelopmentStage`, `IntegrationAssuranceStage`, `ReleaseStage`: embed the existing `TaskDagScreen`, `ExecutionsScreen`, `AssuranceScreen`, `OutcomeScreen` content inside the frame rather than rebuilding them. ReleaseStage adds Create release, the eligibility checklist (`EligibilityChecklist`), manifest with hash, and Execute release (enabled only when the release is APPROVED).
- Generation endpoints schedule agent work: after Propose/Generate, show "Running — <execution key>" and refresh on the matching `*.proposed` event (§1 event list).
- Empty, loading, error and permission states use `components/primitives/EmptyState` and `components/truth/ExceptionState`.

Acceptance: with a live control API you can go from an empty Greenfield cycle at DISCOVERY to PLANNING entirely inside the studio; each view has a component test with fixture responses copied from the backend models.

## C5 — Decision panel and Next step bar (human in the loop)

Goal: governed human decisions and a truthful "what's next".

- `components/studio/DecisionPanel.tsx`, shown at the top of a stage view when the inbox has a pending approval for this cycle whose type belongs to the stage (SCOPE → PRODUCT_MODEL, ARCHITECTURE → ARCHITECTURE, IMPLEMENTATION_SPEC → PLANNING, ACTION → DEVELOPMENT, FINDING_WAIVER → ASSURANCE, RELEASE → RELEASE; the other types per §5's last paragraph).
  - Shows: approval type and key; subject type, id, version, hash (`Sha` primitive); which guard it unlocks (match `guard_results` from next-transitions); the subject content inline (spec list, architecture, impl spec, manifest).
  - Buttons: Reject · Request changes · Approve. Note required for Reject and Request changes. Follows `components/dialogs/ApprovalDialog.tsx` behaviour and `docs/design/olympus-ui-spec/components/ApprovalDialog.md`.
  - Release approvals go through `POST /releases/{id}/approve` (it binds the decision to the manifest hash); all others through `POST /approvals/{id}/decision`.
  - Errors: 403 → "You need the APPROVER role to decide this"; hash or version conflict → "This changed after approval was requested. Request approval again." with the request action.
  - Read-only for actors without `APPROVER` (`useActorMe`).
  - History under the panel: `GET /audit?target_type=approval&target_id=<id>` (§3 B-05).
- `components/studio/NextStepBar.tsx`, at the bottom of the current stage: each transition from next-transitions with its guards (✓/✕ + reasons). Primary button for the forward command, enabled only when `allowed && !authorization_denied`; sends `expected_state` = current state. Secondary commands (revise_*, return_to_development, cancel) in a menu; cancel asks for confirmation.
- After any decision or transition: invalidate inbox, next-transitions, cycle, stage lists; the spine updates from the SSE event too.

Acceptance: an OPERATOR without APPROVER sees the panel read-only with the role message; after APPROVED, the forward button enables without reload; REJECTED and CHANGES_REQUESTED keep it disabled and show the note.

## C6 — Other journeys

Goal: the same studio for FEATURE_CHANGE, BUG_FIX, BROWNFIELD_ONBOARDING and REMEDIATION.

Add stage views per §5's last paragraph, reading the routers `changes.py`, `spec_deltas.py`, `impact.py`, `defects.py`, `brownfield.py`, `promotion.py`, `readiness.py`, `baselines.py`. Reuse the existing `ImpactScreen`, `TraceabilityScreen`, `CodeIntelligenceScreen` content where it fits. Map SPEC_DELTA, EXPECTED_BEHAVIOR, REPAIR_SPEC, UNREPRODUCED_REPAIR, PROMOTION and READINESS approvals to their stages in the Decision panel.

Acceptance: each cycle type's spine renders with no "unknown stage" fallback; each new stage view has a component test.

## C7 — End-to-end

Goal: prove the studio against the real backend.

Playwright spec `tests/e2e/studio-greenfield.spec.ts` against a running control API (`NEXT_PUBLIC_OLYMPUS_API_URL`) with two tokens (operator; operator+approver). Steps: create project and Greenfield cycle → upload `tests/fixtures/supportdesk/PRD.md` (repo root) from the composer → decompose → see features → edit one spec (new version) → request scope approval → as approver Request changes with a note → request again → Approve → Next step bar enables `start_architecture`. Then send a chat message and assert an assistant turn appears. Tag `@live`; skip when the API is unreachable.

Acceptance: the spec passes locally against `make db-up && make migrate && uvicorn apps.control_api.main:app` with workers running.
