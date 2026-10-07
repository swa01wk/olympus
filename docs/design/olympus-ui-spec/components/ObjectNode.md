# ObjectNode

One authoritative record (or future obligation) on the control-plane map: type, ID · version, title, sub-line, state chip.

- **Provide:** `node`, `status`, `selected`, `dim`, `impact`, `onClick`, `innerRef` (for edge measurement).
- Variants: materialized (solid), future obligation (dashed, never complete), selected (2px `active` outline), collapsed group (stacked outlines, ×n), dimmed outside a lens, impact tag.
- A node is a button; clicking selects only. Keep titles to two lines and push detail to the inspector.
