# ObjectInspector

Context column for the selected record: state → reason → provenance and scope → relations → permitted commands → open drill-down.

- **Provide:** `journey`, `stage`, `id`, `onSelect`, `onOpen(screen, id)`, `onCommand(cmd, id)`, `lens`, `onHoverRel`.
- Relations read as sentences from the owning record; hovering one locates its edge on the map.
- Commands show their typed API; disabled commands carry their reason. The footer always offers the lane's drill-down.
