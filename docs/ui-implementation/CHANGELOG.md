# UI implementation changelog

## Phase 0 — Discovery (2026-10-07)

- Added `docs/ui-implementation/00-discovery.md` — writable paths, backend/frontend inventory, capability map.
- Added `docs/ui-implementation/routes.txt` — 205 Control API routes.

## Phase 1 — Plan (2026-10-07)

- Added `docs/ui-implementation/01-plan.md` — routes, lane/stage mapping, components, phases 2–7.
- Added `docs/ui-implementation/gap-report.md` — missing/derivable items and UI degradation.
- Added `docs/ui-implementation/CHANGELOG.md` (this file).

**Files changed:** `docs/ui-implementation/*` only (no `apps/dashboard/` yet).

## Phase 2 — Foundations (2026-10-07)

- Scaffolded `apps/dashboard/` (Next.js 16, React 19, Tailwind 4, Vitest).
- `styles/tokens.css` + `primitives.css` from design tokens.
- `src/control-plane/lanes.ts`, `stage-lanes.ts`, `attention.ts`.
- `src/adapters/status.ts`.
- Primitives: Button, StatusBadge, ProvenanceBadge, IdRef, Sha, Panel, KV, EmptyState.
- Unit tests for adapters and StatusBadge.

## Phase 3 — Data layer (2026-10-07)

- `src/api/client.ts`, `resources.ts`, `commands.ts`, `query-keys.ts`, core types.
- TanStack Query hooks (`useControlPlaneGraph`, projects, cycles, inbox, attention).
- Fetch-based SSE (`useCycleEventStream` / `useCycleLiveUpdates`) with query invalidation.
- `buildControlPlaneGraph` adapter + unit tests.
- `StreamStatus` shell component; dev cycle panel on `/`.

## Phase 4 — Shell and S02 cycle map (2026-10-07)

- App shell: `TopBar`, `NavRail`, `AppShell`, `StreamStatus`.
- Cycle chrome: `CycleHeader`, `LifecycleRibbon`, `AttentionStrip`.
- S02 hub: `ControlPlaneGraphView`, `ObjectInspector`, lenses, graph/list modes, SVG edges.
- Routes: `/projects`, `/projects/:id`, `/projects/:id/cycles/:cycleId` (+ tasks placeholder).
- Design map styles in `styles/map.css`.

## Phase 5 — Drill-downs S01, S03–S10, IO, AU (2026-10-07)

- Shared drill chrome: `CycleDrillFrame`, `LaneStrip`.
- Screens wired to Control API: product/specs, task DAG + contract, executions, code, traceability, impact, assurance, outcome, integrations, audit.
- S01 project overview: truth tiles, coverage, cycle table.
- Legacy `/projects/:id/control-plane` → active cycle map.
- Routes under `app/(console)/` for all nav rail targets.

## Phase 6 — Dialogs and commands (2026-10-07)

- Modal focus trap: `ModalDialog`, `DrawerPanel`, dialog CSS.
- `ApprovalDialog`, `CheckpointDialog`, `IntakeFormDialog`, `CycleCommandDialog`, `AskOlympusDrawer`.
- `OperatorDialogsProvider` + TopBar intake / Ask Olympus.
- Cycle commands confirm with API preview + `Idempotency-Key`; attention opens approval/clarification.

## Phase 7 — Truth rules, tests, e2e (2026-10-07)

- Exceptional-state components (`ExceptionState`, stream disconnect, reconciliation G9, remediation G10, terminal cycle).
- S01 coverage filter hides aggregate `%` (G6); inspector “why unavailable” pattern.
- Component/unit tests: EvidenceMatrix, EligibilityChecklist, ObjectInspector, coverage/terminal helpers.
- Playwright smoke with `tests/fixtures/` route mocks; `npm run test:e2e`.

## MVP exit — operator UI (2026-10-07)

- `MVP-OPERATOR-UI.md`: Phase 19 alignment, manual smoke, path to chained Playwright walkthrough.
- CI: `.github/workflows/dashboard.yml` (check + e2e).

## Plan 19 — R3 walkthrough handoff (2026-10-07)

- Chained driver pause payload: `project_id`, `cycle_id`, `approval_id`, `dashboard_url` (`scripts/demo/chained/driver.py`).
- DC-004 pause moved to eligible release; UI approval path via `complete_release_after_optional_ui_approval`.
- Dashboard: `?approval=` deep link on cycle map; `tests/e2e/mvp-chained.spec.ts` (opt-in live); `scripts/demo/resume_mvp_pause.py`.
