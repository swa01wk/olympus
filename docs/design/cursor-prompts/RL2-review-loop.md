# RL2 — Revision loop, chat that sees the content, auto-requested approvals

Paste everything below the line into a new Cursor Composer chat (Agent mode). Work on a branch `rl2-review-loop`. RL1 must be merged first.

---

You are adding the review loop to **Olympus**, a governed AI software-delivery control plane (Python 3.12, FastAPI, SQLAlchemy async, PostgreSQL + pgvector; Next.js Studio in `apps/dashboard`). After this phase a reviewer can ask for changes at a checkpoint and get a revised version with a diff and a fresh approval, and the chat can discuss the content being reviewed.

## Read first

1. `docs/design/olympus-review-loop-plan.md` — this phase fixes **G1–G4** and **G11–G13** and implements decisions **1–3** and **9–10** (§2, §3).
2. `docs/design/olympus-chat-workspace-plan.md` §1 and §4 — the Studio's rules.
3. The files named in each step. Read the real code before changing it; never invent a field, enum value or route.

## Rules

- **Backend changes are allowed only in these places**: `core/commands/handlers.py` (`handle_approval_decide`), a new package `core/review/`, `core/planning/orchestrator.py`, `core/planning/completion.py`, `core/planning/architecture/service.py`, `core/planning/implementation_specs/service.py`, `core/product_model/decomposition.py`, `core/product_model/changes/orchestrator.py`, `core/product_model/changes/completion.py`, `core/product_model/defects/orchestrator.py`, `core/orchestrator/` (all), `core/runtime/profiles/kira.py`, `core/runtime/profiles/atlas.py`, `core/runtime/profiles/orchestrator.py`, `agents/kira/prompts/*`, `agents/atlas/prompts/*`, `agents/orchestrator/*`, `apps/control_api/routers/orchestrator.py`, `core/commands/registry.py`, `core/commands/catalog.py`, a new `core/commands/generation_handlers.py`, a new `core/product_model/spec_view.py`, `apps/control_api/routers/specs.py` and `apps/control_api/routers/product_model.py` (additive read fields and one new read route only). Anything else needs my OK first: say which file and why, then stop.
- No migration in this phase. If you find you need one, stop and say why.
- State machines (`core/state/machines.py`) and guards do not change.
- **Approvals are decided only by a human `APPROVER`, only in the Decision panel.** The chat may draft a note; it never decides.
- Every behaviour change gets tests: `unit` for pure logic, `persistence` or `integration` for anything touching the database. Existing tests must keep passing. A test that relied on an approval not being auto-requested is updated, not deleted, and the change is explained in the report.
- Prompt templates render with Jinja `StrictUndefined` (`core/runtime/prompts/registry.py`). Every variable a template uses must be passed by its profile, even as `""`. Bump the template's front-matter `version` when you change it.

## How to work

1. Restate the step's goal and list the files you'll change. Then implement.
2. Backend: `make lint`, `make typecheck`, `make test-unit`, plus the persistence or integration tests you touched (`uv run pytest -m "persistence or integration" tests/<path>`; needs Docker). Frontend: `npm run check` in `apps/dashboard`.
3. Stop after each step with: what changed, test results, anything left over. Wait for `next`.

---

## RL2.1 — Revision inputs reach the agents

Contract bodies already carry an extension dict `_snapshot`. `core/execution/snapshots/builder.py` merges it into the execution snapshot, and profiles read it with `deps.request.snapshot.get(...)`.

- In `core/runtime/profiles/kira.py` and `core/runtime/profiles/atlas.py`, pass two new variables to every `render_prompt` call: `revision_feedback` and `previous_output_json`, read from the snapshot, defaulting to `""`.
- Add this block, adapted to the agent's wording, to `agents/kira/prompts/{decompose,change_interpret,implementation_spec,implementation_spec_delta,implementation_spec_repair,task_plan}.md` and `agents/atlas/prompts/{propose_architecture,architecture_delta}.md`, just before the output instructions:

  ```
  {% if revision_feedback %}
  ## Revision request
  A reviewer asked for changes to your previous output.
  Reviewer's note:
  {{ revision_feedback }}
  Your previous output:
  {{ previous_output_json }}
  Produce a complete new output. Change only what the note asks for, keep everything else as it was, and do not reintroduce anything the note asks to remove.
  {% endif %}
  ```

- Unit tests: each template renders with and without the variables; each profile passes both.

## RL2.2 — Orchestrators accept a revision

Add an optional `revision: RevisionContext | None = None` argument (a frozen dataclass in `core/review/context.py`: `approval_id`, `feedback`, `previous_output_json`, `subject_type`, `subject_id`) to the functions that schedule producing agents. When given, merge `{"revision_feedback", "previous_output_json", "revision_of_approval_id"}` into the contract's `_snapshot` (merge with any existing `_snapshot`; the bug-fix orchestrator already sets one).

