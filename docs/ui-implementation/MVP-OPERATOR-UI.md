# MVP operator UI — acceptance & Phase 19 alignment

**Status:** Phases 0–7 complete (2026-10-07).  
**Scope:** `apps/dashboard/` + Control API only (no backend changes).

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

## 3. Re-enabling Plan 19 Playwright walkthrough

Suggested follow-up (backend + UI, separate PR):

1. Extend `scripts/demo/run_mvp.py` **`--pause-before approve_release:DC-004`** to open `http://127.0.0.1:3010/...` with a known `projectId` / `cycleId` / `approvalId` (from driver state file).
2. Add `tests/e2e/mvp-chained.spec.ts` in `apps/dashboard` that:
   - reads pause metadata from env (or a JSON file written by the driver);
   - completes R3 approval through **ApprovalDialog**;
   - asserts VIEWER token cannot complete the same action (API 403 or disabled UI — prefer API assertion in journey test).
3. Run chaos item “control-api restart during SSE” with dashboard connected (Plan 19 §4.6) — assert **Stream disconnected** notice and successful refetch.

Until then, Plan 19 items **19.16** and **Playwright walkthrough** remain **interim API/journey** proof.

---

## 4. CI

Workflow [`.github/workflows/dashboard.yml`](../../.github/workflows/dashboard.yml):

- `npm run check` on every push/PR touching `apps/dashboard/`
- `npm run test:e2e` with Playwright (dev server on port **3010**, API routes stubbed in spec)

---

## 5. Known gaps (unchanged)

See [`gap-report.md`](./gap-report.md) — especially G1 (composed graph), G2 (partial Why), G3 (task allowed_commands).
