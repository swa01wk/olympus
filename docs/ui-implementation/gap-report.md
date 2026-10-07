# Gap report — Olympus UI implementation

Tracks **Missing** and **Derivable** items from Phase 0. Each entry states how the UI degrades without backend changes.

| ID | Item | Classification | UI degradation |
|----|------|----------------|----------------|
| G1 | Unified control-plane graph `{nodes, edges}` API | **Missing** | Client composes graph from many GETs; loading/skeleton per lane; empty lanes when records not yet created; no fake “future” nodes from lifecycle alone. |
| G2 | Per-record generic “Why this state?” document | **Partial / Missing** for most types | Inspector shows **Unavailable** for Why except: cycle transitions (`next-transitions`), task (`eligibility` + `blocked_reason`), release (`release-eligibility`), gate/assurance slices from `/views/ic/.../assurance`. |
| G3 | Task `allowed_commands` list on API | **Missing** | Show task commands from catalog + state-appropriate labels; disable with “Send to preview eligibility” / server rejection message after attempt—not client-invented guard pass. |
| G4 | Lifecycle ribbon stage history / scrub | **Missing** | Ribbon shows current + **past stages as labels only** (non-clickable); no future stages. |
| G5 | Server-defined attention queue priority | **Missing** | Merge `/views/inbox` + cycle counts; sort with design `ATTENTION_ORDER` in frontend until backend provides ordering. |
| G6 | `views/.../coverage` overall percentage | **Available but misleading** | S01 shows **explicit denominators only**; ignore or hide aggregate `%` field per truth rules. |
| G7 | Deployment success as nav badge | **Partial** | No green deployment indicator without connector/deployment result; show separate deployment approval/action status. |
| G8 | Ask Olympus product requirement | **Derivable** | Wire to `/orchestrator/*` if enabled; else drawer disabled + link to gap G8 in settings copy. |
| G9 | Reconciliation `POST .../retry` vs design | **Design override** | For `ConnectorActionStatus.UNKNOWN` / reconciliation unknown: show **“Reconciliation required”**—**no retry button** (even though API has retry). |
| G10 | REMEDIATION journey (`DeliveryCycleType.REMEDIATION`) | **Backend only** | Not in design four-journey pack; show cycle with generic map or “Journey not in design pack” empty state if encountered. |
| G11 | OpenAPI codegen in CI | **Missing tooling in repo** | Hand-written or locally generated types under `apps/dashboard/src/api/` from router models; refresh when backend changes. |
| G12 | Dashboard env in root `.env.example` | **Missing** | Document `NEXT_PUBLIC_OLYMPUS_API_URL` in `apps/dashboard/README.md` only. |
| G13 | Playwright CI job | **Addressed (dashboard workflow)** | `.github/workflows/dashboard.yml` runs `npm run check` + stubbed `npm run test:e2e`. Live chained R3 spec: `tests/e2e/mvp-chained.spec.ts` (opt-in `MVP_E2E_LIVE=1`; see `MVP-OPERATOR-UI.md` §3). |
| G14 | Spec-code links single endpoint | **Partial** | S06 may require N+1 fetches; show loading per section. |
| G15 | Lease entity exposed separately | **Partial** | Show lease fields from execution/snapshot JSON when present; else “Lease detail unavailable”. |

## Design vs backend naming

Design lifecycle names in the prompt table match **`core/state/machines.py`** state strings for the four primary journeys. Backend cycle `type` values use enums (`GREENFIELD_BUILD`, `BROWNFIELD_ONBOARDING`, `FEATURE_CHANGE`, `BUG_FIX`)—map to design journey IDs GF/BF/FC/BG in the frontend only.

## Disagreements logged (priority: backend wins)

1. **Control-plane view** — Design assumes rich map; backend `/views/.../control-plane` is aggregate counters only (G1).
2. **Coverage percent** — Backend exposes `acceptance_criteria_with_evidence_pct`; design forbids invented completion % (G6).
3. **Reconciliation retry** — Backend exposes retry; design forbids retry for unknown outcomes (G9).