- `PlanningOrchestrator.start_architecture_proposal`, `.start_implementation_spec_generation` (add an optional `feature_spec_id` so one feature can be regenerated), `.start_task_plan_generation` — `core/planning/orchestrator.py`.
- `DecompositionOrchestrator.start_decomposition` — `core/product_model/decomposition.py`.
- `FeatureChangeOrchestrator.schedule_change_interpret`, `.schedule_implementation_spec_delta`, `.schedule_architecture_delta` — `core/product_model/changes/orchestrator.py`.
- The repair implementation-spec scheduler in `core/product_model/defects/orchestrator.py`.

Without `revision`, behaviour and contract hashes must be unchanged (assert this in a test).

## RL2.3 — Request changes re-runs the producing agent (G1, G2)

New `core/review/service.py` with `RevisionService.request_revision(session, approval, ctx) -> uuid.UUID | None`. Call it from `handle_approval_decide` when the decision is `CHANGES_REQUESTED`, after `ApprovalService.decide`.

Map the approval's subject to the agent to re-run. `feedback` is the decision note; `previous_output_json` is the subject's current body.

| Approval type | `subject_type` | Re-run |
|---|---|---|
| SCOPE | `scope_set` | `DecompositionOrchestrator.start_decomposition` on the cycle's latest product source (only in DISCOVERY or PRODUCT_MODEL) |
| ARCHITECTURE | `architecture` (kind not DELTA) | `start_architecture_proposal` |
| ARCHITECTURE_DELTA | `architecture` (kind DELTA, from RL2.5) | `schedule_architecture_delta` |
| IMPLEMENTATION_SPEC | `implementation_spec` | by the spec's `kind`: feature → `start_implementation_spec_generation(feature_spec_id=…)`; DELTA → `schedule_implementation_spec_delta`; REPAIR → the repair scheduler; REMEDIATION → no agent (it is drafted deterministically): return `None` |
| SPEC_DELTA | spec delta | `schedule_change_interpret` |
| RELEASE, FINDING_WAIVER, ACTION, PROMOTION, UNREPRODUCED_REPAIR | — | no agent: return `None` |

Read the exact `subject_type` strings from each `request_approval` call site; don't guess them.

- Idempotent: one revision task per approval. A second call for the same approval returns the same task id.
- Emit a domain event `revision.requested` `{approval_id, subject_type, subject_id, task_id}` on the cycle.
- When the revised output is persisted (`core/planning/completion.py`, `core/product_model/changes/completion.py`, and the decomposition persist path), set the previous version's status to `SUPERSEDED`. Then emit `revision.completed` `{approval_id, old_subject_id, new_subject_id}`. Find the previous version through `_snapshot.revision_of_approval_id`.
- `REJECTED` keeps today's behaviour: no re-run.
- Integration tests: CHANGES_REQUESTED on an architecture creates one `atlas.propose_architecture` task whose contract `_snapshot` carries the note and the previous body; persisting a fake output supersedes v1 and creates v2; a second decide call doesn't create a second task.

## RL2.4 — The backend raises approvals itself (decision 3)

New `core/review/auto_request.py`: `ensure_pending_approval(session, *, approval_type, subject_type, subject_id, subject_version, subject_hash, delivery_cycle_id, ctx)` returns the existing PENDING approval for the same subject and hash, or requests one through the existing service method.

- Call it right after persisting: an architecture (`ArchitectureService.persist_proposal`), an implementation spec (`ImplementationSpecService.persist_draft` and `.persist_repair_draft`), and an architecture delta (RL2.5). Spec deltas already auto-request; leave them. Scope stays an explicit request.
- Make the existing explicit `…/approval-request` endpoints idempotent through the same helper, so the Studio buttons and the journey tests keep working.
- Integration test: persisting an architecture leaves exactly one PENDING `ARCHITECTURE` approval, and calling the approval-request endpoint afterwards returns that same approval id.

## RL2.5 — Persist the architecture delta (G11)

Today `atlas.architecture_delta` output only emits `architecture_delta.proposed` (`core/product_model/changes/completion.py`). Nothing creates the `Architecture` row with `kind="DELTA"` that `architecture_delta_resolved` (`core/intelligence/impact/guards.py`) looks for, and nothing raises an approval. So "propose" can never pass the guard.

