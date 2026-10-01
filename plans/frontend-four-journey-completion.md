# UI-19 Four-Journey Simulation — completion report (2026-10-01)

**Scope:** Fixture-only checkpointed world per `plans/frontend-four-journey-simulation.md`. Not backend E2E proof.

## Delivered

- **Contracts & services (SIM-01):** repository, runtime, assurance/release/control-plane extensions; `OlympusServices` + http stubs; query keys.
- **Engine (SIM-02):** `buildWorld`, `WorldBuilder`, deterministic clock/ids, store, `ScenarioController`, `?fx=` via `lib/api/fx-param.ts`, `ScenarioControlBar` + `CheckpointGuide`, checkpoint delta hook in `fixture-stream.ts`.
- **World narratives (SIM-04–07):** `world-variants.ts` + `world-mutations.ts` for Greenfield/Brownfield/Feature Change/Bug Fix (bug-fix chains FC@11); legacy `supportdesk/*` seed retained as builder input; deterministic timestamps in legacy modules.
- **Code model (SIM-03):** `code-model/revisions.ts`, `index-from-model.ts`, `diffs.ts`, `enrichCodeModel`, BFS `lineage-index.ts`.
- **Repository UX (SIM-08):** `/projects/[pid]/code` tabs (repository, workspaces, commits, …), `RepositoryHeader`, `MaterializationTimeline`, `RepositorySummaryChip` in ContextBar, `/repository` redirect.
- **Transparency (SIM-09–10):** Workspaces tab with NOT CANONICAL watermark; `DecisionExplainer` on Control Plane.
- **Tests (SIM-12):** world-build, consistency-rules, determinism-scan, secrets-and-paths, lineage, scenario-controller, repository-header component; Playwright `journey-feature-change.spec.ts`.
- **STATUS.md:** UI-19 row, checkpoint column, FE-C17–22, M-30–41, change log.

## Default demo position

`feature-change:05-development-running` (`NEXT_PUBLIC_FIXTURE_SCENARIO` / `?fx=`).

## Follow-ups (not blocking fixture demo)

- Per-checkpoint `.ts` apply modules under `runtime-a/` / `runtime-b/` (currently centralized in variants).
- Full §15 volume targets and remaining Playwright journey specs (greenfield, brownfield, bug-fix, screens-populated, axe).
- Remove legacy `lib/fixtures/scenarios/supportdesk/*` once all entities are checkpoint-authored.
