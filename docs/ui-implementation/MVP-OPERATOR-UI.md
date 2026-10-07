# MVP operator UI — acceptance & Phase 19 alignment

**Status:** Phases 0–7 complete (2026-10-07).  
**Scope:** Primary work in `apps/dashboard/` + `docs/ui-implementation/`; minimal demo handoff in `scripts/demo/chained/driver.py` and chained journey pause timing for Plan 19 walkthrough.

Plan 19 deferred the **Playwright operator walkthrough** while the legacy dashboard was removed ([`plans/19-final-e2e-and-mvp-acceptance.md`](../../plans/19-final-e2e-and-mvp-acceptance.md) §1 item 7). This rebuild restores a **control-plane-first** client suitable to reintroduce that walkthrough against the SupportDesk chained demo.

---

## 1. What the MVP UI must prove (operator lens)

These mirror Plan 19 human-in-the-loop steps without replacing backend journey tests:

| Plan 19 moment | UI capability | Route / action |
|----------------|---------------|----------------|
| R3 release approval (HUMAN) | Approval dialog with rationale → `POST /approvals/{id}/decision` | Inbox / attention → **Inspect** |
| Clarification during live work | Checkpoint dialog → `POST /clarifications/{id}/answer` | Attention strip |
| New cycle intake | Intake dialog → `POST /projects/{id}/delivery-cycles` | TopBar **New delivery cycle** |
| Operate current cycle | S02 map, lenses, permitted cycle commands (confirm dialog) | `/projects/:id/cycles/:cycleId` |
| Trace / impact / assurance | S07–S09 drill-downs | Nav rail |
| Ask Olympus (optional) | Orchestrator drawer (requires `delivery_cycle_id`) | TopBar **Ask Olympus** |
| VIEWER 403 | N/A in UI-only CI | API tests remain authoritative; UI should show API errors, not fake success |

Backend **MVP_COMPLETE** is still decided by `scripts/acceptance/evaluate_mvp.py` and chained pytest — not by this UI alone.

---

## 2. Manual smoke (local stack)

Prerequisites: Control API on `http://127.0.0.1:8000`, bearer token with OPERATOR scopes.

```bash
cd apps/dashboard
export NEXT_PUBLIC_OLYMPUS_API_URL=http://127.0.0.1:8000
# localStorage key olympus_api_token or NEXT_PUBLIC_OLYMPUS_API_TOKEN
npm install && npm run dev
```

Checklist:

1. **Projects** — `/projects` lists projects from API.
2. **S01** — `/projects/:projectId` shows SHAs, coverage denominators (no overall %), cycle table.
3. **S02** — cycle map loads composed graph; SSE indicator; disconnected notice + refetch when stream drops.
4. **Attention** — pending approval opens ApprovalDialog; clarification opens CheckpointDialog.
5. **Command** — “Why this state?” → permitted cycle command → confirm preview → POST succeeds or shows server rejection.
6. **Drill-downs** — rail links S03–S10, IO, AU resolve without 404.
7. **Truth** — integrator failure shows **Reconciliation required** (no retry button).

Automated: `npm run check` (26 unit/component tests), `npm run test:e2e` (stubbed API smoke).

---

## 3. Plan 19 Playwright walkthrough (R3 approval)

Implemented (2026-10-07):

1. **`--pause-before approve_release:DC-004`** writes `var/olympus/demo/pause.json` with `project_id`, `cycle_id`, `release_id`, `approval_id`, `api_base`, and `dashboard_url` (default dashboard `http://127.0.0.1:3010`).
2. Pause fires **after** DC-004 release is **ELIGIBLE** (not at cycle start). The journey completes release execution after `resumed: true` (UI may have already `POST /approvals/{id}/decision`).
3. Cycle map deep link: `?approval={uuid}` opens **ApprovalDialog** (`CycleMapScreen` + `OperatorDialogsProvider.openApproval`).
4. **`tests/e2e/mvp-chained.spec.ts`** — opt-in with `MVP_E2E_LIVE=1`, `OLYMPUS_HUMAN_TOKEN`, and an active pause file; not run in default dashboard CI.

```bash
cd apps/dashboard
export MVP_E2E_LIVE=1 OLYMPUS_HUMAN_TOKEN="$OLYMPUS_HUMAN_TOKEN"
npm run test:e2e -- tests/e2e/mvp-chained.spec.ts
```

Manual resume without Playwright: `uv run python scripts/demo/resume_mvp_pause.py` after approving in the browser.

Still TODO for full Plan 19 **19.16**: VIEWER 403 assertion in the same Playwright session; chaos “control-api restart during SSE” with dashboard connected.

---

## 4. CI

Workflow [`.github/workflows/dashboard.yml`](../../.github/workflows/dashboard.yml):

- `npm run check` on every push/PR touching `apps/dashboard/`
- `npm run test:e2e` with Playwright (dev server on port **3010**, API routes stubbed in spec)

---

## 5. Known gaps (unchanged)

See [`gap-report.md`](./gap-report.md) — especially G1 (composed graph), G2 (partial Why), G3 (task allowed_commands).