- In `FeatureChangeCompletionService.persist_from_execution`, for `atlas.architecture_delta`, add `ArchitectureService.persist_delta(...)`. It creates an `Architecture` with `kind="DELTA"`, status `PROPOSED`, the next version on the project's architecture lineage, `body` = the `ArchitectureDeltaProposal`, and a `content_hash`.
- Raise an `ARCHITECTURE_DELTA` approval for it with `subject_type="architecture"` (RL2.4 helper).
- In `handle_approval_decide`, an APPROVED `ARCHITECTURE_DELTA` whose `subject_type` is `architecture` calls `ArchitectureService.on_approved`. The decline path (`subject_type="ARCHITECTURE_DELTA_DECLINED"`) is unchanged.
- Integration test: feature-change cycle with `architecture_delta_suggested`; fake delta output → PENDING approval → approve → `architecture_delta_resolved` passes.

## RL2.6 — The chat sees what you're reviewing (G3, G4)

Files: `apps/control_api/routers/orchestrator.py`, `core/orchestrator/service.py`, `core/orchestrator/validator.py`, `agents/orchestrator/schemas.py`, `agents/orchestrator/prompts/converse.md`, `core/runtime/profiles/orchestrator.py`.

- `TurnBody` gains an optional `focus: {subject_type, subject_id}`. Allowed subject types: `product_source`, `feature_spec`, `scope_set`, `architecture`, `implementation_spec`, `task_plan`, `spec_delta`, `impact_assessment`, `defect`, `release`. Store `focus` on the user turn.
- `build_snapshot`:
  - Use the **cycle** overview whenever the session has a `delivery_cycle_id` (G4). Keep the project overview as a second key.
  - Add `focus` from a loader registry in `core/orchestrator/focus.py`. Each loader returns `{type, id, key, version, status, content_hash, body, sources}`.
  - `sources` = what the subject was built from:
    - a feature spec → the PRD sections it cites;
    - an architecture → the approved feature specs (key + summary);
    - an implementation spec → its feature spec and architecture refs;
    - a task plan → its implementation spec keys;
    - a spec delta → the change request text;
    - a defect → its triage, expected behaviour and root cause.
  - Cap the focus at 24,000 characters, truncating `sources` first, and set `truncated: true` when you do.
- New intent `REVISION_NOTE_DRAFT` with `revision_note_draft: {approval_id, note}`. The validator accepts it only when `approval_id` is a PENDING approval in the snapshot's inbox.
- `complete_turn` persists `revision_note_draft`, `navigate_to` and `refs` (it drops the last two today).
- `converse.md` instructions:
  - Answer questions about the focused subject from `focus`, citing keys.
  - When the user asks to change something that has a pending approval, reply with `REVISION_NOTE_DRAFT`: a concrete, minimal note.
  - Never decide an approval.
- Tests:
  - G4 regression: a session with both ids gets the cycle overview.
  - Each focus loader against seeded rows, including truncation.
  - The validator accepts and rejects revision drafts correctly.
  - `complete_turn` persists the new fields.

## RL2.7 — Studio: focus, revision state, diff, note draft

Files: `apps/dashboard/src/api/*`, `apps/dashboard/components/studio/*`, `apps/dashboard/lib/*`.

- Types: `focus` on `postTurn`; `revision_note_draft`, `navigate_to`, `refs` on assistant turns; the `REVISION_NOTE_DRAFT` intent.
- Each stage view registers the subject it has magnified (a small context, `useStudioFocus`). `useOrchestratorChat.send` sends it as `focus`.
- `RevisionNoteDraftCard`: shows the drafted note with **Use in decision panel**, which fills the Decision panel's note for that approval and scrolls to it. It never submits.
- On `revision.requested` for the visible subject, show "Revising: <agent> is preparing version N+1". On `revision.completed`, load both versions and show a diff: a line diff of the bodies rendered as stable, pretty-printed JSON, with no new dependency (write a small LCS helper in `lib/` with tests). Show the fresh approval in the Decision panel.
- Keep the RL1.7 helper text only for approval types with no agent (see the RL2.3 table). For the rest, the text becomes: "The agent will revise using your note."
- NAVIGATE turns: `navigate_to` selects the stage (`?stage=`).
- Tests: the card fills the note and doesn't submit; the diff helper; the revising state follows events; `focus` is sent.

## RL2.8 — One product-spec view for both entry points (G12, decision 9)

A greenfield PRD and a brownfield repo end in the same canonical model, but nothing shows it as one document, and the API hides where each rule came from.

Backend (additive only; existing fields and routes keep their shape):

