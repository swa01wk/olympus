# Frontend fixture E2E coverage (`@frontend-e2e @fixture-journey`)

Not backend E2E proof. Maps Playwright specs to journeys and transparency dimensions.

| Journey | Spec | Checkpoints | State | Control | Execution | Traceability | Repo truth |
|---|---|---|---|---|---|---|---|
| Feature Change | `journeys/feature-change.spec.ts` | 00–11 + traversal | ✓ | ✓ (05) | ✓ (05) | partial | ✓ (05, 08, 11) |
| Greenfield | `journeys/greenfield.spec.ts` | 00, 14 + traversal | ✓ | — | — | — | ✓ (14) |
| Brownfield | `journeys/brownfield.spec.ts` | 00, 11 + traversal | ✓ | — | — | — | — |
| Bug Fix | `journeys/bug-fix.spec.ts` | 00, 07, 11 + traversal | ✓ | ✓ (07) | partial | — | ✓ (11) |
| Cross-cutting | `cross-cutting/*.spec.ts` | representative | ✓ | ✓ | ✓ | partial | ✓ |

Gaps (UI/FX follow-ups): full per-checkpoint five-dimension matrix, evidence registry rows, release manifest view, lineage click-through, greenfield/brownfield fixture narrative depth (FX-02/FX-03), `advancesOn` inbox flows for all approval keys.
