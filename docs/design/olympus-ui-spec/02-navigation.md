# Navigation

## Model

```
                S01 Project Overview
                        │ Open control-plane map
                        ▼
 Trace lens ◀── S02 Delivery Cycle · control-plane map ──▶ Inspector
 Impact lens ◀─   IN    WK    EX    CD    EV    OU
   │   │          │     │     │     │     │     │
   ▼   ▼          ▼     ▼     ▼     ▼     ▼     ▼
  S07 S08        S03   S04   S05   S06   S09   S10
                 └──── ← Back to cycle map (restores selection) ────┘
```

- **Rail.** `PO` Project, `MAP` Cycle map (boxed: the hub), a "drill" divider, then `IN WK EX CD TR IM EV OU`, with utilities `IO` Integrations and `AU` Audit at the bottom. A lane monogram shows a flag glyph when that lane has an attention item.
- **Top bar.** Product wordmark, project, **cycle picker** (switching it switches the journey on every screen), event-stream state ("Live · refreshed 10:53:12" or "Disconnected · last refresh 10:41:07"), New delivery cycle, Ask Olympus.
- **Entering a drill-down.** Click a lane header, use "Open in <screen> →" in the inspector, click a lane in the lane strip, or use the rail. The selected record carries over; if it belongs to another lane, the drill-down opens its lane's default record.
- **Leaving a drill-down.** "← Back to cycle map" restores selection, lens and graph position.

## State preserved in every URL

`project · cycle · selected object · version · index scope · target SHA`. A shared link must reproduce the view, including which SHA scope the operator was reading.

| Screen | Proposed route |
|---|---|
| S01 Project Overview | `/projects/:projectId` |
| S02 Delivery Cycle | `/projects/:projectId/cycles/:cycleId?selected=:id&lens=:lens` |
| S03 Product / Specs | `/projects/:projectId/features/:featureId/specs/:version` |
| S04 Task DAG | `/cycles/:cycleId/tasks?selected=:taskId` |
| S05 Execution Inspector | `/executions/:executionId` |
| S06 Code Intelligence | `/projects/:projectId/code?index=:indexId&symbol=:symbolId` |
| S07 Traceability | `/projects/:projectId/lineage?selected=:entityId&cycle=:cycleId` |
| S08 Impact Explorer | `/cycles/:cycleId/impact` |
| S09 Assurance | `/cycles/:cycleId/assurance?candidate=:candidateId` |
| S10 Release | `/cycles/:cycleId/outcome` |

Routes are design proposals, not assertions that endpoints exist.

## Global utilities (auxiliary, not journeys)

- **New delivery cycle**: intent-specific intake. Greenfield takes a product source. Brownfield takes a repository, branch and exact SHA. Feature Change takes the requested behaviour and baseline. Bug Fix takes the observed result, reproduction steps, severity and baseline. Submitting sends a typed create command, waits for the server's acknowledgement, then navigates to the new map.
- **Ask Olympus**: a drawer scoped to the current cycle and stage. Answers are built from authoritative records and link to them. A mutation is only ever offered as an explicit typed command that the operator reviews and sends with normal authorization.
- **Integrations**: inbound events (signature, idempotency key, correlation) and outbound actions (execution and contract scope, policy, result). An unknown outcome must be reconciled before any retry.
- **Audit**: actor, command, time, version, correlation ID, before/after references and rationale. It is filterable, immutable and traversable to failures, approvals and connector results.

## Responsive behaviour

- **≥ 1280px**: rail + graph + 320px inspector.
- **1024–1279px**: the inspector moves under the graph; lanes keep 148px minimum and the graph scrolls horizontally rather than shrinking.
- **≤ 720px**: the rail collapses, the graph defaults to List mode, tables scroll inside their container and dialogs go full width.
