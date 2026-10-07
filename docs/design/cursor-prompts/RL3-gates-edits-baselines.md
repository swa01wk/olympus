# RL3 — Human gates, direct edits, baselines that can change

Paste everything below the line into a new Cursor Composer chat (Agent mode). Work directly on `main`. RL2 must be complete first.

---

You are closing the remaining governance gaps in **Olympus** (Python 3.12, FastAPI, SQLAlchemy async, PostgreSQL 16; Next.js Studio in `apps/dashboard`). After this phase:

- a human confirms what "correct" means for an underspecified bug;
- a human approves every task plan;
- approval notes reach later agents;
- reviewers can edit architecture and implementation specs directly;
- a bug fix can retire a baseline that pinned the bug.

## Read first

1. `docs/design/olympus-review-loop-plan.md` — this phase fixes **G5–G10** and implements decisions **4–8**.
2. `core/review/` from RL2 (`RevisionService`, `ensure_pending_approval`). Reuse it; don't duplicate it.
3. The files named in each step.

## Rules

- **Backend changes are allowed only in**:
  - `core/review/`, `core/commands/handlers.py`, `core/domain/enums.py` (`ApprovalType` only)
  - `core/domain/approvals/` (only if a step needs it), `core/product_model/defects/`, `core/product_model/knowledge.py`
  - `core/planning/task_plans/`, `core/planning/guards.py` (`task_plan_accepted_contracts_issued` only), `core/planning/architecture/`, `core/planning/implementation_specs/`
  - `core/intelligence/baselines/`, `core/assurance/obligations.py`, `core/assurance/gates.py`, `core/release/completion.py`
  - `core/execution/snapshots/product_context.py`, `core/runtime/profiles/*`, `agents/*/prompts/*`
  - `apps/control_api/routers/{planning,specs,defects,approvals}.py`
  - one new migration `migrations/versions/0033_rl3_review_gates.py`, and `config/policy/default.yaml` (`approvals_required` only).

  Anything else needs my OK first: say which file and why, then stop.
- State machine edges in `core/state/machines.py` do not change. A guard may gain a condition only where a step says so.
- Approvals are decided only by a human `APPROVER`, only in the Decision panel.
- Tests for every behaviour change. Journey tests and harnesses that accepted plans or resolved expected behaviour with a system actor are updated to use a human approver (`tests/fixtures/brownfield_phase12_harness.py` has `ensure_human_approver`). Explain each test change in the report.
- Templates render with `StrictUndefined`; every new variable must be passed by its profile. Bump template `version`s you change.

## How to work

1. Restate the step's goal and list the files. Then implement.
2. `make lint`, `make typecheck`, `make test-unit`, plus the persistence and integration tests you touched (Docker); `make migrate` against a fresh database for the migration; `npm run check` for Studio steps.
3. Commit each finished step to `main` with the message `RL3.<k>: <summary>`, and push when the phase's acceptance checks pass. Don't create branches.
4. Stop after each step with: what changed, test results, the commit, anything left over. Wait for `next`.

---

## RL3.1 — Migration 0033

One migration, `0033_rl3_review_gates.py` (`down_revision` = the current head; check `migrations/versions/`):

- `ALTER TYPE <approval type enum> ADD VALUE 'TASK_PLAN'`. Read the enum's real name from the database or migration `0003_p01_gov.py`, and use `op.get_context().autocommit_block()`.
- `expected_behavior_resolutions.contradicted_baseline_ids` JSONB, not null, default `[]`.
- `behavioral_baselines.provisional` boolean, not null, default `false`.

Add `TASK_PLAN` to `ApprovalType` and `approvals_required` (`TASK_PLAN: true`, `EXPECTED_BEHAVIOR: true`). Persistence test: upgrade, then downgrade (the enum value may stay; document that).

## RL3.2 — Human gate on expected behaviour (G5, G7, decision 6)

Files: `core/product_model/defects/service.py` (`persist_expected_behavior`), `core/product_model/defects/guards.py` (`expected_behavior_resolved`), `core/product_model/defects/completion.py`, `core/commands/handlers.py`.

