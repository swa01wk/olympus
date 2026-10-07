# RL4 — Prove it: honest journey tests and a live run through the Studio

Paste everything below the line into a new Cursor Composer chat (Agent mode). Work on a branch `rl4-prove-it`. RL1–RL3 must be merged first.

---

You are proving that **Olympus** works end to end with live agents and real human decisions. Today some journey tests pass because harness code fills in for agents that stall. This phase:

- makes those fallbacks explicit;
- adds two new scenario suites (TaskFlow from a PRD, Kanban Lite from a repo) that exercise the review loop and the new gates;
- runs the four-journey acceptance through the Studio UI.

## Read first

1. `docs/design/olympus-review-loop-plan.md` (all phases) and `STATUS.md` §16–§17.
2. `docs/design/olympus-cursor-prompt-chat-workspace.md` §C7 (as corrected in RL1.8).
3. `tests/journey/chained/runner.py`, `tests/journey/chained/greenfield_live.py`, `tests/journey/feature_change_live_pipeline.py`, `tests/journey/bug_fix_helpers.py`, `tests/fixtures/release_harness.py`, `tests/fixtures/assurance_harness.py`, `tests/fixtures/brownfield_phase12_harness.py`, `scripts/acceptance/evaluate_mvp.py`.

## Rules

- **No production code changes** (`core/`, `apps/`, `agents/`, `migrations/`) except fixing a defect a test exposes. If you must fix one, stop first and describe the defect, the evidence and the fix, then wait for my OK.
- Live tests need `LLM_LIVE_TESTS=1` and a provider key, and must skip with a clear message without them. Never assert an LLM's exact wording; assert structure, state and records.
- A scenario that can't complete over HTTP is a finding: fail with `BACKEND_GAP: <step>` and record it in `STATUS.md` §17. Don't seed or patch around it.

## How to work

1. Restate the step's goal and the files. Implement.
2. Deterministic lanes: `make check`. Live lanes: run what your keys allow and report cost and duration.
3. Stop after each step with a report. Wait for `next`.

---

## RL4.1 — Make every fallback explicit

The live journey helpers fill in for agents in these places (verify each and find any others):

- `greenfield_live.py`: completes code tasks from fixture files when Forge doesn't finish.
- `feature_change_live_pipeline.py`: `complete_feature_change_implementation_tasks`; scope approval seeded.
- `bug_fix_helpers.py`: the `maybe_apply_*_fallback` functions (triage, reproduction, root cause, repair spec).
- `release_harness.py`: `patch_agentless_assurance`, `_stub_unsatisfied_required_obligations` and `_waive_open_blocking_findings`; it also calls `finalize_all_pending_gates` (`tests/fixtures/assurance_harness.py`) with a synthetic human.
- `brownfield_phase12_harness.py`: `_declare_ready_with_workflow_thresholds` (zeroes every readiness threshold), and the empty characterization plan from `FakeProvider` in live tests.

Steps:

- Gate each live-path fallback on `OLYMPUS_JOURNEY_FALLBACKS=1`, default off.
- With the flag off, the point where a fallback would have run fails with `AGENT_STALLED: <stage> <agent profile> <execution id>` and the last `next-transitions` guard results.
- With the flag on, every use is appended to `var/olympus/reports/fallbacks_<run_id>.json` and printed in the test summary.
- The deterministic lane (`tests/journey/test_greenfield_supportdesk.py`, `make test-journey`) keeps its seeds. Rename its docstring to say plainly that it is deterministic and seeded.
- `scripts/acceptance/evaluate_mvp.py`: add a check that fails when a fallbacks file exists for the run.

## RL4.2 — Scenario fixtures

Create the fixtures below. They mirror a walkthrough already reviewed with the product owner; keep names and behaviours as written.

### TaskFlow (`tests/fixtures/taskflow/`)

`PRD.md`:

