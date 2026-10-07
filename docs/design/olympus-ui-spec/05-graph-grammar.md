# Graph grammar

## Nodes

Each node is one authoritative record, or one future obligation. The anatomy is always the same, top to bottom:

1. **Type** in `label` (e.g. ATTEMPT, FEATURE SPEC, MANDATORY PROOF)
2. **ID · version** in `id`
3. **Title**, at most two lines
4. **Sub-line** (optional, `sha`): SHA scope, counts, or the one fact that matters ("snapshot stale", "p = 0.78")
5. **Status chip**: glyph + word, plus "×n" for a collapsed group

| Variant | Treatment | Meaning |
|---|---|---|
| Materialized | solid `border-strong`, `surface` fill | An authoritative record exists |
| Future obligation | dashed `border-strong`, no fill, `text-secondary` | Will materialize at a named stage; never drawn as complete |
| Selected | 2px `active` outline | Inspector shows this record. Selection never mutates |
| Collapsed group | stacked offset outlines + "×n" | Several records of one kind (e.g. 4 evidence records); inspector lists members |
| Outside lens | 32% opacity | Not part of the active Trace / Impact / Blockers set |
| Impact tag | corner tag DIRECT / INFERRED (dashed) / SCOPE | Only in the Impact lens |

## Edges

Edges point downstream, in the direction authority flows. The persisted relation reads from the record that owns it. In the inspector each edge is a sentence, e.g. "REC-017 RECOVERED_FROM CODE-117 · DISCOVERED · 0.84".

| Style | Use |
|---|---|
| Solid | Authoritative / deterministic relation (structural, generated lineage, approval) |
| Dashed (`attention` when emphasized) | Inferred / discovered relation; carries confidence |
| Dotted | Obligation: either end is a future record, or the target evidence is missing |
| `active`, 2.25px | The edge being located from the inspector's relation list |

Cross-lane edges leave the right side of the source and enter the left side of the target; backward edges (Brownfield, Bug Fix) mirror that. Same-lane edges (DEPENDS_ON, CALLS) route through the lane's left gutter. Typed labels are not painted on the canvas by default — they live in the inspector, and hovering a relation highlights its edge on the map.

**Proposed presentation vocabulary** (map to persisted relation types during implementation): `DERIVED_FROM`, `IMPLEMENTS`, `DEPENDS_ON`, `EXECUTED_AS`, `PRODUCED`, `INTEGRATED_IN`, `CONTAINED_IN`, `VERIFIED_BY`, `APPROVED_BY`, `EVALUATED_IN`, `GATES`, `AUTHORIZES`, plus journey-specific `CONSTRAINS`, `ASSESSED_IN`, `AFFECTS`, `RECOVERED_FROM`, `OBSERVED_IN`, `HAS_UNCERTAINTY`, `RESOLVED_BY`, `PROMOTED_FROM`, `REPRODUCED_AS`, `VIOLATES`, `SUPPORTS`, `LOCATED_IN`, `SCOPES`, `REPROVED_BY`, `SUCCEEDED_BY`, `PINS`.

## Lenses

| Lens | Highlights | Leads to |
|---|---|---|
| Lifecycle (default) | The current stage's lane (outlined) and the selected record's neighbourhood | — |
| Trace | Full upstream + downstream lineage of the selected record | S07 Traceability |
| Impact | Records with direct / inferred / scope impact | S08 Impact Explorer |
| Blockers | Attention items plus the records named in their blocking predicates | the blocking record's drill-down |

## The Why inspector

Every status chip opens the same evaluation record: summary, predicate checks (✓ passed / ✕ unmet / — not applicable, each with a detail), blocking record IDs (clickable), policy key and version, input versions, evaluation time and actor, and the next permitted step. A model explanation may summarize it but never replaces it.

## Progressive disclosure and scale

- Show the **neighbourhood relevant to the cycle**, not a global repository graph. A lane shows at most ~6 records before collapsing same-kind records into a group with a count and its highest-priority state.
- **List mode** projects the same records as an accessible table (lane, record, type, title, state, provenance). Graph and list must come from the same server records.
- Production needs pan/zoom on desktop, focus-on-neighbourhood, breadcrumb reset and virtualization for large graphs — engineering work beyond this concept.
- Lineage is bidirectional. Principal symbols map to specs; helpers inherit context through structural relations rather than duplicate feature links. Discovered edges keep confidence and supporting code/test evidence.
