# Engineering handoff

## Stack and data flow

Next.js + TypeScript + React + shadcn/ui, TanStack Query and SSE, as documented. The frontend **projects** authoritative control-API responses. SSE events invalidate and refetch server state; completion is never fabricated in a client reducer. When the stream drops, show the last authoritative refresh time and stop implying progress.

## Read models the UI needs

- **Every record:** entity type, ID, version, status, source / provenance, policy reason, input / candidate / index SHA, evidence links and **permitted commands** (with disabled reasons).
- **Every edge:** actual relation type, source and target identity, provenance (GENERATED_LINEAGE / DISCOVERED / HUMAN_CONFIRMED / structural), confidence where relevant, source evidence and version scope.
- **Why record** per status: predicates with pass / unmet / n-a and detail, blocking IDs, policy key + version, inputs, evaluated-at and evaluator.
- **Cycle:** journey, lifecycle stages with lane mapping, current stage, attention items in priority order.

## Commands

Use the documented command patterns, never PATCH lifecycle fields from a view:
`POST /delivery-cycles/{id}/commands/{command}` · `POST /approvals/{id}/decision` · `POST /executions/{id}/cancel` · `POST /specs/{id}/approve` · `POST /releases/{id}/approve` · `POST /releases/{id}/execute`. Send actor context, expected version / state and an idempotency key. After a rejected command, show the denial reason and re-render the current authoritative state.

## Component inventory → implementation

| Component here | Role | Notes for shadcn/ui build |
|---|---|---|
| AppShell, TopBar, NavRail | Frame, cycle picker, stream state | Rail monograms are lane codes; flags from attention items |
| LifecycleRibbon, JourneySpine, LaneStrip | Lifecycle and position | Spine positions come from measured lane centres |
| AttentionStrip | Top reason + actions | Priority order is a server concern; UI renders it |
| ControlPlaneGraph, ObjectNode | The map | SVG edges over a CSS grid of lanes; List mode over the same data |
| ObjectInspector, WhyPanel, CommandList | Reasons and permitted actions | Commands open dialogs or send typed commands |
| TaskDag, TaskContractCard, AttemptHistory | Work lane | Contract is immutable per version |
| ExecutionTimeline | Governed events | One row per ToolGateway decision |
| ShaScopeBanner | Index scope | Three scopes, never merged |
| EvidenceMatrix, EligibilityChecklist | Proof and eligibility | Old-SHA rows labelled, never counted |
| VersionDiff | Spec versions | Immutable versions side by side |
| ApprovalDialog, CheckpointDialog, IntakeForm, Drawer | Decisions and intake | Focus trap, Escape, focus restore; server validates version and authorization |

Every component needs loading, empty, unavailable, permission-denied and stale variants where meaningful.

## Acceptance for the UI

- All four journeys preserve state clarity, control-plane reasons, execution transparency, traceability and repository truth.
- A reviewer can reach raw supporting proof from any PASS indicator, and deep links work Feature/Spec → Task/Execution → CodeEntity → Evidence/Gate → Release and back.
- Rejected approval, stale execution, missing evidence, integration conflict and unknown connector result all have reviewable UI states.
- Brownfield finishes at readiness with no release command. Bug Fix retains before-failure evidence and shows exact-SHA after-proof.
- No secrets in model metadata, tool logs or source snapshots.

## What this is — and is not

These are proposed designs: layout, colours, routes, component names and relation labels are design choices to validate. The prototypes are fixture-driven; their buttons preview typed commands and record nothing. Stage scrubbing on the ribbon is a design-review aid — production shows recorded history only. Backend wiring, real pan/zoom and virtualization, live agent execution, approvals, connector actions and deployments are subsequent implementation work. No UI concept is the technical definition of done.

## Source cross-reference

| Requirement | Architecture plan v1.2 | Technical spec v1.0 |
|---|---|---|
| Control-plane authority / operator | §§1–4, 23 | §§1, 5, 7, 25 |
| Versioned product semantics | §§4.1, 14 | §§5.2, 6, 14 |
| Task / contract / execution | §§5, 7–9 | §§8–12 |
| Canonical index / traceability | §§13–14 | §§13–14, 17 |
| Four journeys | §§15–18, 26.1 | §§19–22 |
| Evidence / gates / outcome | §§11–12 | §§18, 23 |
| Inbound / outbound / reconciliation | §§20.1–20.4 | §§15–16 |
| Frontend / visibility | §§23–24, 26 | §§24–27, 31–32 |
