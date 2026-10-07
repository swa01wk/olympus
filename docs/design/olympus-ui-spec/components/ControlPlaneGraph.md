# ControlPlaneGraph

The centrepiece: six fixed lanes of authoritative records with typed edges, the journey spine, four lenses and an accessible list mode.

- **Provide:** `journey`, `stage`, `selected`, `onSelect`, `lens` (`lifecycle` | `trace` | `impact` | `blockers`), `onLens`, `view` (`graph` | `list`), `onView`, `onOpenLane`, `onStage`, optional `focusEdge` (from the inspector's hovered relation).
- Lane order is fixed for every journey; the current stage's lane is outlined. Edges: solid authoritative, dashed inferred, dotted obligation.
- Show the cycle's neighbourhood, not the whole repository. Never shrink to fit — scroll, collapse groups, or switch to list.
