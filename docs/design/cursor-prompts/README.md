# Cursor prompts — review loop (RL1–RL4)

Spec: `docs/design/olympus-review-loop-plan.md`. Background on the journeys, stages and human checkpoints: `docs/design/olympus-journeys.md`. Run the phases in order; each builds on the previous one.

| Phase | Prompt | Touches | Done when |
|---|---|---|---|
| RL1 | `RL1-studio-gaps.md` | `apps/dashboard`, `docs/` | All four journeys can be driven from the Studio without calling the API by hand |
| RL2 | `RL2-review-loop.md` | backend (scoped) + `apps/dashboard` | Request changes on an architecture produces a revised v2 with a diff and a fresh approval; chat answers from the content and proposes generate steps; one product-spec view for greenfield and brownfield |
| RL3 | `RL3-gates-edits-baselines.md` | backend (scoped) + `apps/dashboard` | A bug fix that contradicts an onboarding baseline reaches release with a human-confirmed expected behaviour and the baseline superseded |
| RL4 | `RL4-prove-it.md` | `tests/`, `apps/dashboard/tests/e2e` | The acceptance evaluator passes on a live four-journey Studio run with no fallback flag |

## How to run a phase in Cursor (Composer)

Everything happens on `main`; there are no per-phase branches.

1. Open the repo root in Cursor. `git switch main && git pull`.
2. New Composer chat, Agent mode, model **Composer 2.5**. Paste the whole prompt file for the phase.
3. Composer works one step at a time, commits each finished step to `main` (`RL<N>.<k>: <summary>`), and stops with a report. Reply `next` to continue, or give corrections.
4. When the phase's acceptance checks pass, Composer pushes `main`. Start the next phase in a new chat.

Long phases have numbered steps (RL2.1, RL2.2 …). If a Composer chat gets long, start a new one with: `Continue phase RL<N> from step RL<N>.<k>. Read docs/design/cursor-prompts/RL<N>-*.md and STATUS.md §17 first.`

## Rules shared by every phase

These are repeated at the top of each prompt so each one can be pasted alone.

- Read `docs/design/olympus-review-loop-plan.md` first. Finding ids (G1, S4, …) and decision numbers refer to it.
- The backend is changed only where the phase says. Never invent an endpoint, field or enum value; read the router and Pydantic model.
- Approvals are decided only by a human `APPROVER`, only in the Decision panel. Chat never decides.
- Every backend change ships with tests at the right marker (`unit`, `persistence`, `integration`). Existing journey and phase tests must keep passing.
- Backend checks: `make lint`, `make typecheck`, `make test-unit`; `make check` before the phase ends (needs Docker for Testcontainers).
- Frontend checks: `npm run check` in `apps/dashboard`.
- Record progress in `STATUS.md` §17 (created in RL1).
