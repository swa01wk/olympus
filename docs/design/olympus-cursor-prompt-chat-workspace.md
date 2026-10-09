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
- Intake (`projects.py`, `delivery_cycles.py`, `changes.py`, `defects.py`): `createProject({key, name, description?})`, `createDeliveryCycle` (exists), `createChangeRequest(projectId, {title, description, external_ref?})` and `createDefect(projectId, {title, description, external_ref?})` — both return the cycle id they open.
- Feature Change (`changes.py`, `spec_deltas.py`, `impact.py`): `getChangeInterpretation`, `rerunChangeInterpretation`, `getCycleSpecDelta`, `createSpecDelta(featureId, {from_spec_id?, to_spec_id, delivery_cycle_id})`, `requestSpecDeltaApproval(deltaId)`, `createImpactAssessment(cycleId, {spec_delta_id?, seed_stable_keys?, index_version_id?})`, `getLatestImpactAssessment`, `getStaleness`, `proposeArchitectureDelta(cycleId)`, `declineArchitectureDelta(cycleId, {note})`.
- Bug Fix (`defects.py`): `getDefect`, `listReproductions`, `getDefectTrace`, `getRootCause`, `proceedUnreproduced(defectId, {reason})`, `rejectDefect(defectId, {reason?})`.
- Brownfield (`brownfield.py`, `promotion.py`, `readiness.py`, `baselines.py`): `getDiscovery`, `getRecovery`, `listObservedBehaviors`, `getReviewQueue`, `recordPromotionDecision(cycleId, {subject_type, subject_id, decision, note?})`, `getReadiness`, `listBaselines`, `activateBaseline`.
- Assurance (`assurance.py`, `findings.py`): `listGates(icId)`, `finalizeGate`, `runWarden(icId)`, `runSentinel(icId)`, `listFindings(cycleId)`, `waiveFinding`, `remediateFinding`, `listEvidence(cycleId)`.
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
  - History under the panel: the approval's `decision_note`, `decided_by_actor_id` and `decided_at` from `GET /approvals` (§3 B-05).
- `components/studio/NextStepBar.tsx`, at the bottom of the current stage: each transition from next-transitions with its guards (✓/✕ + reasons). Primary button for the forward command, enabled only when `allowed && !authorization_denied`; sends `expected_state` = current state. Secondary commands (revise_*, return_to_development, cancel) in a menu; cancel asks for confirmation.
- After any decision or transition: invalidate inbox, next-transitions, cycle, stage lists; the spine updates from the SSE event too.

Acceptance: an OPERATOR without APPROVER sees the panel read-only with the role message; after APPROVED, the forward button enables without reload; REJECTED and CHANGES_REQUESTED keep it disabled and show the note.

## C6 — Other journeys

Goal: the same studio for FEATURE_CHANGE, BUG_FIX, BROWNFIELD_ONBOARDING and REMEDIATION.

Add stage views per §5's last paragraph, reading the routers `changes.py`, `spec_deltas.py`, `impact.py`, `defects.py`, `brownfield.py`, `promotion.py`, `readiness.py`, `baselines.py`. Reuse the existing `ImpactScreen`, `TraceabilityScreen`, `CodeIntelligenceScreen` content where it fits. Map SPEC_DELTA, EXPECTED_BEHAVIOR, REPAIR_SPEC, UNREPRODUCED_REPAIR, PROMOTION and READINESS approvals to their stages in the Decision panel.

C7b drives all of these through the UI, so each must exist as a visible action:
- **Studio intake** (control panel "New"): New project · Greenfield cycle · Brownfield onboarding (pick repository) · Change request (title + description, or attach a `.md`) · Defect (same). After intake, navigate to the new cycle's studio.
- **Feature Change:** view the interpretation (Re-run), the spec delta (Request approval), the impact assessment, and the architecture delta (Propose / Decline with note).
- **Bug Fix:** view triage, reproductions, trace and root cause; *Proceed unreproduced* (reason required) and *Reject defect*.
- **Brownfield:** view discovery, recovery and observed behaviors; work the review queue with a promotion decision per item; view readiness with each failing check.
- **Assurance (all journeys):** gates with status; *Run Warden* / *Run Sentinel* when not already scheduled; *Finalize gate* when the backend reports it pending; findings with *Waive* (creates a FINDING_WAIVER approval) and *Remediate*.

