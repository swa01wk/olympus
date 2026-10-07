Olympus is a governed software-delivery control plane. Its UI is a **visible control plane**: the Delivery Cycle map is the primary workspace. Overview, Specs, Tasks, Executions, Code, Traceability, Impact, Assurance and Release are drill-downs one click away from it. Every view answers five questions in a fixed order: **state → reason → evidence → permitted action → traceability**.

This system holds the foundations, the components, ten canonical screens and the four-journey specification. Screens are live, fixture-driven prototypes. Switch the cycle picker (DC-001 Greenfield, DC-002 Brownfield, DC-003 Feature Change, DC-004 Bug Fix) to run each journey through the same screens. SupportDesk names, IDs, SHAs, counts and code excerpts are illustrative fixtures, not extracted records.

Read next: **UI concept** (why the map is the hub) → **Navigation** → **Screens** → **Journeys** → **Graph grammar** → **Truth rules** → **Engineering handoff**.

## Content fundamentals

- **Say what is true, in the order it is decided.** Lead with the state, then the reason, then what may be done. "Release blocked: AC-011-03 has no E2E evidence at c83a12d." Not "Almost there!"
- **Name the record.** Every claim carries an ID, set in `id` (mono): `TASK-104`, `TC-104 v2`, `IC-003`. Put the version with the ID, never in prose ("SPEC-011 v2", not "the latest spec").
- **SHAs are always explicit and short.** Use 7 characters in `sha`: `c83a12d`. Always say which scope a SHA belongs to: provisional candidate, canonical assurance target, or released baseline.
- **Use sentence case for UI text** and UPPERCASE only for lifecycle states and the `label` style (object types, column headers): `EXECUTION ATTEMPT`, `ASSURANCE`. Lifecycle stage names keep their persisted spelling with spaces for underscores: `IMPACT ANALYSIS`.
- **Address the operator as "you" only when an action is theirs.** "Release approval APR-302 is waiting for you." System actors are named: Olympus, scheduler, ToolGateway, Warden, Sentinel, Forge, Scout.
- **Agent names appear only in execution context** (Execution Inspector, attempt metadata). They never organize navigation.
- **Never claim more than the evidence.** Probable cause is "Probable cause · p = 0.78", never "Root cause". A reproduced defect is "Failure reproduced", never "Passed". Proof that is ready while approval is outstanding is "Awaiting approval", never "Ready to release".
- **Never invent a completion percentage.** Coverage always shows its denominator and says what it counts: "Mandatory AC proof for R2 · 11 / 12".
- **Never use emoji.** State glyphs (■ ✓ ● ‖ ⊘ ✕ ↻ ◐ ○ !) are typographic marks paired with a word.

## Visual foundations

**Color.** The palette is neutral first. One accent (`active`) means selection, current stage, running work and links. Three signal hues carry state: `success`, `attention` and `failure`.
- Set the workspace on `bg`. Put panels, inspector, dialogs and materialized nodes on `surface`. Put lanes, table headers, code and neutral chips on `surface-sunken`.
- Set body text in `text` and metadata in `text-secondary`. Both pass 4.5:1 on `bg`, `surface` and `surface-sunken` in light and dark.
- Fill status chips with the tone's tint and text: `success` on `success-tint`, `attention` on `attention-tint`, `failure` on `failure-tint`, `active` on `active-tint`. A chip always carries a glyph and a word. `success` and `failure` are told apart by word and glyph as well as hue.
- Use `border` only for quiet structure. Use `border-strong` wherever a line carries meaning: dashed future-obligation nodes, control outlines and inactive edges. It holds 3:1 on surfaces.
- Draw context edges in `edge` and the selected neighbourhood in `edge-strong`. Draw the edge being located from the inspector in `active`.
- Use `primary` / `on-primary` for the single primary command in a view (Open contextual detail, Approve, Execute release).
- Never use gradients. Never tint a whole lane or panel by status. Only the lane of the current lifecycle stage gets `active-tint` with an `active` outline.

**Type.** IBM Plex Sans for interface, IBM Plex Mono for identifiers (hosted on Google Fonts).
- `title` 24/30 medium: one per screen. `section` 16/22 medium: panel headings. `body` 14/20 for reasons and dialog copy. `body-sm` 13/18 for tables, node titles and nav.
- `label` 11/14 uppercase, tracked: object types and column headers. It is the smallest size allowed.
- `id`, `sha` and `code` (mono) for entity IDs, versions, relation types, SHAs, routes, timestamps and typed command previews.
- `stat` 28/32 appears only in the Overview truth tiles.
- Never shrink a whole graph to fit. Switch to scroll or list mode instead.

**Spacing and layout.** The base unit is 8px (`space-2`). Pad nodes and table cells with `space-3` and panels with `space-4` to `space-5`. Wide desktop (1440) is rail `rail-width` 76px + flexible workspace + inspector `inspector-width` 320px. Below 1280px the inspector moves under the graph and lanes keep `lane-min-width` 148px with horizontal scroll. Below 720px the rail collapses and the graph becomes list mode.

**Borders, radii, elevation.** Separate panels with borders, not shadows. Radii: `radius-chip` 4px for chips, `radius-control` 6px for buttons, inputs and graph nodes, `radius-surface` 8px for panels, lanes and dialogs. `shadow-overlay` appears only on dialogs, drawers and toasts.

**States.**
- **Selection** is a 2px `active` outline, never a fill.
- **Materialized record**: solid `border-strong` on `surface`.
- **Future obligation**: dashed `border-strong` on transparent, text in `text-secondary`, chip "Future obligation". It is never drawn as completed.
- **Collapsed group**: stacked offset outlines plus "×n".
- **Outside the active lens**: 32% opacity.
- **Disabled commands**: `surface-sunken` fill, `text-secondary` text, and a tooltip or caption saying why.
- **Focus**: 2px solid `focus` ring, 2px offset, on every interactive element.

**Motion.** Keep it to 120ms opacity changes on lens switches. Nothing animates to imply progress the server has not confirmed.

## Iconography

Olympus uses no icon font. Navigation uses **monograms**: lane codes `IN WK EX CD EV OU` for drill-downs, `MAP` for the hub, `PO`, `TR`, `IM`, `IO`, `AU`. They are set in `id` mono inside a 76px rail with an 11px label beneath. State uses the **typographic glyphs** listed above, always beside a word. No logo was provided: the product name is set as a tracked uppercase wordmark in `body-sm` semibold. Replace it when a real mark exists. Do not draw one.

## Accessibility

- Every status has text plus a glyph; colour is never the only signal.
- The graph has an equivalent **List** view over the same records, and every node is a keyboard-focusable button with an `aria-label` that states type, ID, title and state.
- Dialogs trap focus, close on Escape and restore focus to the opener. Approvals are never placed behind a chat transcript.
- Contrast: all text pairs ≥ 4.5:1 and all meaningful borders, focus rings and edges ≥ 3:1, in both themes.