- `GET /specs/{id}` (`apps/control_api/routers/specs.py`): add `promoted_from_id` and `derived_from_source_version_id`, and `given`, `when`, `then` on each acceptance criterion.
- `FeatureResponse` (`apps/control_api/routers/product_model.py`): add `description`, `origin` (`ModelOrigin`) and `source_refs`.
- New read route `GET /projects/{p}/product-spec`, built by `core/product_model/spec_view.py`. It returns, per capability, per feature, the **current canonical spec**: the latest version per lineage with status APPROVED, PROMOTED or CONFIRMED_EXISTING. Each spec carries:
  - its body;
  - its ACs with given/when/then and mandatory flag;
  - a `provenance` block:
    - greenfield: product source id, version, title and the feature's `source_refs` (PRD sections);
    - brownfield: follow `promoted_from_id` to the recovered spec and return its `confidence` and `recovered_evidence`;
  - `known_gaps`: uncertainties decided `ACCEPT_KNOWN_GAP` that cite this feature's entities.
- Tests: persistence tests for one greenfield-decomposed spec and one promoted recovered spec; the new route returns both in the same shape.

Studio:

- `components/studio/ProductSpecView.tsx`: renders `GET /projects/{p}/product-spec` as a PRD-shaped document, reachable from the control panel ("Product spec").
  - Layout: capability headings, feature headings, behaviour, rules, ACs as given/when/then.
  - Each rule and AC has a provenance chip in words: "PRD v2 · Feature: Archive project" (opens the source content), or "HIGH · tests/test_cards.py::test_move_card".
  - Known gaps are marked "Known gap: not confirmed".
- Embed it in the PRODUCT_MODEL stage (greenfield, after scope approval) and the BASELINE and READY stages (brownfield).
- A "Copy as Markdown" button produces the same document as text.
- Tests: both provenance kinds render; the Markdown export matches a snapshot.

## RL2.9 — The chat can propose every generate step (G13, decision 10)

Today the chat can only propose commands registered on the bus (`core/commands/registry.py`) and listed in `core/commands/catalog.py`. The generate steps are REST-only.

- In `core/commands/generation_handlers.py`, add handlers that call the **same** orchestrator or service methods the REST routes call:
  - `architecture.propose {cycle_id}`
  - `implementation_specs.generate {cycle_id, feature_spec_id?}`
  - `task_plan.generate {cycle_id}`
  - `change_interpretation.rerun {cycle_id}`
  - `architecture_delta.propose {cycle_id}`
  - `release.create {cycle_id}`

  Register them in `build_command_bus`. Add catalog entries with `target_type: "delivery_cycle"`, `required_roles: ["OPERATOR"]` and a payload schema. The REST routes stay as they are.
- `agents/orchestrator/prompts/converse.md`: when the cycle sits at a stage whose generate step hasn't run, or has finished and was rejected, propose the matching command with a one-line rationale. Never propose `approval.decide`.
- Studio `src/api/proposal-routes.ts`: map each new command to its existing REST route:
  - `architecture.propose` → `POST /delivery-cycles/{c}/architecture/propose`
  - `implementation_specs.generate` → `POST /delivery-cycles/{c}/implementation-specs/generate`
  - `task_plan.generate` → `POST /delivery-cycles/{c}/task-plan/generate`
  - `change_interpretation.rerun` → `POST /delivery-cycles/{c}/change-interpretation/rerun`
  - `architecture_delta.propose` → `POST /delivery-cycles/{c}/architecture-delta/propose`
  - `release.create` → `POST /delivery-cycles/{c}/release`

  The proposal card shows the route and runs it only after a click.
- Tests:
  - the catalog export includes the six commands;
  - the orchestrator validator accepts a proposal for each;
  - each handler calls its orchestrator (mocked);
  - `routeForProposal` has a case per command.

## RL2.10 — Live check and status

- Add `tests/integration/live_llm/test_revision_loop_live.py` (`live_llm` marker, skipped without keys): request changes on a real Atlas proposal with the note "Put the archived-project rule in one ProjectGuard used by the service layer". Assert v2 exists, v1 is SUPERSEDED, a new PENDING approval exists, and v2's decisions mention a single guard.
- Update `STATUS.md` §17: RL2 COMPLETE with the milestone and test results, plus a changelog row. In `docs/design/olympus-chat-workspace-plan.md` §3, mark B-01 (`navigate_to` and `refs`) and B-03 (chat can't propose REST-only steps) fixed.

## Phase acceptance

- `make check` and `npm run check` green; existing journey tests unchanged in outcome.
- In the Studio, on a live greenfield cycle at ARCHITECTURE:
  1. Ask the chat "why is X done this way?" and get an answer that cites the architecture's decisions.
  2. Click Request changes with a note.
  3. See "Revising", then a v1→v2 diff that changes only what the note asked, with a fresh approval in the Decision panel.
- The chat proposes "generate the architecture" at an empty ARCHITECTURE stage, and the card runs it.
- "Product spec" renders a greenfield project and a brownfield project in the same shape, each rule showing its source.
