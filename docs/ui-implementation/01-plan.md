# Phase 1 — Implementation plan

**Prerequisite:** Approval of `00-discovery.md` and this plan before any code in `apps/dashboard/`.

**Strategy:** Recreate `apps/dashboard/` as a control-plane-first Next.js app aligned with `docs/design/olympus-ui-spec/`. Preserve **deep links** from the legacy app via redirects where paths differ from design `02-navigation.md`.

---

## 1. Target route map

Design routes reconciled with legacy URLs (redirect old → new).

| Screen | Design route | Implementation route | Legacy redirect |
|--------|--------------|----------------------|-----------------|
| S01 Overview | `/projects/:projectId` | same | — |
| S02 Cycle map (hub) | `/projects/:projectId/cycles/:cycleId?selected=&lens=` | same | `/projects/:id/control-plane` → cycle map |
| S03 Specs | `/projects/:projectId/features/:featureId/specs/:version` | same | `/projects/:id/product` → default feature/spec |
| S04 Task DAG | `/cycles/:cycleId/tasks?selected=` | **`/projects/:projectId/cycles/:cycleId/tasks?selected=`** (project context for shell) | legacy used nested path |
| S05 Execution | `/executions/:executionId` | same | — |
| S06 Code | `/projects/:projectId/code?index=&symbol=` | same | — |
| S07 Traceability | `/projects/:projectId/lineage?selected=&cycle=` | same | — |
| S08 Impact | `/cycles/:cycleId/impact` | **`/projects/:projectId/cycles/:cycleId/impact`** | — |
| S09 Assurance | `/cycles/:cycleId/assurance?candidate=` | **`/projects/:projectId/cycles/:cycleId/assurance`** | — |
| S10 Release / outcome | `/cycles/:cycleId/outcome` | **`/projects/:projectId/cycles/:cycleId/outcome`** | `/releases` list remains at project level |
| IO Integrations | (utility) | `/projects/:projectId/integrations` | keep |
| AU Audit | (utility) | `/audit` or `/projects/:projectId/audit` | keep global audit |
| Login | — | `/login` | keep |

**URL-preserved state:** `projectId`, `cycleId`, `selected` (record id), `lens`, `index` / `symbol`, `candidate` (IC id), `shaScope` query where needed (see ShaScopeBanner).

**App shell:** All cycle-scoped drill-downs render **CycleHeader + LifecycleRibbon + LaneStrip + Back to map**.

---

## 2. Lane mapping (single config file)

**File (Phase 2):** `apps/dashboard/src/control-plane/lanes.ts`

| Lane code | `LaneId` | Record kinds (graph node types) |
|-----------|----------|----------------------------------|
| IN | `intent` | ProductSource, Capability, Feature, FeatureSpec, SpecDelta, AcceptanceCriterion, ImplementationSpec, Architecture, ChangeRequest, Defect, Clarification, Decomposition, ChangeInterpretation, ObservedBehavior, RecoveredSpec, KnowledgeItem (intent-class) |
| WK | `work` | Task, TaskDependency, TaskPlan, TaskContract |
| EX | `exec` | Execution, ExecutionSnapshot, ActionRequest, Artifact, Clarification (checkpoint), ModelCall (as sub-row in S05) |
| CD | `code` | Repository, CodeIndexVersion, IntegrationCandidate, CandidateCommit, CodeEntity (summary nodes), Architecture (structural) |
| EV | `evidence` | Evidence, VerificationObligation, Gate, Finding, Approval, Baseline, PromotionDecision, ReadinessAssessment, Review |
| OU | `outcome` | Release, ReleaseManifest, ReleaseEligibilityEvaluation, DeliveryOutcome, Deployment (connector-scoped) |

**Rail monograms:** `PO`, boxed `MAP`, divider, `IN WK EX CD TR IM EV OU`, bottom `IO`, `AU`.  
`TR` / `IM` are **lenses** on S02 (not lanes)—routes S07/S08.

**Attention flags:** Per-lane boolean derived from attention queue items mapped to lane via record kind.

---

## 3. Stage → lane mapping (backend state names)

**File:** `apps/dashboard/src/control-plane/stage-lanes.ts`  
Keys: `DeliveryCycleType` → ordered `{ state, laneCode }[]`.

### GREENFIELD_BUILD

| State | Lane |
|-------|------|
| DISCOVERY | IN |
| PRODUCT_MODEL | IN |
| ARCHITECTURE | IN |
| PLANNING | WK |
| DEVELOPMENT | EX |
| INTEGRATION | CD |
| ASSURANCE | EV |
| RELEASE | OU |
| COMPLETE | OU |

### BROWNFIELD_ONBOARDING

| State | Lane |
|-------|------|
| RECON | CD |
| CODE_INDEX | CD |
| RECOVERED_SPEC | IN |
| BASELINE | EV |
| READINESS | EV |
| REMEDIATION | WK |
| READY | OU |

### FEATURE_CHANGE

| State | Lane |
|-------|------|
| INTAKE | IN |
| SPEC_DELTA | IN |
| IMPACT_ANALYSIS | CD |
| PLANNING | WK |
| DEVELOPMENT | EX |
| INTEGRATION | CD |
| ASSURANCE | EV |
| RELEASE | OU |
| COMPLETE | OU |

### BUG_FIX

| State | Lane |
|-------|------|
| TRIAGE | IN |
| REPRODUCTION | EV |
| EXPECTED_BEHAVIOR | IN |
| ROOT_CAUSE | CD |
| DEVELOPMENT | EX |
| INTEGRATION | CD |
| REGRESSION | EV |
| ASSURANCE | EV |
| RELEASE | OU |
| COMPLETE | OU |