```markdown
# TaskFlow — Product Requirements Document

## Overview
TaskFlow is a lightweight project and task tracker for small teams.
Stack (NFR): FastAPI, SQLAlchemy, pytest. SQLite is acceptable.

## Capability: Project management
### Feature: Create project
A user creates a project with a name. Default status is ACTIVE.
Rules: name is required and unique.
### Feature: Archive project
Archived projects are read-only: their tasks can't be created or changed (409).
### Feature: List projects
List projects, optionally filtered by status.

## Capability: Task management
### Feature: Create task
Title is required. A task belongs to one project. Default status is TODO.
Optional assignee (email) and due_date.
### Feature: Update task status
TODO → IN_PROGRESS → DONE. DONE → TODO reopens a task.
An unknown status is rejected with 422.
### Feature: Assign task
Set or clear a task's assignee.
### Feature: List tasks
List a project's tasks, filtered by status and assignee.

## Capability: Platform
### Feature: Health check
```

`clarification_answers.yaml` (match a question by keyword):

- `uniqueness` / `case` → "Case-insensitive: 'Website' and 'website' collide; a clash returns 409."
- `archive` / `who` → "Any user; v1 has no auth."

`approvals.yaml`:

- **SCOPE**: approve, note "v1 scope as written; auth and comments are out of scope".
- **ARCHITECTURE v1**: CHANGES_REQUESTED, note "Put the archived-project rule in one ProjectGuard that TaskService calls; don't check it in each router."
- **ARCHITECTURE v2**: approve.
- Every other approval: approve.

`change_overdue.md`:

```markdown
# Change request: overdue tasks

Show which tasks are overdue. A task is overdue when its due_date
is before today and its status isn't DONE.
- Add is_overdue to every task response.
- GET /projects/{id}/tasks accepts ?overdue=true.
```

Its SPEC_DELTA approval note: "Use the UTC date for today."

`defect_reopen_archived.md`:

```markdown
# Defect: reopening a task in an archived project succeeds

Steps
1. Archive project P.
2. Take a DONE task in P.
3. PATCH /tasks/{id}/status {"status": "TODO"}

Actual: 200, and the task is reopened.
Expected: 409. Archived projects are read-only.
```

### Kanban Lite (`tests/fixtures/repos/kanban_lite/`, plus `tests/fixtures/kanban_lite/`)

A small existing FastAPI app, about 600 lines, written as a team would have written it without Olympus. Python 3.12, FastAPI, SQLAlchemy 2, Pydantic 2, pytest, SQLite through `create_all`; no migrations. A README that only says "A tiny kanban API."

- `app/models.py`: `Board(id, name)`, `Column(id, board_id, name, position)`, `Card(id, column_id, title, position, archived)`. `Column.cards` uses `cascade="all, delete-orphan"`.
- `app/routers/boards.py`:
  - `POST /boards`, `GET /boards` (with columns), `POST /boards/{id}/columns` (appended at the next position);
  - `DELETE /columns/{id}` (deletes without checking for cards).
  - This router writes through the session directly.
- `app/routers/cards.py`: `POST /columns/{id}/cards` (appended at the end), `PATCH /cards/{id}/move {column_id, position}`, `PATCH /cards/{id}/archive`.
- `app/services/card_service.py`: `move_card` (returns 400 when the target column is on another board) and `_reorder` (dense integer positions within a column).
- `tests/test_boards.py` (4 tests) and `tests/test_cards.py` (6 tests). Cover create board, list boards, add column, create card, move card within a board, and archive card. Leave **no** test for the cross-board 400 or for deleting a column.

`tests/fixtures/kanban_lite/`:

- `brownfield_review.yaml`:
  - Promote every recovered feature spec and implementation spec.
  - Approve the recovered architecture (keep the router bypass).
  - Activate every baseline with evidence; defer the rest.
  - Accept the cascade-delete uncertainty as a known gap: "Behaviour not confirmed with product yet."
- `change_wip_limits.md`:

  ```markdown
  # Change request: WIP limits

  Columns can have an optional wip_limit. Creating a card in, or moving
  a card into, a column that's already at its limit returns 409.
  Archived cards don't count toward the limit.
  ```

  Expected: impact suggests an architecture delta. The scenario **proposes** it (Atlas), and the human approves it with the note "One home for the limit check; also removes the router bypass."