Acceptance: each cycle type's spine renders with no "unknown stage" fallback; each new stage view has a component test.

## C7 — End-to-end: the studio proves the four-journey MVP

Goal: a green C7 means the frontend and backend are integrated. It has two parts. C7a runs on every PR and catches contract drift. C7b drives the backend's own Phase 19 acceptance run (all four journeys on one project) entirely through the studio, then checks it with the backend's own acceptance evaluator.

Reference implementation to mirror: `tests/journey/chained/runner.py` (journey order and inputs), `tests/journey/chained/assertions.py` (terminal state), `scripts/acceptance/evaluate_mvp.py` (acceptance checks), and the inputs in `tests/fixtures/supportdesk/`. Read them before writing C7b.

Important difference: the backend's own journey tests take service-layer shortcuts for some steps (they call Python services and seed rows directly). C7b may not. **Every operator and human action goes through the studio UI, which goes through HTTP.** If a step has no HTTP route, that is a finding, not something to work around (rule 5 below).

### C7a — Contract gate (deterministic; runs on every PR)

1. `apps/dashboard/scripts/export-openapi.sh`: from the repo root, run
   `OLYMPUS_ENV=test DATABASE_URL=postgresql+psycopg://x:x@localhost/x uv run python -c "import json; from apps.control_api.main import create_app; print(json.dumps(create_app().openapi(), indent=1, sort_keys=True))" > apps/dashboard/tests/contract/openapi.json`
   Commit `openapi.json`. No database is needed; `create_app()` only connects inside its lifespan.
2. `src/api/contract-manifest.ts`: one entry per client function from C1 — `{ fn, method, pathTemplate, sampleBody?, sampleQuery? }`. Path templates use the backend's parameter names (`/delivery-cycles/{cycle_id}/…`).
3. `tests/contract/api-contract.test.ts` (vitest), failing when:
   - a manifest `method + pathTemplate` is not in `openapi.json`;
   - a manifest entry is missing for any function exported from `src/api/resources.ts` or `src/api/commands.ts`;
   - `sampleBody` has a key the request schema does not define, or lacks a key the schema marks `required` (for routes whose OpenAPI request schema is a model; routes that read raw JSON show no schema and are listed in an explicit allow-list with a comment pointing to the router line);
   - the TS unions for `DeliveryCycleType`, `ApprovalType` and `ApprovalStatus` differ from the enums in `openapi.json`.
4. Add `npm run test:contract` and include it in `npm run check`. When the backend changes, re-export `openapi.json` in the same PR.

Acceptance: deliberately renaming one path in the manifest fails the test with the path in the message; restoring it passes.

### C7b — Live four-journey run through the studio (sign-off lane)

**Stack** (document it in `apps/dashboard/tests/e2e/README.md`):
- `make mvp-env` (runs `scripts/demo/bootstrap.sh`), or by hand: `make db-up && make migrate`; `uvicorn apps.control_api.main:app`; `python -m apps.scheduler_worker.main`; `python -m apps.execution_worker.main`.
- `OLYMPUS_ENV=journey`, a live LLM key (`ANTHROPIC_API_KEY` or `OPENAI_API_KEY`) and `LLM_TEST_BUDGET_USD`. The backend has no fake provider for a running stack; agent stages need a real model.
- Tokens: `uv run python -m apps.control_api.cli.seed_actor --name ui-operator --roles OPERATOR` → `OLYMPUS_OPERATOR_TOKEN`; `… --name ui-approver --roles OPERATOR,APPROVER` → `OLYMPUS_APPROVER_TOKEN`.
- Dashboard: `NEXT_PUBLIC_OLYMPUS_API_URL` → the control API. Playwright `baseURL` → the dashboard.