- When Kira's classification is `UNDERSPECIFIED` or `CONFLICTING`:
  - Compute the **contradicted baselines**: ACTIVE baselines whose `lineage_key` is in the triage's `suspected_baseline_keys`, or whose `ac_lineage_key` is among the cited ACs. Store their ids on the resolution.
  - Raise an `EXPECTED_BEHAVIOR` approval through `ensure_pending_approval`. Use `subject_type="expected_behavior_resolution"`; the hash covers the statement, the proposed AC and the contradicted ids.
- `SPECIFIED` resolutions with no contradicted baselines need no approval (today's behaviour). `SPECIFIED` with contradicted baselines also raises the approval.
- `expected_behavior_resolved` additionally requires that approval to be APPROVED with a matching hash, whenever one was raised.
- On APPROVED:
  - The proposed AC becomes canonical as a new version of the feature's approved spec. Model this on how the feature-change path applies an approved spec delta (`ChangeRequestService.on_spec_delta_approved`).
  - Then run `start_root_cause` if allowed, as `BugFixCompletionService` does after other steps.
- On CHANGES_REQUESTED: re-run `kira.expected_behavior` with the note (add the row to RL2's `RevisionService` mapping and the revision block to `agents/kira/prompts/expected_behavior.md`).
- On REJECTED: the defect stays at EXPECTED_BEHAVIOR; the note is visible.
- Integration tests:
  - UNDERSPECIFIED → approval raised, root cause blocked.
  - Approve → AC canonical, root cause starts.
  - CHANGES_REQUESTED → re-run with the note.
  - SPECIFIED without conflicts → unchanged.

## RL3.3 — Contradicted baselines are superseded at release (G9)

Files: `core/assurance/obligations.py`, `core/intelligence/baselines/bug_fix_promotion.py`, `core/release/completion.py`.

- While a bug-fix cycle has an APPROVED expected behaviour, its `contradicted_baseline_ids` do not create `BASELINE_REQUIRED` obligations in that cycle. Record them on the verification plan as "superseded by approved expected behaviour <approval key>" so the reason is visible.
- `BugFixBaselinePromotionService.on_release`:
  - Mark those baselines `SUPERSEDED`.
  - Add the regression test as a new ACTIVE baseline (`source=REPAIR`) for the new canonical AC, mirroring `feature_change_promotion.py`.
- Integration test: a characterization baseline pins the bug; the bug fix approves a contradicting expected behaviour; assurance passes the BASELINE gate; after release the old baseline is SUPERSEDED and the new one ACTIVE.

## RL3.4 — Human gate on task plans (G6, decision 5)

Files: `core/planning/task_plans/service.py`, `core/planning/guards.py`, `apps/control_api/routers/planning.py`, `core/commands/handlers.py`, `core/review/service.py`.

- After `persist_proposed`, raise a `TASK_PLAN` approval (`subject_type="task_plan"`, hash of the plan body) via `ensure_pending_approval`.
- On APPROVED in `handle_approval_decide`, call `TaskPlanService.accept` with the approver's context.
- `accept` now requires a matching APPROVED `TASK_PLAN` approval. `task_plan_accepted_contracts_issued` checks it too.
- `POST /task-plans/{id}/commands/accept` stays as a convenience for approvers. It requires a human `APPROVER`, and requests and approves in one call, like the brownfield promotion pattern in `core/intelligence/recovered_specs/promotion.py`.
- CHANGES_REQUESTED re-runs `kira.task_plan` with the note (add to RL2's mapping).
- Update the planning and journey harnesses that accept plans with a system actor.
- Tests: a plan can't be accepted without approval; approve → contracts issued; CHANGES_REQUESTED → re-run.

## RL3.5 — Approval notes reach later agents (G8, decision 7)

Files: `core/product_model/knowledge.py`, `core/commands/handlers.py`, `core/execution/snapshots/product_context.py`, `core/runtime/profiles/*`, `agents/*/prompts/*`.

- On any APPROVED or CHANGES_REQUESTED decision with a non-empty note, create a `DECISION` knowledge item for the cycle: "`<approval type> <subject key>: <note>`". Add a `create_decision_from_approval` beside `create_decision_from_clarification`.
- `product_context_for_task` already loads the cycle's decisions as `decision_items`, but only Kira's decompose prompt uses them. Pass `decision_context` (same "Prior decisions:" format) to every Kira and Atlas prompt, `forge.implementation` (`agents/forge/prompts/implement.md`), `warden.review` and `sentinel.plan`. Add the variable to each template.
- Tests: a decision note appears in the rendered prompt of the next agent in the same cycle.

## RL3.6 — Provisional baselines for accepted known gaps (G10, decision 8)

Files: `core/intelligence/baselines/*`, `core/intelligence/recovered_specs/promotion.py` (read only), `core/assurance/obligations.py`, `core/assurance/gates.py`.

- When a baseline is created or activated in a brownfield cycle, set `provisional=true` if its `exercised_stable_keys` overlap the citations of an uncertainty decided `ACCEPT_KNOWN_GAP` in that cycle. This covers characterization, remediation and review activation.
- A provisional baseline that fails in a later cycle does not fail the BASELINE gate. It creates a non-blocking finding (category `RISK`, severity `MINOR`, title "Provisional baseline contradicted: <key>") that names the known gap.
- An `ACTIVATE` promotion decision on the baseline clears `provisional`.
- Expose `provisional` on `GET /projects/{p}/baselines` and `GET /baselines/{id}`.
- Tests: flag set from a known gap; a failing provisional baseline yields a MINOR finding and a passing gate; ACTIVATE clears it.

## RL3.7 — Direct edits (decision 4)

Files: `apps/control_api/routers/planning.py`, `core/planning/architecture/service.py`, `core/planning/implementation_specs/service.py`.

- `POST /architectures/{id}/versions {body, contracts?, note}` and `POST /implementation-specs/{id}/versions {body, note}`:
  - Validate exactly as agent output is validated: `validate_architecture_proposal`, and the implementation-spec conformance check in `core/planning/implementation_specs/conformance.py`.
  - Create the next version as PROPOSED and mark the previous one `SUPERSEDED`.
  - Record the editor in a domain event (`architecture.edited` / `implementation_spec.edited` with the actor and note).
  - Raise a fresh approval through `ensure_pending_approval`.
- Allowed only while the cycle is in the stage that owns the subject, and only for a PROPOSED subject. The edit's note also becomes a decision (RL3.5).
- Task plans have no edit endpoint.
- Tests: valid edit → v+1 PROPOSED with a PENDING approval; invalid body → 422 with the validator's messages; wrong stage → refused.

## RL3.8 — Studio

- **Decision panel, `EXPECTED_BEHAVIOR`** (at EXPECTED_BEHAVIOR): show the classification, Kira's statement, the proposed AC as given/when/then, the reporter's questions, and the contradicted baselines with their current given/when/then.
- **Decision panel, `TASK_PLAN`** (PLANNING; ROOT_CAUSE for bug fix — extend RL1.1's `approvalStage`): show the DAG, sizes, scopes and risks. Remove the standalone Accept button; plan acceptance is the approval.
- **Editors**:
  - Architecture: form for `ArchitectureBody` with lists for components, dependency rules, decisions, contracts.
  - Implementation spec: form for `ImplementationSpecBody`.
  - Both have a raw-JSON fallback and show validation errors from the API. Saving shows the v→v+1 diff (RL2 helper) and the fresh approval.
- **Baselines**: a "Provisional" badge in words, in brownfield and assurance views, with the known gap it rests on.
- Tests for each.

## RL3.9 — Status

`STATUS.md` §17: RL3 COMPLETE with milestone and test results, plus a changelog row. In `olympus-chat-workspace-plan.md` §1, `EXPECTED_BEHAVIOR` and `TASK_PLAN` are now created; update the list.

## Phase acceptance

- `make check` and `npm run check` green; `make migrate` on a fresh database.
- Integration scenario (deterministic, fake provider in-process) mirroring the Kanban Lite bug in `olympus-review-loop-plan.md`:
  1. A brownfield characterization baseline pins "deleting a column deletes its cards".
  2. A bug fix classifies the defect UNDERSPECIFIED and proposes 409.
  3. A human approves the expected behaviour, which lists that baseline.
  4. Repair, regression and assurance pass, including the BASELINE gate.
  5. The release supersedes the old baseline and activates the regression baseline.