- `defect_delete_column.md`:

  ```markdown
  # Defect: deleting a column silently deletes its cards

  Steps: a board has a column "Doing" with 3 cards. DELETE /columns/{id}.
  Actual: 204, and the 3 cards are gone.
  Expected: we shouldn't lose cards. Either block the delete or move them.
  ```

  Expected behaviour: the human approves "deleting a non-empty column returns 409; an empty column still deletes with 204" and confirms that the delete-column baseline is contradicted.

## RL4.3 — Scenario suites

`journey` + `live_llm` markers; each journey in its own file, resumable through a run file under `var/olympus/journeys/<run_id>.json`. Drive every step over HTTP with an operator token and an approver token, as the Studio does. No service-layer shortcuts; fallbacks only behind RL4.1's flag.

**TaskFlow** (`tests/journey/taskflow/`)

1. Greenfield → R1:
   - Answer the clarifications.
   - At ARCHITECTURE, Request changes with the note, then assert v1 is `SUPERSEDED`, v2 is `PROPOSED`, a new PENDING approval exists, and v2 is not v1.
   - Approve v2.
   - The task plan needs a `TASK_PLAN` approval.
   - Assert R1 is `RELEASED`.
2. Feature change → R2: assert the SPEC_DELTA note became a decision visible in the next agent's snapshot (`decision_items`).
3. Bug fix → R3: classification SPECIFIED citing the archived-project AC; no `EXPECTED_BEHAVIOR` approval is raised; the regression test fails on R2's SHA and passes on R3's.

**Kanban Lite** (`tests/journey/kanban_lite/`; register the fixture repo as `LOCAL` or through the Gitea profile)

1. Brownfield → READY_FOR_CHANGE, with the real readiness thresholds:
   - If readiness fails as remediable, run remediation.
   - Assert the delete-column baseline is `provisional` (it rests on the accepted known gap).
2. Feature change → R1: the architecture delta is proposed, persisted, approved and resolves the guard; the BASELINE gate runs the impacted baselines.
3. Bug fix → R2:
   - UNDERSPECIFIED → an `EXPECTED_BEHAVIOR` approval listing the delete-column baseline.
   - Approve it → the BASELINE gate passes.
   - After release, the old baseline is `SUPERSEDED` and the regression baseline is `ACTIVE`.

Add `make test-journey-taskflow` and `make test-journey-kanban`.

## RL4.4 — Studio live run (C7b)

Implement C7b from `docs/design/olympus-cursor-prompt-chat-workspace.md` (Playwright, four journeys through the UI, two browser contexts, `BACKEND_GAP` on any missing route). Also, in the greenfield spec:

- At ARCHITECTURE, the approver uses **Request changes**. Assert the Studio shows "Revising", then a v1→v2 diff and a new Decision panel.
- The operator makes one **direct edit** to an implementation spec. Assert the diff and the fresh approval.
- Ask the chat a question about the focused architecture. Assert the assistant turn arrives and cites at least one record key. Don't assert wording.
- At the bug fix, the `EXPECTED_BEHAVIOR` panel appears only if the classification needs it.

Then run `scripts/acceptance/evaluate_mvp.py` as C7b describes, with the RL4.1 fallbacks check.

## RL4.5 — Report

`STATUS.md` §17: RL4 COMPLETE only when the evaluator passes with no fallbacks file. Record:

- run ids, duration and LLM spend per suite;
- every `AGENT_STALLED` and `BACKEND_GAP` seen, with its stage;
- the Playwright report path.

Add a changelog row.

## Phase acceptance

- `make check` green; deterministic lanes unchanged.
- `make test-journey-taskflow`, `make test-journey-kanban` and `npm run test:e2e:studio` pass live with `OLYMPUS_JOURNEY_FALLBACKS` unset.
- The evaluator passes, and there's no `var/olympus/reports/fallbacks_<run_id>.json`.