**Rules**
1. Playwright performs every operator and human action by using the studio: clicks, typing, file attach, Decision panel, Next step bar, proposal cards. No `request.post` for mutations.
2. Direct API calls from the spec are allowed only for reads: to assert, and to wait for agent work (`/next-transitions`, `/views/delivery-cycles/{id}/overview`, stage lists).
3. No database access and no backend Python helpers. The spec never imports from `tests/` or calls `seed_*`.
4. Two browser contexts, set via `localStorage["olympus_api_token"]`. The **operator** context drives the cycle. The **approver** context decides every approval. Each time an approval appears, first assert the operator context shows the Decision panel read-only with the APPROVER message.
5. If a step cannot be done in the studio because the backend has no HTTP route for it, fail with `BACKEND_GAP: <step>`. Add the gap to §3 of `olympus-chat-workspace-plan.md` and to `STATUS.md` §16, and stop. Do not seed, patch or skip.
6. Waiting on agent work: wait on UI state (spine status, workspace records), not sleeps. Per-stage timeout from `STUDIO_E2E_STAGE_TIMEOUT_MS` (default 15 min). On timeout, attach to the report: the last `next-transitions` (every guard with its reasons), the last 50 cycle events, and a screenshot.
7. Inputs come from the backend fixtures: PRD `tests/fixtures/supportdesk/PRD.md`; clarification answers by keyword from `tests/fixtures/supportdesk/clarification_answers.yaml`; approval notes from `tests/fixtures/supportdesk/chained/approvals.yaml`; brownfield promotion choices from `tests/fixtures/supportdesk/brownfield_review.yaml`; change request `tests/fixtures/supportdesk/change_priority.md`; defect `tests/fixtures/supportdesk/defect_closed_update.md`.
8. Resumable: one Playwright file per journey, run serially, sharing `var/olympus/ui-e2e/<RUN_ID>.json` (`project_id`, cycle ids, tokens' actor names). `STUDIO_E2E_RUN_ID=<id>` resumes from the first incomplete journey.
9. Chat is checked at least once per journey: send a question about the current blocker. Assert an assistant turn arrives (event or polling) and that the transcript shows no `system: scheduled` rows. If the turn is `PROPOSE_COMMAND`, assert the card's preview equals `routeForProposal` for that proposal. Do not assert a specific intent or wording; the model's output varies.

**Journeys** (one project; key `SUPPORTDESK-UI-<RUN_ID>`, because the evaluator requires the `SUPPORTDESK` prefix)

`tests/e2e/studio/01-greenfield.spec.ts` — DC-001 → R1
1. Create the project and a GREENFIELD_BUILD cycle from the studio intake. Wait until the repository is READY (guard `repository_ready_with_canonical_commit` no longer failing).
2. DISCOVERY: attach `PRD.md` in the composer → Decompose → `start_product_modeling`.
3. PRODUCT_MODEL: answer every open clarification. Open one feature spec, edit it and save a new version. Request scope approval.
4. **Human-in-the-loop deviation:** approver chooses *Request changes* with a note → operator edits the spec again and re-requests → approver *Approves*. Assert the first approval's subject hash differs from the second's.
5. `start_architecture` → Propose architecture → Request approval → approver *Rejects* with a note → operator proposes again → Request approval → approver *Approves* → `start_planning`.
6. PLANNING: Generate implementation specs → request approval for each → approver approves each. Generate task plan → Accept plan → `start_development`.
7. DEVELOPMENT: wait for all code tasks to complete (watch the task DAG). If a governed action needs an ACTION approval, approver decides it in the Decision panel. Then `start_integration`.
8. INTEGRATION → `start_assurance`. Warden and Sentinel are scheduled automatically by default policy. If neither starts within the stage timeout, trigger them from the assurance view. Waive or remediate findings only through the workspace, using an approval for waivers. Then `start_release` once `required_gates_pass` holds.
9. RELEASE: Create release → approver approves (manifest hash shown) → Execute → `complete`.
10. Assert, via the API: cycle `COMPLETE`; release `R1` `RELEASED` with `integrated_sha`.

`tests/e2e/studio/02-brownfield.spec.ts` — DC-002 → READY_FOR_CHANGE
1. Create a BROWNFIELD_ONBOARDING cycle on the project's repository.
2. `start_code_index` → wait for the index → `start_spec_recovery` → wait for the recovery proposal → `start_baseline`.
3. Work the review queue in the workspace. Record promotion decisions per `brownfield_review.yaml`; the approver records the approver-only decisions (promote as canonical, approve as project architecture, accept known gap), and the backend approves the resulting PROMOTION and ARCHITECTURE approvals in the same call. Then `start_readiness`.
4. If readiness fails as remediable: `start_remediation`, let it complete, `reassess_readiness`. Repeat until it passes or the stage timeout is reached.
5. `declare_ready` (no approval is requested).
6. Assert: cycle `READY`; project `readiness_state` `READY_FOR_CHANGE`.

`tests/e2e/studio/03-feature-change.spec.ts` — DC-003 → R2
1. Studio intake → *Change request* with the title and body of `change_priority.md` (`POST /projects/{p}/change-requests`). Open the cycle it returns.
2. `start_spec_delta` → wait for the interpretation and spec delta → Request approval → approver approves → `start_impact_analysis`.
3. Wait for the impact assessment and review it in the workspace. Resolve the architecture delta (propose and approve it, or decline it with a note) → `start_planning`.
4. Same as Greenfield steps 6–9 → release `R2`.
5. Assert: cycle `COMPLETE`; `R2` `RELEASED`.

`tests/e2e/studio/04-bug-fix.spec.ts` — DC-004 → R3
1. Studio intake → *Defect* with the title and description of `defect_closed_update.md` (`POST /projects/{p}/defects`). Open the cycle it returns (it starts at TRIAGE).
2. Wait for triage → `start_reproduction`. If the reproduction is not recorded within the timeout, use *Proceed unreproduced* with a reason; the approver decides the UNREPRODUCED_REPAIR approval.
3. `resolve_expected_behavior` → (EXPECTED_BEHAVIOR approval from RL3 onward) → `start_root_cause`.
4. Wait for root cause and the repair spec → approver approves the repair **IMPLEMENTATION_SPEC** → accept the task plan → `start_development`.
5. Development → `start_integration` → `start_regression` → wait for reproduction and regression to pass → `start_assurance` → release as in Greenfield steps 8–9 → `R3`.
6. Assert: cycle `COMPLETE`; `R3` `RELEASED`.

**Final acceptance** (`tests/e2e/studio/global-teardown.ts`, only when all four journeys passed):
run `uv run python scripts/acceptance/evaluate_mvp.py --project <project_id> --run-id <RUN_ID> --out var/olympus/reports` with `OLYMPUS_HUMAN_TOKEN=$OLYMPUS_APPROVER_TOKEN`. Fail the run if any check fails, and attach the generated `mvp_acceptance_<RUN_ID>.md` to the Playwright report. The evaluator checks, among others: project key, R1/R2/R3 released, four cycles terminal, project READY_FOR_CHANGE, live LLM used, no blocking findings, audit chain valid, LLM spend within budget.

Scripts: `npm run test:e2e:studio` (all four, serial), `npm run test:e2e:studio -- --grep greenfield` (one journey). Tag `@live`; skip with a clear message when the API or LLM key is missing.

Acceptance: on a clean database, `npm run test:e2e:studio` passes all four journeys and the evaluator reports every check passed. Commit the evaluator report path and the Playwright report summary to `STATUS.md` §16. Any `BACKEND_GAP` is listed there with the step that hit it.