Terminal `CANCELLED` / `FAILED` → show in ribbon as outcome-adjacent chip, no future lanes.

---

## 4. Status adapter

**File:** `apps/dashboard/src/adapters/status.ts`

Map **backend enum/string** → `{ uiKey, label, tone, glyph }` using vocabulary from `reference-implementation/model.ts` `STATUS` and `components/StatusBadge.md`.

Examples (non-exhaustive; complete in Phase 2):

| Backend | UI key |
|---------|--------|
| `TaskStatus.BLOCKED` | `blocked` |
| `TaskStatus.READY` / `QUEUED` | `ready` / `queued` |
| `ExecutionStatus.CHECKPOINTED` | `checkpointed` |
| `ExecutionStatus.STALE` | `stale` |
| `SpecStatus.PROPOSED` | `proposed` |
| `SpecStatus.APPROVED` | `approved` |
| `ICStatus.INTEGRATING` | `integrating` |
| `ICStatus.READY` | `canonical` |
| `GateStatus.PASS` / `FAIL` | `passed` / `failed` |
| `ReleaseStatus.*` | map per release router |
| `KnowledgeClass.INFERENCE` | `inferred` |
| `KnowledgeClass.UNCERTAINTY` | `decision` / custom copy |

Never send UI keys to the API—display only.

---

## 5. Component → file map

Base: `apps/dashboard/src/components/` (names align with design `07-engineering-handoff.md`).

| Design component | Target path |
|------------------|-------------|
| AppShell, TopBar, NavRail | `shell/AppShell.tsx`, `shell/TopBar.tsx`, `shell/NavRail.tsx` |
| LifecycleRibbon, JourneySpine, LaneStrip | `cycle/LifecycleRibbon.tsx`, `cycle/JourneySpine.tsx`, `cycle/LaneStrip.tsx` |
| AttentionStrip | `cycle/AttentionStrip.tsx` |
| ControlPlaneGraph, ObjectNode | `graph/ControlPlaneGraph.tsx`, `graph/ObjectNode.tsx` |
| ObjectInspector, WhyPanel, CommandList | `inspector/ObjectInspector.tsx`, `inspector/WhyPanel.tsx`, `inspector/CommandList.tsx` |
| Primitives (Button, StatusBadge, …) | `ui/*` (shadcn) + `primitives/*` |
| TaskDag, TaskContractCard | `tasks/TaskDag.tsx`, `tasks/TaskContractCard.tsx` |
| ExecutionTimeline | `executions/ExecutionTimeline.tsx` |
| ShaScopeBanner | `code/ShaScopeBanner.tsx` |
| EvidenceMatrix, EligibilityChecklist | `assurance/EvidenceMatrix.tsx`, `assurance/EligibilityChecklist.tsx` |
| VersionDiff | `specs/VersionDiff.tsx` |
| ApprovalDialog, CheckpointDialog, IntakeForm | `dialogs/*` |
| Ask Olympus drawer | `shell/AskOlympusDrawer.tsx` |

Screens (App Router): `app/(console)/projects/[projectId]/...` per §1.

---

## 6. Data layer outline (Phase 3)

| Layer | Location |
|-------|----------|
| HTTP client + auth header | `src/api/client.ts` |
| Generated or hand types | `src/api/types/` |
| TanStack Query keys + hooks | `src/api/hooks/` |
| SSE hook (invalidate queries) | `src/api/sse/useCycleEventStream.ts` |
| `buildControlPlaneGraph()` | `src/control-plane/build-graph.ts` |
| `sendCommand()` | `src/api/commands.ts` |
| Attention merge | `src/control-plane/attention.ts` |

---

## 7. Phases 2–7 — commit plan

Each phase = one reviewable commit (message `ui(phase-N): …`). No backend files.

### Phase 2 — Foundations

- Scaffold Next.js app in `apps/dashboard/` (package.json, tsconfig, tailwind, shadcn).
- Tokens from `tokens.json` → CSS variables + Tailwind theme; IBM Plex fonts.
- Primitives: Button, StatusBadge, ProvenanceBadge, IdRef, Sha, Panel, KV, EmptyState.
- `lanes.ts`, `stage-lanes.ts`, `status.ts` stubs with unit tests.

### Phase 3 — Data layer

- API client, hooks for projects, cycles, views, inbox, SSE.
- `buildControlPlaneGraph`, `attention.ts`, `sendCommand`.
- Stream indicator in TopBar.

### Phase 4 — Shell + S02

- AppShell, cycle picker, map page, graph + inspector + lenses + list mode.
- ObjectInspector wired to real records (partial Why per gap report).

### Phase 5 — Drill-downs S01, S03–S10, IO, AU

- Implement screens per `03-screens.md` / `04-journeys.md`.
- Journey-specific S03 modes; Brownfield S10 without release execute.

### Phase 6 — Dialogs + commands

- Approval, checkpoint, intake, Ask Olympus.
- Focus trap + command preview payloads.

### Phase 7 — Exceptional states + tests

- `06-truth-rules.md` patterns.
- Unit tests: graph adapter, status, stage-lanes, attention.
- Component tests: StatusBadge, ObjectInspector, EvidenceMatrix, EligibilityChecklist.
- Playwright against local backend or recorded fixtures under `apps/dashboard/tests/fixtures/`.

---

## 8. Phase 1 exit

- [x] Route map, lane config plan, stage-lanes, status adapter plan, component map, commit breakdown
- [x] Gaps cross-referenced in `gap-report.md`
- [ ] **Stopped — awaiting your approval before Phase 2**
